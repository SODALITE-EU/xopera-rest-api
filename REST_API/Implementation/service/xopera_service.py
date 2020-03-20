import json
import logging as log
import subprocess
from pathlib import Path

import yaml
from werkzeug.datastructures import FileStorage

from settings import Settings
from util import xopera_util, timestamp_util


def deploy(deployment_location: Path, inputs_file: FileStorage = None):

    # add generic rc file to deployment_location
    xopera_util.generic_rc_file(path=deployment_location)

    log.info("Orchestrating with xOpera...")

    timestamp_start = timestamp_util.datetime_now_to_string()

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
        xopera_util.replace_username_and_password(f"{deployment_location}/openrc.sh", os_username, os_password)

    log.info(f"inputs_file: \n{inputs_dict}")

    with open(f"{deployment_location}/{inputs_filename}", 'w') as inputs_file:
        yaml.dump(inputs_dict, inputs_file)
        # print(json.dumps(inputs_dict))

    _list = [f'{Settings.implementation_dir}/service/deploy_scripts/deploy.sh', '{}'.format(str(deployment_location)),
             Settings.logfile_name, timestamp_start, inputs_filename, Settings.interpreter]

    subprocess.Popen(_list)  # , stderr=trash, stdout=trash)


def undeploy(deployment_location: Path, inputs_file: FileStorage = None):

    # add generic rc file to deployment_location
    xopera_util.generic_rc_file(path=deployment_location)

    log.info("Orchestrating with xOpera...")

    timestamp_start = timestamp_util.datetime_now_to_string()

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
        xopera_util.replace_username_and_password(f"{deployment_location}/openrc.sh", os_username, os_password)

    log.info(f"deploy.yaml: \n{deploy_dict}")
    with open(f"{deployment_location}/blueprint_id.deploy", 'w') as deploy_file:
        json.dump(deploy_dict, deploy_file)
        # print(json.dumps(deploy_dict))
    _list = [f'{Settings.implementation_dir}/service/deploy_scripts/undeploy.sh', str(deployment_location),
             Settings.logfile_name, timestamp_start, Settings.interpreter]

    subprocess.Popen(_list)
