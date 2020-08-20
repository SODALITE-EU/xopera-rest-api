import json

from settings import Settings


def check_status(session_token: str, format: str = 'short'):
    json_dict = {'state': "running", 'nodes': {}}
    deploy_dir = next(Settings.deployment_data.glob(f'*/{session_token}'), None)
    if deploy_dir is None:
        return {'message': f'Could not find session with session_token {session_token}'}, 404
    for file_path in (deploy_dir / ".opera" / "instances").glob("*"):
        parsed = json.load(open(file_path, 'r'))
        component_name = parsed['tosca_name']['data']
        json_dict['nodes'][component_name] = parsed if format == 'long' else parsed['state']['data']

    log_json_path = next(deploy_dir.glob("*.json"), None)
    if log_json_path:
        log_json = json.load(log_json_path.open('r'))
        status_code = 201 if log_json['state'] == "done" else 500
        json_dict = log_json if format == 'long' else {'state': log_json['state']}
    else:
        status_code = 202
    return json_dict, status_code
