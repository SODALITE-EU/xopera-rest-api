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
   }
    stages {
        stage ('Pull repo code from github') {
            steps {
                checkout scm
            }
        }
        stage('test xOpera') {
            environment {
            XOPERA_TESTING = "True"
            }
            steps {
                sh  """ #!/bin/bash                         
                        rm -f sonar-project.properties
                        ls -l
                        virtualenv venv
                        . venv/bin/activate
                        cd REST_API/
                        pip3 install -r requirements.txt
                        cd Implementation/
                        touch *.xml
                        python3 -m pytest --pyargs -s tests --junitxml="results.xml" --cov=gitCsarDB --cov=blueprint_converters --cov=settings  --cov=service --cov=util --cov-report xml tests/
                    """
                junit 'results.xml'
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
        stage('Build and push xopera-flask') {
            when { tag "*" }
            steps {
                sh "cd REST_API; docker build -t xopera-flask -f Dockerfile-flask ."
                sh "docker tag xopera-flask $docker_registry_ip/xopera-flask"
                sh "docker push $docker_registry_ip/xopera-flask"
            }
        }
        stage('Build and push xopera-nginx') {
            when { tag "*" }
            steps {
                sh "cd REST_API; docker build -t xopera-nginx -f Dockerfile-nginx ."
                sh "docker tag xopera-nginx $docker_registry_ip/xopera-nginx"
                sh "docker push $docker_registry_ip/xopera-nginx"
            }
        }
        stage('Push xopera-flask to DockerHub') {
            when { tag "*" }
            steps {
                withDockerRegistry(credentialsId: 'jenkins-sodalite.docker_token', url: '') {
                    sh  """#!/bin/bash
                            docker tag xopera-flask sodaliteh2020/xopera-flask
                            git fetch --tags
                            ./make_docker.sh push sodaliteh2020/xopera-flask
                        """
                }
            }
        }
        stage('Push xopera-nginx to DockerHub') {
            when { tag "*" }
            steps {
                withDockerRegistry(credentialsId: 'jenkins-sodalite.docker_token', url: '') {
                    sh  """#!/bin/bash
                            docker tag xopera-nginx sodaliteh2020/xopera-nginx
                            git fetch --tags
                            ./make_docker.sh push sodaliteh2020/xopera-nginx
                        """
                }
            }
        }
        stage('Install dependencies') {
            when { tag "*" }
            steps {
                sh "virtualenv venv"
                sh ". venv/bin/activate; python -m pip install -U 'opera[openstack]==0.5.7'"
                sh ". venv/bin/activate; python -m pip install docker"
                sh ". venv/bin/activate; ansible-galaxy install -r REST_API/requirements.yml"
            }
        }
        stage('Deploy to openstack') {
            when { tag "*" }
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
                    sh ". venv/bin/activate; cd xOpera-rest-blueprint; rm -r -f .opera; opera deploy service.yaml -i input.yaml"
                }
            }
        }
    }
}
