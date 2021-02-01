from opera.api.cli import SQL_database, CSAR_db
from opera.api.controllers.background_invocation import InvocationWorkerProcess
from opera.api.log import get_logger
from opera.api.openapi.models.error_msg import ErrorMsg
from opera.api.openapi.models.just_message import JustMessage
from opera.api.util import xopera_util

logger = get_logger(__name__)


def get_outputs(session_token):
    """
    Obtain outputs


    :param session_token: Token of TOSCA session
    :type session_token: str

    :rtype: object
    """

    session_data = SQL_database.get_session_data(session_token)
    if not session_data:
        return JustMessage(f"Session with session_token: {session_token} does not exist, cannot deploy"), 404
    blueprint_token = session_data['blueprint_token']
    version_tag = session_data['version_tag']
    if not CSAR_db.version_exists(blueprint_token, version_tag):
        return JustMessage(
            f"Did not find blueprint with token: {blueprint_token} and version_id: {version_tag or 'any'}"), 404

    outputs, exception = InvocationWorkerProcess.outputs(session_token)
    if exception:
        return ErrorMsg(exception[0], exception[1]), 500
    return outputs, 200
