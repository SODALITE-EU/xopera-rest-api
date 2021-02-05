import json

from opera.api.cli import SQL_database
from opera.api.controllers import security_controller
from opera.api.controllers.background_invocation import InvocationService
from opera.api.log import get_logger
from opera.api.openapi.models import InvocationState, Invocation, GitLog
from opera.api.openapi.models.just_message import JustMessage

logger = get_logger(__name__)

invocation_service = InvocationService()


@security_controller.check_role_auth_session_or_blueprint
def get_deploy_log(blueprint_token=None, session_token=None):
    """

    :param blueprint_token: token of blueprint
    :type blueprint_token: str
    :param session_token: token of session
    :type session_token: str

    :rtype: List[Invocation]
    """
    data = SQL_database.get_deployment_log(blueprint_token, session_token)
    if not data:
        return JustMessage("Log file not found"), 400
    return [Invocation.from_dict(json.loads(_data[1])) for _data in data], 200


@security_controller.check_role_auth_blueprint
def get_git_log(blueprint_token, version_tag=None, fetch_all=False):
    """

    :param blueprint_token:
    :type blueprint_token: str
    :param version_tag: version_tag of blueprint
    :type version_tag: str
    :param fetch_all: show all database entries, not just last one
    :type fetch_all: bool

    :rtype: List[GitLog]
    """

    data = SQL_database.get_git_transaction_data(blueprint_token, version_tag, fetch_all)
    if not data:
        return JustMessage("Log file not found"), 400
    return [GitLog.from_dict(item) for item in data], 200


@security_controller.check_role_auth_session
def get_status(session_token):
    """
    Obtain job status

    :param session_token: session_token
    :type session_token: str

    :rtype: Invocation
    """
    inv = invocation_service.load_invocation(session_token)
    if inv is None:
        return {'message': f'Could not find session with session_token {session_token}'}, 404
    code = {
        InvocationState.PENDING: 202,
        InvocationState.IN_PROGRESS: 202,
        InvocationState.SUCCESS: 201,
        InvocationState.FAILED: 500
    }
    logger.debug(json.dumps(inv.to_dict(), indent=2, sort_keys=True))
    return inv, code[inv.state]
