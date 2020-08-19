import json
import logging as log
import subprocess
from pathlib import Path

import yaml
from werkzeug.datastructures import FileStorage

from blueprint_converters import blueprint2CSAR
from settings import Settings
from util import xopera_util, timestamp_util


def deploy(deployment_location: Path, inputs_file: FileStorage = None):
    log.info("Orchestrating with xOpera...")

    timestamp_start = timestamp_util.datetime_now_to_string()
    entry_definitions = blueprint2CSAR.entry_definitions(csar=deployment_location)

    inputs_dict = dict()
    inputs_filename = "inputs.yaml"
    if inputs_file:
        inputs_yaml = yaml.safe_load(inputs_file.read().decode('utf-8'))
        inputs_dict = inputs_yaml or dict()
        inputs_filename = inputs_file.filename

    log.debug(f"inputs_file: \n{inputs_dict}")

    with open(f"{deployment_location}/{inputs_filename}", 'w') as inputs_file:
        yaml.dump(inputs_dict, inputs_file)

    _list = [f'{Settings.implementation_dir}/service/deploy_scripts/deploy.sh', '{}'.format(str(deployment_location)),
             Settings.logfile_name, timestamp_start, inputs_filename, Settings.interpreter, entry_definitions]

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
