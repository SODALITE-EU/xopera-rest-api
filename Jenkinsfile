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

        stage('Build xopera-nginx') {
            // Build on every tag
            when { tag "*" }
            steps {
                sh """#!/bin/bash
                    cd REST_API
                    ../make_docker.sh build xopera-nginx Dockerfile-nginx
                    """
            }
        }

        stage('Push xopera-nginx to sodalite-private-registry') {
            // Staging on every tag
            when { tag "*" }
            steps {
                withDockerRegistry(credentialsId: 'jenkins-sodalite.docker_token', url: '') {
                    sh  """#!/bin/bash
                            ./make_docker.sh push xopera-nginx staging
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

    }
}
