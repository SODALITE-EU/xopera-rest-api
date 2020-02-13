import glob
import json
import logging as log
import os
import subprocess
import uuid
from pathlib import Path

import yaml
from werkzeug.datastructures import FileStorage

from deployment_preparation import deployment_io
from deployment_preparation.dp_types import Deployment, Directory
from deployment_preparation.settings import Settings


def check_status(token: str, format: str = 'short'):
    json_dict = {}
    for file_path in glob.glob("{}{}/*.data".format(Settings.deployment_data, token)):
        file = open(file_path, 'r')
        parsed = json.load(file)
        component_name = os.path.splitext(file_path)[0].split('/')[-1]
        if format == 'long':
            json_dict[component_name] = parsed

        else:
            json_short = parsed['state']
            json_dict[component_name] = json_short
    if "deploy" in json_dict or "undeploy" in json_dict:
        mode = "deploy" if "deploy" in json_dict else "undeploy"
        state = json_dict[mode]['state'] if format == 'long' else json_dict[mode]
        status_code = 201 if state == "done" else 500
    else:
        status_code = 202
    return json_dict, status_code


def save_file(file: FileStorage, base_path: Path):
    path = str(base_path / Path(file.filename))

    file.save(dst=path)
    return path


def deploy_by_token(blueprint_token: str, deployment: Deployment, inputs_file: FileStorage = None):
    try:

        session_token = uuid.uuid4()
        location = deployment_io.generate_data(deployment, session_token)

        logfile_name = Settings.logfile_name
        trash = open("/dev/null", 'w')

        log.info("Orchestrating with xOpera...")

        timestamp_start = Settings.datetime_now_to_string()

        _list = [f'{Settings.implementation_dir}/scripts/deploy.sh', '{}'.format(Path(location).absolute()), deployment.id, logfile_name,
                 str(blueprint_token), str(session_token), timestamp_start, deployment.timestamp]

        inputs_dict = dict()
        inputs_filename = "inputs.yaml"
        if inputs_file:
            inputs_yaml = yaml.safe_load(inputs_file.read().decode('utf-8'))
            inputs_dict = inputs_yaml or dict()
            inputs_filename = inputs_file.filename

        # add / overwrite xopera-key-name
        inputs_dict['xopera-key-name'] = Settings.key_pair

        # extract OS_USERNAME and OS_PASSWORD
        if "OS_USERNAME" in inputs_dict and "OS_PASSWORD" in inputs_dict:
            os_username = inputs_dict["OS_USERNAME"]
            os_password = inputs_dict["OS_PASSWORD"]
            inputs_dict.pop("OS_USERNAME", None)
            inputs_dict.pop("OS_PASSWORD", None)
            deployment_io.replace_username_and_password(f"{location}/openrc.sh", os_username, os_password)

        log.info(f"inputs_file: \n{inputs_dict}")

        with open(f"{location}/{inputs_filename}", 'w') as inputs_file:
            yaml.dump(inputs_dict, inputs_file)
            # print(json.dumps(inputs_dict))

        _list.append(inputs_filename)

        subprocess.Popen(_list)  # , stderr=trash, stdout=trash)
        return session_token

    except Exception:
        log.error('Exception while deploying: ', exc_info=True)
        return None


def undeploy_by_token(blueprint_token: str, blueprint_id: str, blueprint_timestamp: str, directory: Directory,
                      inputs_file: FileStorage = None):
    try:

        session_token = uuid.uuid4()
        location = deployment_io.regenerate(directory, session_token)

        logfile_name = Settings.logfile_name
        trash = open("/dev/null", 'w')

        log.info("Orchestrating with xOpera...")

        timestamp_start = Settings.datetime_now_to_string()

        _list = [f'{Settings.implementation_dir}/scripts/undeploy.sh', '{}'.format(Path(location).absolute()), blueprint_id, logfile_name,
                 blueprint_token, str(session_token), timestamp_start, blueprint_timestamp]

        deploy_dict = dict()
        deploy_dict['name'] = "service.yaml"
        if inputs_file:
            inputs_yaml = yaml.safe_load(inputs_file.read().decode('utf-8'))
            deploy_dict['inputs'] = inputs_yaml or dict()
        else:
            deploy_dict['inputs'] = dict()

        # add / overwrite xopera-key-name
        deploy_dict['inputs']['xopera-key-name'] = Settings.key_pair

        # extract OS_USERNAME and OS_PASSWORD
        if "OS_USERNAME" in deploy_dict['inputs'] and "OS_PASSWORD" in deploy_dict['inputs']:
            os_username = deploy_dict['inputs']["OS_USERNAME"]
            os_password = deploy_dict['inputs']["OS_PASSWORD"]
            deploy_dict['inputs'].pop("OS_USERNAME", None)
            deploy_dict['inputs'].pop("OS_PASSWORD", None)
            deployment_io.replace_username_and_password(f"{location}/openrc.sh", os_username, os_password)

        log.info(f"deploy.yaml: \n{deploy_dict}")

        with open(f"{location}/{blueprint_id}.deploy", 'w') as deploy_file:
            json.dump(deploy_dict, deploy_file)
            # print(json.dumps(deploy_dict))

        subprocess.Popen(_list)  # , stdout=trash, stderr=trash)
        return session_token

    except Exception:
        log.error("Error in undeploy_by_id: ", exc_info=True)
        return None
