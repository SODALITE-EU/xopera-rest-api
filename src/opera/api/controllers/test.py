from opera.commands.diff import _parser_callback
import argparse
from opera.utils import format_outputs, save_outputs, get_template, get_workdir
from opera.storage import Storage
from opera.api.util import xopera_util

from pathlib import Path
import yaml
import json


class AObj:
    name = None


class Inputs:
    name = None



blueprint_dir = Path(
    '/home/mihaeltrajbaric/projects/SODALITE/Collection/TOSCA/mihas-private-tosca-blueprint-collection/blueprint_hash_test')

with xopera_util.cwd(blueprint_dir):

    args = argparse.Namespace()
    args.instance_path = None
    args.output = None
    args.shell_completion = None
    args.template = Path('service.yaml').open('r')
    args.template_only = False
    args.verbose = False
    args.command = 'diff'
    args.format = 'yaml'
    args.inputs = Path('inputs.yaml').open('r')

    _parser_callback(args)
