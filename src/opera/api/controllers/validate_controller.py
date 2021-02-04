from opera.api.cli import CSAR_db
from opera.api.controllers.background_invocation import InvocationWorkerProcess
from opera.api.log import get_logger
from opera.api.openapi.models.error_msg import ErrorMsg
from opera.api.openapi.models.just_message import JustMessage
from opera.api.util import xopera_util
from opera.api.controllers import security_controller

logger = get_logger(__name__)

@security_controller.check_role_auth_blueprint
def post_validate(blueprint_token, version_tag=None):
    """post_validate

    Validates TOSCA service template # noqa: E501

    :param blueprint_token: Token of TOSCA blueprint
    :type blueprint_token: str
    :param version_tag: Version_tag to of TOSCA blueprint
    :type version_tag: str

    :rtype: JustMessage
    """
    inputs = xopera_util.inputs_file()

    exception = InvocationWorkerProcess.validate(blueprint_token, version_tag, inputs)
    if exception:
        return ErrorMsg(exception[0], exception[1]), 500
    return JustMessage("Validation OK"), 200