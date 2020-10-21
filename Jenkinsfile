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
       // POSTGRES SETTINGS
       postgres_address = "xopera-postgres"
       postgres_user = credentials('postgres-user')
       postgres_password = credentials('postgres-password')
       postgres_db = "postgres"
       // XOPERA SETTINGS
       verbose_mode = "debug"
       // GIT SETTINGS
       git_type = "gitlab"
       git_url = "https://gitlab.com"
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

       // DOCKER CERTIFICATES
       ca_crt_file = credentials('xopera-ca-crt')
       ca_key_file = credentials('xopera-ca-key')

       // CI-CD vars
       TAG_SEM_VAR = """${bash(
                returnStdout: true,
                script: './env_helper.sh SemVar $BRANCH_NAME'
            )}"""
   }
    stages {
        stage ('Pull repo code from github') {
            steps {
                checkout scm
            }
        }
        stage('print env_vars'){
            steps {
                sh "echo $TAG_SEM_VAR"
                error("Check env vars")

            }

        }
        stage('test xOpera') {
            environment {
            XOPERA_TESTING = "True"
            }
            steps {
                sh  """ #!/bin/bash
                        rm -rf venv
                        python3 -m venv venv-test
                        . venv-test/bin/activate
                        cd REST_API/
                        pip3 install -r requirements.txt
                        cd Implementation/
                        touch *.xml
                        python3 -m pytest --pyargs -s tests --junitxml="results.xml" --cov=./ --cov=./gitCsarDB --cov=./blueprint_converters --cov=./settings  --cov=./service --cov=./util --cov-report xml tests/
                    """
                junit 'REST_API/Implementation/results.xml'
            }
        }
        stage('SonarQube analysis'){
            environment {
            scannerHome = tool 'SonarQubeScanner'
            }
            steps {
                withSonarQubeEnv('SonarCloud') {
                    sh  """ #!/bin/bash
                            cd REST_API/Implementation/
                            ${scannerHome}/bin/sonar-scanner
                        """
                }
            }
        }
        stage('Build xopera-flask') {
            // Staging on every Semantic version compliant tag
            when {
                allOf {
                    expression{tag "*"}
                    expression{env.BRANCH_NAME =~ /^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$/}
                }
             }
            steps {
                sh """#!/bin/bash
                    cd REST_API
                    ../make_docker.sh build xopera-flask Dockerfile-flask
                    """
            }
        }
        stage('Build xopera-nginx') {
            // Staging on every Semantic version compliant tag
            when {
                allOf {
                    expression{tag "*"}
                    expression{env.BRANCH_NAME =~ /^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$/}
                }
            }
            steps {
                sh """#!/bin/bash
                    cd REST_API
                    ../make_docker.sh build xopera-nginx Dockerfile-nginx
                    """
            }
        }
        stage('Push xopera-flask to sodalite-private-registry') {
            // Staging on every Semantic version compliant tag
            when {
                allOf {
                    expression{tag "*"}
                    expression{env.BRANCH_NAME =~ /^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$/}
                }
            }
            steps {
                withDockerRegistry(credentialsId: 'jenkins-sodalite.docker_token', url: '') {
                    sh  """#!/bin/bash
                            ./make_docker.sh push xopera-flask staging
                        """
                }
            }
        }
        stage('Push xopera-nginx to sodalite-private-registry') {
            // Staging on every Semantic version compliant tag
            when {
                allOf {
                    expression{tag "*"}
                    expression{env.BRANCH_NAME =~ /^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$/}
                }
            }
            steps {
                withDockerRegistry(credentialsId: 'jenkins-sodalite.docker_token', url: '') {
                    sh  """#!/bin/bash
                            ./make_docker.sh push xopera-nginx staging
                        """
                }
            }
        }
        stage('Push xopera-flask to DockerHub') {
            // Only on production tags (MAJOR.MINOR.PATCH)
            when {
                allOf {
                    expression{tag "*"}
                    expression{env.BRANCH_NAME =~ /^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$/}
                }
            }
            steps {
                withDockerRegistry(credentialsId: 'jenkins-sodalite.docker_token', url: '') {
                    sh  """#!/bin/bash
                            ./make_docker.sh push xopera-flask production
                        """
                }
            }
        }
        stage('Push xopera-nginx to DockerHub') {
            // Only on production tags (MAJOR.MINOR.PATCH)
            when {
                allOf {
                    expression{tag "*"}
                    expression{env.BRANCH_NAME =~ /^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$/}
                }
            }
            steps {
                withDockerRegistry(credentialsId: 'jenkins-sodalite.docker_token', url: '') {
                    sh  """#!/bin/bash
                            ./make_docker.sh push xopera-nginx production
                        """
                }
            }
        }
        stage('Install deploy dependencies') {
            // Only for production versions
            when {
                allOf {
                    expression{tag "*"}
                    expression{env.BRANCH_NAME =~ /^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$/}
                }
            }
            steps {
                sh """#!/bin/bash
                    python3 -m venv venv-deploy
                    . venv-deploy/bin/activate
                    python3 -m pip install --upgrade pip
                    python3 -m pip install 'opera[openstack]==0.5.7' docker
                    ansible-galaxy install -r REST_API/requirements.yml
                   """
            }
        }
        stage('Deploy to openstack') {
            // Only for production versions
            when {
                allOf {
                    expression{tag "*"}
                    expression{env.BRANCH_NAME =~ /^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$/}
                }
            }
            steps {
                withCredentials([sshUserPrivateKey(credentialsId: 'xOpera_ssh_key', keyFileVariable: 'xOpera_ssh_key_file', usernameVariable: 'xOpera_ssh_username')]) {
                    // BUILD THE INPUTS FILE
                    sh """\
                    echo "# OPENSTACK SETTINGS
                    ssh-key-name: ${ssh_key_name}
                    image-name: ${image_name}
                    openstack-network-name: ${network_name}
                    security-groups: ${security_groups}
                    flavor-name: ${flavor_name}
                    identity_file: ${xOpera_ssh_key_file}
                    # DOCKER SETTINGS
                    docker-network: ${docker_network}
                    dockerhub-user: ${dockerhub_user}
                    dockerhub-pass: ${dockerhub_pass}
                    docker-public-registry-url: ${docker_public_registry_url}
                    docker-private-registry-url: ${docker_registry_ip}
                    docker-registry-cert-country-name: ${docker_registry_cert_country_name}
                    docker-registry-cert-organization-name: ${docker_registry_cert_organization_name}
                    docker-registry-cert-email-address: ${docker_registry_cert_email_address}
                    docker_ca_crt: ${ca_crt_file}
                    docker_ca_key: ${ca_key_file}
                    # POSTGRES SETTINGS
                    postgres_env:
                      postgres_user: ${postgres_user}
                      postgres_password: ${postgres_password}
                      postgres_db: ${postgres_db}
                    # XOPERA SETTINGS
                    xopera_env:
                      XOPERA_VERBOSE_MODE: ${verbose_mode}
                      # XOPERA GIT SETTINGS
                      XOPERA_GIT_TYPE: ${git_type}
                      XOPERA_GIT_URL: https://gitlab.com
                      XOPERA_GIT_AUTH_TOKEN: ${git_auth_token}
                      # XOPERA POSTGRES CONNECTION
                      XOPERA_DATABASE_IP: ${postgres_address}
                      XOPERA_DATABASE_NAME: ${postgres_db}
                      XOPERA_DATABASE_USER: ${postgres_user}
                      XOPERA_DATABASE_PASSWORD: ${postgres_password}
                      # OPENSTACK DEPLOYMENT FALLBACK SETTINGS
                      OS_PROJECT_DOMAIN_NAME: ${OS_PROJECT_DOMAIN_NAME}
                      OS_USER_DOMAIN_NAME: ${OS_USER_DOMAIN_NAME}
                      OS_PROJECT_NAME: ${OS_PROJECT_NAME}
                      OS_TENANT_NAME: ${OS_TENANT_NAME}
                      OS_USERNAME: ${OS_USERNAME}
                      OS_PASSWORD: ${OS_PASSWORD}
                      OS_AUTH_URL: ${OS_AUTH_URL}
                      OS_INTERFACE: ${OS_INTERFACE}
                      OS_IDENTITY_API_VERSION: \\"${OS_IDENTITY_API_VERSION}\\"
                      OS_REGION_NAME: ${OS_REGION_NAME}
                      OS_AUTH_PLUGIN: ${OS_AUTH_PLUGIN}" >> xOpera-rest-blueprint/input.yaml
                    """.stripIndent()
                    // PRINT THE INPUT YAML FILE
                    sh 'cat xOpera-rest-blueprint/input.yaml'
                    // DEPLOY XOPERA REST API
                    sh ". venv-deploy/bin/activate; cd xOpera-rest-blueprint; rm -r -f .opera; opera deploy service.yaml -i input.yaml"
                }
            }
        }

    }
}
