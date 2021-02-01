# xopera-rest-api
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=SODALITE-EU_xopera-rest-api&metric=alert_status)](https://sonarcloud.io/dashboard?id=SODALITE-EU_xopera-rest-api)

Implementation of the xOpera orchestrator REST API

## Prerequisites
    
    - Ubuntu 20.04 or newer
    - Python 3.8.5 with pip 21 or newer
    - Docker engine 20.10 or newer

### GIT backend server (optional, recommended)
xOpera REST API uses git backend to store blueprints. It supports github.com and gitlab (both gitlab.com and private gitlab based servers).
If GIT server is not set it uses computer's filesystem to store git repos.

To connect REST API to github.com:
 - github.com user with enough private repository is needed. Every blueprint will be saved to its own repository,
  so unlimited account with private repositories is recommended.
 - obtain [github access token](https://github.com/settings/tokens) with repo end delete_repo permissions
 - export following environmental variables:
    - XOPERA_GIT_TYPE=github
    - XOPERA_GIT_AUTH_TOKEN=[your_github_access_token]
 - optionally set some of [optional git config settings](#Optional-git-configuration-settings)
    
To connect REST API to gitlab server:
 - obtain [Gitlab's Personal Access Token](https://xxx.xx/profile/personal_access_tokens) with api scope
 - export following environmental variables:
    - XOPERA_GIT_TYPE=gitlab
    - XOPERA_GIT_URL=[url_to_your_gitlab_server]
    - XOPERA_GIT_AUTH_TOKEN=[your_personal_access_token]
 - optionally set some of [optional git config settings](#Optional-git-configuration-settings)

 If non of options above is available, xOpera REST API can use its internal filesystem as git server (MockConnector).
 This option has a big limitation of not enabling users to inspect blueprints as on github.com, gitlab.com or any other gitlab server.
 To connect REST API with MockConnector to internal filesystem:
 - export following environmental variables:
    - XOPERA_GIT_TYPE=mock
 - optionally set some of [optional git config settings](#Optional-git-configuration-settings)

 Note: Mock connector is default option which is used in case of missing XOPERA_GIT_TYPE environmental variable.


#### Optional git configuration settings
Beside obligatory settings following settings can be configured:
 - XOPERA_GIT_WORKDIR - workdir for git on REST API server
 - XOPERA_GIT_REPO_PREFIX (default: `gitDB_`) - repo prefix. Blueprint with token `963d7c94-34f9-498d-b122-472dbd9a8681` would be saved to repository `gitDB_963d7c94-34f9-498d-b122-472dbd9a8681`
 - XOPERA_GIT_COMMIT_NAME (default: `SODALITE-xOpera-REST-API`) - user.name to author git commit
 - XOPERA_GIT_COMMIT_MAIL (default: `no-email@domain.com`) - user.mail to author git commit
 - XOPERA_GIT_GUEST_PERMISSIONS (default: `reporter`) - role, assigned to user, added to repository. See [access to blueprints](#ACCESS-TO-REPOSITORY-WITH-BLUEPRINTS).

See [example config](src/opera/api/settings/example_settings.sh) for example on how to export variables.
### PostgreSQL (optional, recommended)
Rest API is using PostgreSQL database for saving bluepints and deployment logs.
If PostgreSQL database is not available, it uses computer's filesystem.

To connect REST API, config must be exported as series of environmental variables:
- XOPERA_DATABASE_IP=[database_ip]
- XOPERA_DATABASE_PORT=[database_port]
- XOPERA_DATABASE_NAME=[database_name]
- XOPERA_DATABASE_USER=[database_username]
- XOPERA_DATABASE_PASSWORD=[database_password]
- XOPERA_DATABASE_TIMEOUT=[database_timeout], optional
- XOPERA_DATABASE_LOG_TABLE=[table_name_for_logs], optional

See [example config](src/opera/api/settings/example_settings.sh).

PostgreSQL can be also run as [docker container](#PostgreSQL-docker)

### Docker registry (optional, recommended)
In most applications, REST API needs docker registry to store docker images.
It can be run [locally](#Local-docker-registry) or [remotely](#Connect-to-remote-registry).
See [docker docs](https://docs.docker.com/engine/security/certificates/) for more details.
Certificates 

## Installation
    
### SSH keys
xOpera needs SSH key pair with `xOpera` substring in name in `/root/.ssh` dir. It can be generated using

    sudo ./Installation/ssh_keys.sh [common name]

where common name is desired name for SSH key (usually computer's IP).

## Quick start

### Local run
To run locally, use [docker compose](docker-compose.yml) or [local TOSCA template](xOpera-rest-blueprint/service-local.yaml) with compliant orchestrator.

### Remote deploy
REST API can be deployed remotely using [TOSCA template](xOpera-rest-blueprint/service.yaml) with compliant orchestrator, for instance [xOpera](https://github.com/xlab-si/xopera-opera).

## API
Check [openapi spec](openapi-spec.yml).

## How to use API
Standard scenarios of using REST api:

### FIRST RUN
- GET key pair via ssh/keys/public download and register it on your OpenStack

### MANAGE
- upload blueprint with POST to /manage
    - new version of existing one must be POSTed to /manage/{blueprint_token}
    - save blueprint_metadata, returned by API call -> it is the only way of accessing your blueprint afterwards

- delete entire blueprint with DELETE to /manage/{blueprint_token}
    - if version_tag is specified, only this version will be deleted
    - use force, if necessary

#### ACCESS TO REPOSITORY WITH BLUEPRINTS
- xOpera REST API uses git backend for storing blueprints
- to obtain access, POST to /manage/<blueprint_token>/user endpoint username
    - invitation for user with username will be sent to its email address (github.com)
    - user will be added to repository (gitlab)
- with GET to /manage/<blueprint_token>/user user_list can be obtained

### VALIDATE
- TOSCA syntax can be validated with POST to /validate/{blueprint_token}
    - if version_tag is specified, specific version will be inspected, otherwise the last one
    - optionally, inputs file to be used with template must also be uploaded within same API call

### FIRST DEPLOY (deploy/fresh/)
- deploy last version of blueprint with POST to /deploy/fresh/{blueprint_token}
    - optionally, `inputs_file` to be used with template must also be uploaded within same API call
    - another version can be specified by `version_tag` parameter
    - Number of parallel workers can be specified with `workers` parameter
    - save `session_token`

- using `session_token` with GET to /info/status check status and logs of your job
- After completion, check logs with GET to /info/log (deprecated, will be removed soon)

### DEPLOY CONTINUE
If job was interrupted, it can be continued (possibly with new inputs)
- continue with interrupted deploy job with POST to /deploy/{session_token}
    - by default, this option will resume deployment, but it can also start over `(resume=false)`
    - Number of parallel workers can be specified with `workers` parameter
- A new session_token will be assigned to job (old will be returned as `session_token_old`)
- using `session_token` with GET to /info/status check status and logs of your job

### UNDEPLOY
- undeploy blueprint with POST to /undeploy/{blueprint_token}
    - optionally, inputs file to be used with template must also be uploaded within same API call
    - optionally also in combination with version_tag
    - save session_token
- using status_token with GET to /info/status check status of your job
- After completion, check logs with GET to /info/log

### OUTPUTS
If TOSCA service template specified outputs, they can be obtained with GET to /outputs/{session_token}

### DIFF
Diff calculates instance difference between Deployed instance model (accessable via `session_token`) and  
New blueprint version (`blueprint_token` with `version_tag` and `inputs_file`)

### UPDATE
- Update deployes new instance model (DI2), which is diff between Deployed instance model, referenced by `session_token` 
(DI1) and New blueprint (referenced by `blueprint_token` and `version_tag`) with inputs (`inputs_file`).
    - Number of parallel workers can be specified with `workers` parameter
    - save `session_token`
- using status_token with GET to /info/status check status of your job
- After completion, check logs with GET to /info/log
                    
### GIT LOGS
- Last transaction details for gitCsarDB can be inspected using /info/log/git/{blueprint_token} endpoint.
    - optionally, logs inspection can be further specified with version_tag
    - if all=True, all logs that satisfy blueprint_token and version_tag conditions will be returned

## TOSCA 1.3 Cloud Service Archive (CSAR) format

xOpera REST API uses CSAR format as input format for uploading blueprints to REST API server.

### Converting blueprint to CSAR

Blueprint can be transformed to CSAR format with [blueprint2CSAR script](src/opera/api/blueprint_converters/blueprint2CSAR.py).
Check help:

    python3 scripts/blueprint2CSAR.py --help

[blueprint2CSAR](src/opera/api/blueprint_converters/blueprint2CSAR.py) can also be used as python library to be included to your python application.

### Structure of CSAR format  
For details about CSAR format structure, visit [TOSCA Simple Profile in YAML Version 1.3](https://docs.oasis-open.org/tosca/TOSCA-Simple-Profile-YAML/v1.3/os/TOSCA-Simple-Profile-YAML-v1.3-os.html#_Toc26969474)

## Setting up OpenStack
### Setting the default user
When deploying the xOpera Rest API, intended to target Openstack, make sure to pass correct environment variables for 
openstack orchestration (section `# XOPERA OPENSTACK DEPLOYMENT FALLBACK SETTINGS` in `xopera_env` field in 
[inputs-local.yaml](xOpera-rest-blueprint/inputs/input-local.yaml) or [inputs-openstack.yaml](xOpera-rest-blueprint/inputs/input-openstack.yaml))
 
## Docker registry connection
### Local docker registry
To run docker image registry locally, run the following command:

    docker run -d --restart=always --name registry -v /mnt/registry:/var/lib/registry registry:2

### Connect to remote registry

#### Installation with script (Ubuntu only)   
If you are using ubuntu, just run the following script:

    sudo ./Installation/docker_certs.sh [computer_IP] [registry_IP] [path_to_CA_dir]
   
#### Manual installation (Ubuntu or CentOS) 
If you choose to preform steps manually, follow the steps below:
* Ubuntu: add root certificate `ca.crt` to `/usr/share/ca-certificates/` folder, add the filename `ca.crt` to `/etc/ca-certificates.conf` and run `sudo update-ca-certificates` to update certificates.
* CentOS: add root certificate `ca.crt` to `/etc/pki/ca-trust/source/anchors/` folder and run `sudo update-ca-trust` to update certificates.
 
Generate client cert and key, get it signed using docker registry's root CA certificate.

Now create a new directory in the docker certificate folder (`/etc/docker/certs.d/`) that has the same name as the IP/domain of your docker registry.
Afterwards, copy the docker registry's `ca.crt` to newly created folder. You also need to copy client certificate and private key you generated and got signed.

The file structure should be as follows:

    /etc/docker/certs.d/
    └── my_registry_ip
       ├── client.cert
       ├── client.key
       └── ca.crt

See [docker docs](https://docs.docker.com/engine/security/certificates/) for more details.
