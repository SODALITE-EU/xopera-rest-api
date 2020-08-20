pipeline {
    agent { label 'docker-slave' }
       environment {
       // OPENSTACK SETTINGS
       ssh_key_name = "jenkins-opera"
       image_name = "centos7"
       network_name = "orchestrator-network"
       security_groups = "default,sodalite-remote-access,sodalite-rest"
       flavor_name = "m1.medium"
       // DOCKER SETTINGS
       docker_network = "sodalite"
       dockerhub_user = ""
       dockerhub_pass = ""
       docker_registry_ip = credentials('jenkins-docker-registry-ip')
       docker_registry_cert_country_name = "SI"
       docker_registry_cert_organization_name = "XLAB"
       docker_registry_cert_email_address = ""
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
                    sh 'truncate -s 0 xOpera-rest-blueprint/input.yaml'
                    // OPENSTACK SETTINGS
                    sh 'echo "# OPENSTACK SETTINGS" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "ssh-key-name: ${ssh_key_name}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "image-name: ${image_name}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "openstack-network-name: ${network_name}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "security-groups: ${security_groups}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "flavor-name: ${flavor_name}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "identity_file: ${xOpera_ssh_key_file}" >> xOpera-rest-blueprint/input.yaml'
                    // DOCKER SETTINGS
                    sh 'echo "# DOCKER SETTINGS" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "docker-network: ${docker_network}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "dockerhub-user: ${dockerhub_user}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "dockerhub-pass: ${dockerhub_pass}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "docker-public-registry-url: ${docker_public_registry_url}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "docker-private-registry-url: ${docker_registry_ip}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "docker-registry-cert-country-name: ${docker_registry_cert_country_name}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "docker-registry-cert-organization-name: ${docker_registry_cert_organization_name}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "docker-registry-cert-email-address: ${docker_registry_cert_email_address}" >> xOpera-rest-blueprint/input.yaml'
                    // POSTGRES SETTINGS
                    sh 'echo "# POSTGRES SETTINGS" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "postgres_env:" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  postgres_user: ${postgres_user}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  postgres_password: ${postgres_password}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  postgres_db: ${postgres_db}" >> xOpera-rest-blueprint/input.yaml'
                    // XOPERA SETTINGS
                    sh 'echo # XOPERA SETTINGS" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "xopera_env:" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  XOPERA_VERBOSE_MODE: ${verbose_mode}" >> xOpera-rest-blueprint/input.yaml'
                    // XOPERA GIT SETTINGS
                    sh 'echo "  # XOPERA GIT SETTINGS" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  XOPERA_GIT_TYPE: ${git_type}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  XOPERA_GIT_URL: https://gitlab.com" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  XOPERA_GIT_AUTH_TOKEN: ${git_auth_token}" >> xOpera-rest-blueprint/input.yaml'
                    // XOPERA POSTGRES CONNECTION
                    sh 'echo "  # XOPERA POSTGRES CONNECTION" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  XOPERA_DATABASE_IP: ${postgres_address}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  XOPERA_DATABASE_NAME: ${postgres_db}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  XOPERA_DATABASE_USER: ${postgres_user}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  XOPERA_DATABASE_PASSWORD: ${postgres_password}" >> xOpera-rest-blueprint/input.yaml'
                    // OPENSTACK DEPLOYMENT FALLBACK SETTINGS
                    sh 'echo "  # OPENSTACK DEPLOYMENT FALLBACK SETTINGS" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  OS_PROJECT_DOMAIN_NAME: ${OS_PROJECT_DOMAIN_NAME}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  OS_USER_DOMAIN_NAME: ${OS_USER_DOMAIN_NAME}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  OS_PROJECT_NAME: ${OS_PROJECT_NAME}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  OS_TENANT_NAME: ${OS_TENANT_NAME}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  OS_USERNAME: ${OS_USERNAME}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  OS_PASSWORD: ${OS_PASSWORD}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  OS_AUTH_URL: ${OS_AUTH_URL}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  OS_INTERFACE: ${OS_INTERFACE}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  OS_IDENTITY_API_VERSION: ${OS_IDENTITY_API_VERSION}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  OS_REGION_NAME: ${OS_REGION_NAME}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "  OS_AUTH_PLUGIN: ${OS_AUTH_PLUGIN}" >> xOpera-rest-blueprint/input.yaml'
                    // PRINT THE INPUT YAML FILE
                    sh 'cat xOpera-rest-blueprint/input.yaml'
                    // COPY DOCKER CERTIFICATES
                    sh 'cp ${ca_crt_file} xOpera-rest-blueprint/modules/docker/artifacts/'
                    sh 'cp ${ca_key_file} xOpera-rest-blueprint/modules/docker/artifacts/'
                    // DEPLOY XOPERA REST API
                    sh ". venv/bin/activate; cd xOpera-rest-blueprint; opera deploy -i input.yaml xopera service.yaml"
                }
            }
        }
    }
}