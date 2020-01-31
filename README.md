# xopera-rest-api
Implementation of the xOpera orchestrator REST API

## Prerequisites
    
    - Ubuntu 18.04
    - python 3.6 or newer

### PostgreSQL (optional, recommended)
Rest API is using PostgreSQL database for saving bluepints and deployment logs.
If PostgreSQL database is not available, it uses computer's filesystem.

To connect REST API to PostgreSQL database, export DATABASE_IP:
    
    export DATABASE_IP=[you_database_ip]

PostgreSQL can be also run as [docker container](#PostgreSQL-docker)

### Docker registry (optional, recommended)
In most applications, REST API needs docker registry to store docker images.
It can be run [locally](#Local-docker-registry) or [remotely](#Connect-to-remote-registry).
See [docker docs](https://docs.docker.com/engine/security/certificates/) for more details.
If installing with `make`, certificates for remote registry are going to be configured automatically.
    
## Quick start

### Local run

#### Run in venv (optional, recommended)
- Installing: `python3 -m pip install --user virtualenv`
- Creating: `python3 -m venv [venv_name]`
- Activating: `source [venv_name]/bin/activate`


Your python venv must be activated before installation and also before every run.

#### Installation and run

To install, test and run in computer's environment (or venv), simply run:

    make all
    
or run stages separately:

    make clean
    make install
    make build
    make tests
    make run
    
### Run in docker
To install, test and run in docker container, simply run:
    
    make all_docker

or run stages separately:
    
    make clean
    make clean_docker
    make install_docker
    make build
    make tests
    make run_docker

## Manual installation
See [manual installation](#Instructions-for-manual-installation-and-run).

## API
Check [swagger docs](REST_API/Documentation/swagger.json).

## How to use API
Standard scenarios of using REST api:

### FIRST RUN
- GET key pair via ssh/keys/public download and register it on your OpenStack

### DEPLOY
Standard scenarios of using REST api:

- upload blueprint with POST to /manage
    - new version of existing one must be POSTed to /manage/{blueprint_token}
    - save blueprint_metadata, returned by API call -> it is the only way of accessing your blueprint afterwards
- deploy last version of blueprint with POST to /deploy/{blueprint_token}
    - optionally, inputs file to be used with template must also be uploaded within same API call
    - another version can be specified by version_id or timestamp
    - save session_token

- using status_token from with GET to /info/status check status of your job
- After completion, check logs with GET to /info/log

### UNDEPLOY
- undeploy blueprint with DELETE to /deploy/{blueprint_token}
    - optionally, inputs file to be used with template must also be uploaded within same API call
    - optionally also in combination with version_id or timestamp
    - save session_token
- using status_token with GET to /info/status check status of your job
- After completion, check logs with GET to /info/log
- Delete all versions of blueprint from database with DELETE to /manage/{blueprint_token}
    - to delete just specific version, use version_id or timestamp
    - if deployment from template has not been undeployed yet, blueprint cannot be deleted-> use ‘force’ to override
    
Check [HTTP requests](REST_API/Documentation/requests.http) for exact API calls.




## JSON deployment format

### Converting deployment to JSON

Blueprint can be transformed to JSON format with [blueprint2json script](REST_API/Implementation/scripts/blueprint2json.py).
Check help:
    `python3 scripts/blueprint2json.py --help`

### Structure of JSON deployment format  
    
The general format is structured like shown below:

    {
        "blueprint_id": "ID"
        "tosca_definition": FILE,
        "ansible_definition": DIRECTORY,
        "config_script": FILE,
        "timestamp": "YYYY-MM-DD hh:mm:ss.ssssss"
    }

DIRECTORY is structured like this (NAME is name string):

    {
        "name": "NAME",
        "type": "dir",
        "content": [LIST FILES IN THIS ARRAY]
    }

FILE is structured like this (NAME is name string, CONTENT is URL formatted string):

    {
        "name": "NAME",
        "type": "file",
        "content": "CONTENT"
    }

Check [sample blueprint](REST_API/Documentation/blueprint.json).

### Using xopera-key-name in templates

If template requires installing VM, xopera's key name must be set in template in order for xOpera to be able to connect to VM over SSH and configure VM.

The easiest way is to provide it with  `get_input` command:

    vm:
      type: my.nodes.VM.OpenStack
      properties:
        name: website-nginx-test
        image: centos7
        flavor: m1.medium
        network: orchestrator-net
        security_groups: default,sodalite-xopera-rest,sodalite-remote-access
        key_name: { get_input: xopera-key-name}

If get_input field name is set to `xopera-key-name`, rest api will automatically add it's own key name to inputs.
It can also be configured to custom get_input field name, but in this case, user must provide his own file with inputs.

    curl -X "POST" -F "inputs_file=@path/to/file.yaml" localhost:5000/deploy/567858fc-a1e8-43b4-91f5-cb04ec8be90b
    
See [api calls](REST_API/Documentation/requests.http) for more help.

### Using non default user
xOpera by default uses administrator's credentials (provided during configuration of REST API) to login to Openstack.
If some non default user must be used, his credentials can be submitted wit inputs file, provided to `/deploy` endpoint:

    ...
    OS_USERNAME: [username]
    OS_PASSWORD: [password]
    ...
    
    
## Instructions for manual installation and run

### Installation

#### Ubuntu

The following installation supports Ubuntu 18.04. 
Move to REST_API directory and install packages (requires sudo):
    
    sudo ./require.sh
    
#### Alpine

For alpine, run following commands:

    apk add gcc bash openssh-client python3-dev py-virtualenv linux-headers musl-dev libffi-dev libressl-dev postgresql-dev python3 pip3 ansible
    pip3 install -U wheel "opera[openstack]<0.5" Flask flask_restplus psycopg2 jinja2 docker-py
    ansible-galaxy install -r Implementation/scripts/requirements.yml
    
##### Certificates
Docker needs certificates to run properly. Run the command and provide details, when prompted.
    
    sudo ./certs.sh [COMPUTER_IP] [DOCKER_CONTAINER_IP]

Docker container IPs [DOCKER_CONTAINER_IP] start with 172.17.0.2 (172.17.0.1 is the local computer), so this is probably the one.

##### OpenStack credentials
Go to OpenStack dashboard and navigate to the `Access & Security` -> `API Access` and download RC file (RC FILE v3).
[RC_FILE_PATH] is path to RC file, if file with filename `openrc.sh` is located in same directory as script (`REST_API`), it can be left empty.
When prompted, make sure you provide the following script with correct OpenStack password.
    
    sudo ./open_stack_setup.sh [RC_FILE_PATH] [COMPUTER_IP]

##### Default settings
Default settings are stored in [default_settings.json](REST_API/Implementation/settings/default_settings.json).
### Run
#### Docker run REST API
To run docker with REST_API, simply run:

    sudo ./build_and_run.sh

REST_API by default runs on port 5000. If it is already taken, docker launch will fail, so docker's parameter `-p` in `Impementation/build_and_run.sh` must be changed to `-p 5000:[IP_OF_CHOICE]`

#### Local run REST API
To run REST_API app locally, simply run:

    sudo ./Implementation/run.sh

#### PostgreSQL docker
REST API can run with or without database.
To run PostgreSQL inside docker container, run:
    
    docker run --rm --name postgres-docker -e POSTGRES_PASSWORD=password -d -v $HOME/docker/volumes/postgres:/var/lib/postgresql/data postgres
    
Database's IP can be obtained using following command:

    docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' postgres-docker

#### Local docker registry
To run docker image registry locally, run the following command:

    docker run -d --restart=always --name registry -v /mnt/registry:/var/lib/registry registry:2

#### Connect to remote registry

This is done after you already set the docker registry up using either `docker-registry` or `xopera-full` template and would like to connect to registry from another local machine.

##### Installation with script (Ubuntu only)   
If you are using ubuntu, just run the following script:

    sudo ./local_certs.sh [computer_IP] [registry_IP]
   
##### Manual installation (Ubuntu or CentOS) 
If you choose to preform steps manually, follow the steps below:
* Ubuntu: add root certificate `ca.crt` to `/usr/share/ca-certificates/` folder, add the filename `ca.crt` to `/etc/ca-certificates.conf` and run `sudo update-ca-certificates` to update certificates.
* CentOS: add root certificate `ca.crt` to `/etc/pki/ca-trust/source/anchors/` folder and run `sudo update-ca-trust` to update certificates.
 
Now we want to generate client certificate, signed with root CA to use for your local machine. You can do this by running the following command and replacing the [COMPUTER_IP] with the respective value:

    sudo ./Certs/generate_noprompt.sh [COMPUTER_IP] IP:[COMPUTER_IP] local

Now create a new directory in the docker certificate folder (`/etc/docker/certs.d/`) that has the same name as the IP/domain of your docker registry.
Afterwards, copy the `ca.crt` from `Certs` folder inside the newly created folder. You also need to copy the certificate and private key you generated from the `Certs/local` folder into this folder and change the certificate's extension from `.crt` to `.cert`. This way Docker recognizes which certificates are root CAs and which are client certificates. You can leave the .key file as-is.

The file structure should now look similar to this:

    /etc/docker/certs.d/
    └── my_registry_ip
       ├── client.cert
       ├── client.key
       └── ca.crt

See [docker docs](https://docs.docker.com/engine/security/certificates/) for more details.

### Building Docker Images

#### Build

Some deployments need docker images to deploy services properly(for instance full_test example, that deploys REST API container)

To build the REST API image, run the following command from the `REST_API/` folder:

    sudo ./build_xopera_rest.sh

Command will make `xopera_rest.tar` image in `Builds` dir. The content of this dir will be copied to `home/xopera/build` as part of `run.sh` script so make sure to build images before running REST API, or you can just copy images by yourself. 

To test and start your newly built docker container locally (optionally, not necessary), run the following command:

    docker run -it xopera_rest

