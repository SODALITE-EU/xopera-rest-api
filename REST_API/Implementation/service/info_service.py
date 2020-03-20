import glob
import json
import os

from settings import Settings


def check_status(session_token: str, format: str = 'short'):
    json_dict = {}
    for file_path in glob.glob("{}/*/{}/*.data".format(Settings.deployment_data, session_token)):
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

