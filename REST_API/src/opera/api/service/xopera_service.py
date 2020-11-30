import json
import logging as log
import subprocess
from pathlib import Path

import yaml
from werkzeug.datastructures import FileStorage

from opera.api.blueprint_converters import blueprint2CSAR
from opera.api.settings import Settings
from opera.api.util import xopera_util, timestamp_util
from opera.api.log import get_logger

logger = get_logger(__name__)

def deploy(deployment_location: Path, inputs_file: FileStorage = None):
    logger.info("Orchestrating with xOpera...")

    timestamp_start = timestamp_util.datetime_now_to_string()
    entry_definitions = blueprint2CSAR.entry_definitions(csar=deployment_location)

    inputs_dict = dict()
    inputs_filename = "inputs.yaml"
    if inputs_file:
        inputs_yaml = yaml.safe_load(inputs_file.read().decode('utf-8'))
        inputs_dict = inputs_yaml or dict()
        inputs_filename = inputs_file.filename

    logger.debug(f"inputs_file: \n{inputs_dict}")

    with open(f"{deployment_location}/{inputs_filename}", 'w') as inputs_file:
        yaml.dump(inputs_dict, inputs_file)

    _list = [f'{Settings.implementation_dir}/service/deploy_scripts/deploy.sh', '{}'.format(str(deployment_location)),
             Settings.logfile_name, timestamp_start, inputs_filename, Settings.interpreter, entry_definitions]

    """
    import os
    logger.info(os.path.isfile(f'{Settings.implementation_dir}/service/deploy_scripts/deploy.sh'))
    # command = ['cd', f'{Settings.implementation_dir}/service/deploy_scripts', '&$', 'ls', '-la']
    bashCommand = f'/bin/sh cd /{Settings.implementation_dir}/service/deploy_scripts && ls -la'
    # popen = subprocess.Popen(command, stdout=subprocess.PIPE, universal_newlines=True)
    # logger.info(" ".join(iter(popen.stdout.readline, "")))
    # popen.stdout.close()
    process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    logger.info(output)
    """

    subprocess.Popen(_list)


def undeploy(deployment_location: Path, inputs_file: FileStorage = None):
    log.info("Orchestrating with xOpera...")

    timestamp_start = timestamp_util.datetime_now_to_string()

    inputs_dict = dict()
    if inputs_file:
        inputs_yaml = yaml.safe_load(inputs_file.read().decode('utf-8'))
        inputs_dict = inputs_yaml or dict()

    log.debug(f"inputs_file: \n{inputs_dict}")
    with (deployment_location / ".opera" / "inputs").open('w') as inputs_file:
        json.dump(inputs_dict, inputs_file, indent=2)

    _list = [f'{Settings.implementation_dir}/service/deploy_scripts/undeploy.sh', str(deployment_location),
             Settings.logfile_name, timestamp_start, Settings.interpreter]

    subprocess.Popen(_list)
