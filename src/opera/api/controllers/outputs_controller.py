from opera.api.cli import SQL_database, CSAR_db
from opera.api.controllers.background_invocation import InvocationWorkerProcess
from opera.api.log import get_logger
from opera.api.openapi.models.error_msg import ErrorMsg
from opera.api.openapi.models.just_message import JustMessage
from opera.api.util import xopera_util
from opera.api.controllers import security_controller

logger = get_logger(__name__)


@security_controller.check_role_auth_session
def get_outputs(session_token):
    """
    Obtain outputs


    :param session_token: Token of TOSCA session
    :type session_token: str

    :rtype: object
    """

    session_data = SQL_database.get_session_data(session_token)
  
    outputs, exception = InvocationWorkerProcess.outputs(session_token)
    if exception:
        return ErrorMsg(exception[0], exception[1]), 500
    return outputs, 200
