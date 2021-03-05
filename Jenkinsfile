pipeline {
    agent { label 'docker-slave' }
       environment {
       // OPENSTACK SETTINGS
       ssh_key_name = "jenkins-opera"
       image_name = "centos7"
       network_name = "orchestrator-network"
       security_groups = "default,sodalite-remote-access,sodalite-rest,sodalite-uc"
       flavor_name = "m1.medium"
       // DOCKER SETTINGS
       docker_network = "sodalite"
       dockerhub_user = " "
       dockerhub_pass = " "
       docker_registry_ip = credentials('jenkins-docker-registry-ip')
       docker_registry_cert_country_name = "SI"
       docker_registry_cert_organization_name = "XLAB"
       docker_public_registry_url = "registry.hub.docker.com"
       docker_registry_cert_email_address = "dragan.radolovic@xlab.si"
       cert_path = "/home/xopera/certs"
       cert_files_prefix = "image.docker.local"

       // POSTGRES SETTINGS
       postgres_address = "xopera-postgres"
       postgres_user = credentials('postgres-user')
       postgres_password = credentials('postgres-password')
       postgres_db = "postgres"
       postgres_port = "5432"
       // XOPERA SETTINGS
       xopera_debug = "false"
       xopera_log_level = "debug"
       // GIT SETTINGS
       git_type = "gitlab"
       git_server_url = "https://gitlab.com"
       git_auth_token = credentials('git-auth-token')
       // OPENSTACK DEPLOYMENT FALLBACK SETTINGS
       OS_PROJECT_DOMAIN_NAME = "Default"
       OS_USER_DOMAIN_NAME = "Default"
       OS_PROJECT_NAME = "orchestrator"
       OS_TENANT_NAME = "orchestrator"
       OS_USERNAME = credentials('os-username')
       OS_PASSWORD = credentials('os-password')
       OS_AUTH_URL = credentials('os-auth-url')
       OS_INTERFACE = "public"
       OS_IDENTITY_API_VERSION = "3"
       OS_REGION_NAME = "RegionOne"
       OS_AUTH_PLUGIN = "password"

       // ROOT X.509 CERTIFICATES
       ca_crt_file = credentials('xopera-ca-crt')
       ca_key_file = credentials('xopera-ca-key')

       // CI-CD vars
       // When triggered from git tag, $BRANCH_NAME is actually GIT's tag_name
       TAG_SEM_VER_COMPLIANT = """${sh(
                returnStdout: true,
                script: './validate_tag.sh SemVar $BRANCH_NAME'
            )}"""

       TAG_MAJOR_RELEASE = """${sh(
                returnStdout: true,
                script: './validate_tag.sh MajRel $BRANCH_NAME'
            )}"""

       TAG_PRODUCTION = """${sh(
                returnStdout: true,
                script: './validate_tag.sh production $BRANCH_NAME'
            )}"""

       TAG_STAGING = """${sh(
                returnStdout: true,
                script: './validate_tag.sh staging $BRANCH_NAME'
            )}"""
   }
    stages {
        stage ('Pull repo code from github') {
            steps {
                checkout scm
            }
        }
        stage('Inspect GIT TAG'){
            steps {
                sh """ #!/bin/bash
                echo 'TAG: $BRANCH_NAME'
                echo 'Tag is compliant with SemVar 2.0.0: $TAG_SEM_VER_COMPLIANT'
                echo 'Tag is Major release: $TAG_MAJOR_RELEASE'
                echo 'Tag is production: $TAG_PRODUCTION'
                echo 'Tag is staging: $TAG_STAGING'
                """
            }

        }
        stage('Test xOpera') {
            steps {
                sh  """ #!/bin/bash
                        python3 -m venv venv-test
                        . venv-test/bin/activate
                        pip3 install --no-cache-dir -r requirements.txt
                        ./generate.sh
                        cd src/
                        touch *.xml
                        python3 -m pytest --junitxml=results.xml --cov=./opera/api/ --cov=./opera/api/gitCsarDB --cov=./opera/api/blueprint_converters --cov=./opera/api/settings --cov=./opera/api/service --cov=./opera/api/util --cov=./opera/api/controllers --cov-report xml
                    """
                junit 'src/results.xml'
            }
        }
        stage('SonarQube analysis'){
            environment {
            scannerHome = tool 'SonarQubeScanner'
            }
            steps {
                withSonarQubeEnv('SonarCloud') {
                    sh  """ #!/bin/bash
                            ${scannerHome}/bin/sonar-scanner
                        """
                }
            }
        }
        stage('Build xopera-rest-api') {
            when {
                allOf {
                    // Triggered on every tag, that is considered for staging or production
                    expression{tag "*"}
                    expression{
                        TAG_STAGING == 'true' || TAG_PRODUCTION == 'true'
                    }
                }
             }
            steps {
                sh """#!/bin/bash
                    ./make_docker.sh build xopera-rest-api
                    """
            }
        }
        stage('Push xopera-rest-api to sodalite-private-registry') {
            // Push during staging and production
            when {
                allOf {
                    expression{tag "*"}
                    expression{
                        TAG_STAGING == 'true' || TAG_PRODUCTION == 'true'
                    }
                }
            }
            steps {
                withDockerRegistry(credentialsId: 'jenkins-sodalite.docker_token', url: '') {
                    sh  """#!/bin/bash
                        ./make_docker.sh push xopera-rest-api staging
                        """
                }
            }
        }
        stage('Push xopera-rest-api to DockerHub') {
            // Only on production tags
            when {
                allOf {
                    expression{tag "*"}
                    expression{
                        TAG_PRODUCTION == 'true'
                    }
                }
            }
            steps {
                withDockerRegistry(credentialsId: 'jenkins-sodalite.docker_token', url: '') {
                    sh  """#!/bin/bash
                            ./make_docker.sh push xopera-rest-api production
                        """
                }
            }
        }
        stage('Install deploy dependencies') {
            when {
                allOf {
                    expression{tag "*"}
                    expression{
                        TAG_STAGING == 'true' || TAG_PRODUCTION == 'true'
                    }
                }
            }
            steps {
                sh """#!/bin/bash
                    python3 -m venv venv-deploy
                    . venv-deploy/bin/activate
                    python3 -m pip install --upgrade pip
                    python3 -m pip install opera[openstack]==0.6.4 docker
                    ansible-galaxy install geerlingguy.pip,2.0.0 --force
                    ansible-galaxy install geerlingguy.docker,3.0.0 --force
                    ansible-galaxy install geerlingguy.repo-epel,3.0.0 --force
                    rm -r -f xOpera-rest-blueprint/modules/
                    git clone -b 3.2.1 https://github.com/SODALITE-EU/iac-modules.git xOpera-rest-blueprint/modules/
                    cp ${ca_crt_file} xOpera-rest-blueprint/modules/docker/artifacts/ca.crt
                    cp ${ca_crt_file} xOpera-rest-blueprint/modules/misc/tls/artifacts/ca.crt
                    cp ${ca_key_file} xOpera-rest-blueprint/modules/docker/artifacts/ca.key
                    cp ${ca_key_file} xOpera-rest-blueprint/modules/misc/tls/artifacts/ca.key
                   """
            }
        }
        stage('Deploy to openstack for staging') {
            // Only on staging tags
            when {
                allOf {
                    expression{tag "*"}
                    expression{
                        TAG_STAGING == 'true'
                    }
                }
            }
            environment {
                // add env var for this stage only
                vm_name = 'xOpera-dev'
            }
            steps {
                withCredentials([sshUserPrivateKey(credentialsId: 'xOpera_ssh_key', keyFileVariable: 'xOpera_ssh_key_file', usernameVariable: 'xOpera_ssh_username')]) {
                    sh """#!/bin/bash
                        # create input.yaml file from template
                        envsubst < xOpera-rest-blueprint/inputs/input.yaml.tmpl > xOpera-rest-blueprint/input.yaml
                        . venv-deploy/bin/activate
                        cd xOpera-rest-blueprint
                        rm -r -f .opera
                        opera deploy service.yaml -i input.yaml
                       """
                }
            }
        }
        stage('Deploy to openstack for production') {
            // Only on production tags
            when {
                allOf {
                    expression{tag "*"}
                    expression{
                        TAG_PRODUCTION == 'true'
                    }
                }
            }
            environment {
                vm_name = 'xOpera'
            }
            steps {
                withCredentials([sshUserPrivateKey(credentialsId: 'xOpera_ssh_key', keyFileVariable: 'xOpera_ssh_key_file', usernameVariable: 'xOpera_ssh_username')]) {
                    sh """#!/bin/bash
                        envsubst < xOpera-rest-blueprint/inputs/input.yaml.tmpl > xOpera-rest-blueprint/input.yaml
                        . venv-deploy/bin/activate
                        cd xOpera-rest-blueprint
                        rm -r -f .opera
                        opera deploy service.yaml -i input.yaml
                       """
                }
            }
        }

    }
}
