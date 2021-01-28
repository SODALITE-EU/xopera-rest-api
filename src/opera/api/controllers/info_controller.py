import json

from opera.api.controllers.background_invocation import InvocationService
from opera.api.log import get_logger
from opera.api.openapi.models import InvocationState
from opera.api.openapi.models.git_log import GitLog
from opera.api.openapi.models.just_message import JustMessage
from opera.api.service import csardb_service, sqldb_service
from opera.api.settings import Settings

logger = get_logger(__name__)

CSAR_db = csardb_service.GitDB(**Settings.git_config)
SQL_database = sqldb_service.connect(Settings.sql_config)
invocation_service = InvocationService()


def get_deploy_log(blueprint_token=None, session_token=None):
    """

    :param blueprint_token: token of blueprint
    :type blueprint_token: str
    :param session_token: token of session
    :type session_token: str

    :rtype: None
    """
    data = SQL_database.get_deployment_log(blueprint_token=blueprint_token, session_token=session_token)
    if not data:
        return JustMessage("Log file not found"), 400
    # TODO solve timestamp format
    # return [DeploymentLog.from_dict(json.loads(_data[1])) for _data in data], 200
    return [json.loads(_data[1]) for _data in data], 200


def get_git_log(blueprint_token, version_tag=None, fetch_all=False):
    """

    :param blueprint_token:
    :type blueprint_token: str
    :param version_tag: version_tag of blueprint
    :type version_tag: str
    :param fetch_all: show all database entries, not just last one
    :type fetch_all: bool

    :rtype: None
    """

    data = SQL_database.get_git_transaction_data(blueprint_token, version_tag, fetch_all)
    if not data:
        return JustMessage("Log file not found"), 400
    return [GitLog.from_dict(item) for item in data], 200


def get_status(token=None):
    """Obtain job status

    :param token: session_token
    :type token: str

    :rtype: None
    """
    inv = invocation_service.load_invocation(token)
    if inv is None:
        return {'message': f'Could not find session with session_token {token}'}, 404
    code = {
        InvocationState.PENDING: 202,
        InvocationState.IN_PROGRESS: 202,
        InvocationState.SUCCESS: 201,
        InvocationState.FAILED: 500
    }
    logger.debug(json.dumps(inv.to_dict(), indent=2, sort_keys=True))
    return inv.to_dict(), code[inv.state]
