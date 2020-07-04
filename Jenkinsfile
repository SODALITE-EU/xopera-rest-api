pipeline {
    agent { label 'docker-slave' }
       environment {
       docker_registry_ip = credentials('jenkins-docker-registry-ip')
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
       ssh_key_name = "jenkins-opera"
       image_name = "centos7"
       network_name = "orchestrator-network"
       security_groups = "default,sodalite-remote-access,sodalite-rest"
       flavor_name = "m1.medium"
       postgres_user = credentials('postgres-user')
       postgres_password = credentials('postgres-password')
       postgres_db = "postgres"
       git_type = "gitlab"
       git_url = "https://gitlab.com"
       git_auth_token = credentials('git-auth-token')
       verbose_mode = "debug"
       openrc_file = credentials('atos-openrc')
       ansible_vault_file = credentials('ansible-vault')
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
                sh "cp -f $openrc_file REST_API/Implementation/settings/openrc.sh"
                sh "cp -f $ansible_vault_file REST_API/Implementation/settings/vault.yml"
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
                sh ". venv/bin/activate; python -m pip install -U 'opera[openstack]<0.5'"
                sh ". venv/bin/activate; python -m pip install docker"
                sh ". venv/bin/activate; ansible-galaxy install -r REST_API/requirements.yml"
            }
        }
        stage('Deploy to openstack') {
            when { tag "*" }
            steps {
                withCredentials([sshUserPrivateKey(credentialsId: 'xOpera_ssh_key', keyFileVariable: 'xOpera_ssh_key_file', usernameVariable: 'xOpera_ssh_username')]) {
                    sh 'truncate -s 0 xOpera-rest-blueprint/input.yaml'
                    sh 'echo "ssh-key-name: ${ssh_key_name}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "image-name: ${image_name}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "network-name: ${network_name}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "security-groups: ${security_groups}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "flavor-name: ${flavor_name}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "docker-registry-ip: ${docker_registry_ip}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "postgres_user: ${postgres_user}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "postgres_password: ${postgres_password}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "postgres_db: ${postgres_db}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "git_type: ${git_type}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "git_url: https://gitlab.com" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "git_auth_token: ${git_auth_token}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "verbose_mode: ${verbose_mode}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "identity_file: ${xOpera_ssh_key_file}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "ca_crt_location: ${ca_crt_file}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'echo "ca_key_location: ${ca_key_file}" >> xOpera-rest-blueprint/input.yaml'
                    sh 'cat xOpera-rest-blueprint/input.yaml'
                    sh ". venv/bin/activate; cd xOpera-rest-blueprint; opera deploy -i input.yaml xopera service.yaml"
                }
            }
        }
    }
}