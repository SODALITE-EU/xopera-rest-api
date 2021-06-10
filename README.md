# xopera-rest-api
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=SODALITE-EU_xopera-rest-api&metric=alert_status)](https://sonarcloud.io/dashboard?id=SODALITE-EU_xopera-rest-api)

Implementation of the xOpera orchestrator REST API

## Prerequisites

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

### Docker registry (optional, recommended)
In most applications, REST API needs docker registry to store docker images.
It can be run [locally](#Local-docker-registry) or [remotely](#Connect-to-remote-registry).
See [docker docs](https://docs.docker.com/engine/security/certificates/) for more details.

### OAuth
xOpera REST API uses OAuth 2.0 for authentication.

It can be overridden by setting `AUTH_API_KEY` env var in xopera-rest-api
container to key_name of choice. 
This key must be added to requests as `-H  "X-API-Key: [key_name]"`
    
### SSH keys
xOpera needs SSH key pair with `xOpera` substring in name in `/root/.ssh` (or other) dir. It can be generated using

    sudo ./Installation/ssh_keys.sh [common name] [SSH_DIR | default='/root/.ssh'] 

where common name is desired name for SSH key (usually computer's IP).

## Usage

### Local run
To run locally, use [docker compose](docker-compose.yml) or [local TOSCA template](xOpera-rest-blueprint/service-local.yaml) with compliant orchestrator.

### Remote deploy
REST API can be deployed remotely using [TOSCA template](xOpera-rest-blueprint/service.yaml) with compliant orchestrator, for instance [xOpera](https://github.com/xlab-si/xopera-opera).

## API
Check [openapi spec](openapi-spec.yml) and [sample api requests](api-calls.http).

## How to use API
Standard scenarios of using REST api:

### SSH management
xOpera uses SSH key to connect to instance VMs. Its public key can be obtained with GET to `/ssh/keys/public`. Public 
key must be registered with cloud provider (e.g. OpenStack).

### Blueprint management
Blueprint consist of TOSCA service template with all corresponding artifacts, neatly packed into [The TOSCA Cloud 
Service Archive (CSAR)](https://docs.oasis-open.org/tosca/TOSCA-Simple-Profile-YAML/v1.3/os/TOSCA-Simple-Profile-YAML-v1.3-os.html#_Toc26969474).
xOpera REST API leverages GIT server (it supports Github and Gitlab at the moment) for storing CSARs. 
#### Upload a new blueprint
A new blueprint can be uploaded with POST to `/blueprint`. `CSAR` must be a valid TOSCA CSAR archive (in zip format). 
Optionally, user can add several other parameters:
- `revision_msg` --> commit message for git
- `blueprint_name` --> human-readable blueprint_name
- `aadm_id` --> End-to-end debugging id
- `username` --> User's username
- `project_domain` --> domain of blueprint
 
If successful, response in form of BlueprintVersion schema that will include `blueprint_id` and `version_id`, which can later
 be used for accessing blueprint (version).
 
#### Get list of blueprints
This endpoint allows querying blueprints by `username`, `project_domain` or both. It returns `[Blueprint]` where 
Blueprint consist of (`blueprint_id`, `project_domain`, `username`, `timestamp`)

#### Upload a new blueprint version
A new version can be added to existing blueprint with POST to `/blueprint/{blueprint_id}`. `CSAR` must be a valid TOSCA
CSAR archive (in zip format). Optionally, user can add `revision_msg`, or specify `project_domain` for blueprint. 
If successful, response in form of BlueprintVersion schema will include `blueprint_id` and `version_id`, which can 
later be used for accessing blueprint (version).

#### Delete a blueprint
Blueprint can be deleted with DELETE to `/blueprint/{blueprint_id}`. Before deleting, REST API will check if blueprint
 is a part of any existing deployment and block deletion. This behaviour can be overridden with `force=true` parameter.
 
#### Delete a blueprint version
Blueprint version can be deleted with DELETE to `/blueprint/{blueprint_id}/version/{version_id}`. Before deleting, 
REST API will check if blueprint version is a part of any existing deployment and block deletion. This behaviour can 
be overridden with `force=true` parameter.

#### Obtain list of blueprint users
List of git users with access to Repository with blueprint can be obtained with GET to `/blueprint/{blueprint_id}/user`.

#### Add user to blueprint
Git (Github or Gitlab) user can be added to blueprint with POST to `/blueprint/{blueprint_id}/user/{user_id}`. User will
be assigned developer access and will be able to modify blueprint.

#### Remove user from blueprint
Git user can be removed with POST to `/blueprint/{blueprint_id}/user/{user_id}`.

### Blueprint metadata management
#### Obtain blueprint metadata
Blueprint metadata from the most recent version of blueprint can be obtained with GET 
to `/blueprint/{blueprint_id}/meta`. Metadata consist of:
- `blueprint_id`
- `version_id`
- `name`
- `project_domain`
- `timestamp`
- `url`
- `commit_sha`
- `users`
- `deployments`

#### Obtain blueprint metadata from specific version
Blueprint metadata from specific version of blueprint can be obtained with GET to 
`/blueprint/{blueprint_id}/version/{version_id}/meta`. Endpoint returns the same fields as `/blueprint/{blueprint_id}/meta`.
Note that some parameters are blueprint-version-specific (every version can have its own values) and some are not
 (every version of single blueprint has the same values).

Version-specific metadata: 
- `version_id`
- `timestamp`
- `commit_sha`

#### Obtain blueprint name
Although blueprint name is part of [blueprint meta](#obtain-blueprint-metadata) it can also be obtained via dedicated 
endpoint with GET to `/blueprint/{blueprint_id}/name`.

#### Updating blueprint name
Blueprint name is usually set upon blueprint creation (POST to `/blueprint`), but it can also be changed later, with 
POST to `/blueprint/{blueprint_id}/name`.

### Obtaining list of deployments
List of deployments, created from current blueprint can be obtained with GET to `/blueprint/{blueprint_id}/deployments`.
Every list item consist of:
- `deployment_id`
- `state`
- `operation`
- `timestamp`

List of deployments is part of blueprint metadata and can also be obtained via 
[metadata endpoint](#obtain-blueprint-metadata).

#### Get history of blueprint changes
History of changes, made by xOpera REST API to git repository with blueprint, can be obtained with GET to
`/blueprint/{blueprint_id}/git_history`. Changes can be either `update` (addition of blueprint version) or `delete` 
(deletion of blueprint or blueprint version).

### Blueprint validation

#### Validate blueprint
Blueprint from database can be validated with PUT to `/blueprint/{blueprint_id}/validate`. Optionally, file with inputs
can be added. If blueprint has multiple versions, the last will be validated.

#### Validate specific version of blueprint
Blueprint version from database can be validated with PUT to `/blueprint/{blueprint_id}/version/{version_id}/validate`.
Optionally, file with inputs can be added.

#### Validate new blueprint
Any blueprint in The TOSCA Cloud Service Archive (CSAR) form can be validate with PUT to `/blueprint/validate`.
After validation, blueprint will be discarded.

### Deployment management
Deployment is xOpera REST API's internal representation of current instance state, deployed on cloud platform

<!---
#### Check deployment exists (not implemented)
If deployment, instantiated from blueprint with inputs already exists, can be checked with PUT to `/deployment/exists`.
If `version_id` is not specified, last version is used. Inputs are optional, depending on blueprint.
-->

#### Initialize and deploy
To initialize deployment with first deploy, user can POST to `/deployment/deploy`. If `version_id` is not specified, 
last version is used. Inputs are optional, depending on blueprint. `Workers` is a maximum number of concurrent workers, 
leveraged by xOpera. `deployment_label` is a human-readable label, which can be given to deployment.In case of a 
successful invocation, REST API returns Invocation schema, with `deployment_id` params, which must be used for any 
further interactions with current deployment.

#### Obtain deployment status
Status of deployment can be obtained with GET to `/deployment/{deployment_id}/status`. State of deployment can be one of
`[ pending, in_progress, success, failed ]`. After invocation is done, user can inspect `stdout`, `stderr`, 
`instance_state` and `outputs` (if defined within service template).

#### Inspect deployment history
Entire history of deployment (list of all invocations) can be obtained with GET to `/deployment/{deployment_id}/history`.

#### Continue deploy
In case of deployment failure, deploy invocation can be continued (optionally with new inputs) with POST to
`/deployment/{deployment_id}/deploy_continue`. Opera will continue, where previous deploy failed. Optionally, it can
also start from beginning (`clean_state=True`).

#### Calculate diff
Diff between current deployment state and new blueprint (with inputs) can be obtained by PUT to
`/deployment/{deployment_id}/diff`. Blueprint (version) can be another version of the previously used blueprint or
some version of another blueprint.

#### Update deployment
Deployment can be updated from new blueprint (version) with POST to `/deployment/{deployment_id}/update`. Opera will 
calculate the difference between deployed instance and new blueprint and (un)deploy it. Blueprint (version) can be 
another version of the previously used blueprint or some version of another blueprint.

#### Undeploy
Deployment can be undeployed with POST to `/deployment/{deployment_id}/undeploy`. This is the last invocation in 
deployment lifecycle, and antoher invocation will not be possible, but logs will be preserved.

## TOSCA 1.3 Cloud Service Archive (CSAR) format

xOpera REST API uses CSAR format as input format for uploading blueprints to REST API server.

### Converting blueprint to CSAR

Blueprint can be transformed to CSAR format with [blueprint2CSAR script](src/opera/api/blueprint_converters/blueprint2CSAR.py).
Check help:

    python3 scripts/blueprint2CSAR.py --help

[blueprint2CSAR](src/opera/api/blueprint_converters/blueprint2CSAR.py) can also be used as python library to be included to your python application.

### Structure of CSAR format  
For details about CSAR format structure, visit [TOSCA Simple Profile in YAML Version 1.3](https://docs.oasis-open.org/tosca/TOSCA-Simple-Profile-YAML/v1.3/os/TOSCA-Simple-Profile-YAML-v1.3-os.html#_Toc26969474)

## Additional configuration
### Setting up OpenStack
#### Setting the default user
When deploying the xOpera Rest API, intended to target Openstack, make sure to pass correct environment variables for 
openstack orchestration (section `# XOPERA OPENSTACK DEPLOYMENT FALLBACK SETTINGS` in `xopera_env` field in 
[inputs-local.yaml](xOpera-rest-blueprint/inputs/input-local.yaml) or [inputs-openstack.yaml](xOpera-rest-blueprint/inputs/input-openstack.yaml))
 
### Docker registry connection
#### Local docker registry
To run docker image registry locally, run the following command:

    docker run -d --restart=always --name registry -v /mnt/registry:/var/lib/registry registry:2

#### Connect to remote registry

##### Installation with script (Ubuntu only)   
If you are using ubuntu, just run the following script:

    sudo ./Installation/docker_certs.sh [computer_IP] [registry_IP] [path_to_CA_dir]
   
##### Manual installation (Ubuntu or CentOS) 
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

### PostgreSQL connection
Rest API is using PostgreSQL database. It is deployed with REST API as part of docker-compose template and TOSCA template.
REST API can be configured to connect to any PostgreSQL instance by following environmental variables:
- XOPERA_DATABASE_IP=[database_ip]
- XOPERA_DATABASE_PORT=[database_port]
- XOPERA_DATABASE_NAME=[database_name]
- XOPERA_DATABASE_USER=[database_username]
- XOPERA_DATABASE_PASSWORD=[database_password]
- XOPERA_DATABASE_TIMEOUT=[database_timeout], optional

See [example config](src/opera/api/settings/example_settings.sh).

PostgreSQL can be run as [docker container](https://hub.docker.com/_/postgres).