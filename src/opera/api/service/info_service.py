import json
import time

from opera.api.settings import Settings
from opera.api.controllers.background_invocation import InvocationService
from opera.api.openapi.models import Invocation, InvocationState, OperationType


invocation_service = InvocationService()

def check_status1(session_token: str, format: str = 'short'):
    json_dict = {'state': "running", 'nodes': {}}
    deploy_dir = next(Settings.deployment_data.glob(f'*/{session_token}'), None)
    if deploy_dir is None:
        return {'message': f'Could not find session with session_token {session_token}'}, 404
    for file_path in (deploy_dir / ".opera" / "instances").glob("*"):
        # it seems that reading JSON from file xOpera writes
        # can cause a race condition
        # this should be improved
        count = 0
        while count < 10:
            try:
                parsed = json.load(open(file_path, 'r'))
                component_name = parsed['tosca_name']['data']
                json_dict['nodes'][component_name] = parsed if format == 'long' else parsed['state']['data']
                break
            except:
                count += 1
                time.sleep(0.01)

    log_json_path = next(deploy_dir.glob("*.json"), None)
    if log_json_path:
        log_json = json.load(log_json_path.open('r'))
        status_code = 201 if log_json['state'] == "done" else 500
        json_dict = log_json if format == 'long' else {'state': log_json['state']}
    else:
        status_code = 202
    return json_dict, status_code


def check_status(session_token: str, format: str = 'short'):
    inv = invocation_service.load_invocation(session_token)
    if inv is None:
        return {'message': f'Could not find session with session_token {session_token}'}, 404
    code = {
        InvocationState.PENDING: 202,
        InvocationState.IN_PROGRESS: 202,
        InvocationState.SUCCESS: 201,
        InvocationState.FAILED: 500
    }
    return inv.to_dict(), code[inv.state]
