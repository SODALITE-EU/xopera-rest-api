from opera.api.controllers import security_controller
from opera.api.controllers.background_invocation import InvocationWorkerProcess
from opera.api.openapi.models import Invocation
from opera.api.util import xopera_util


@security_controller.check_role_auth_blueprint
@security_controller.check_role_auth_session
def post_diff(session_token, blueprint_token, version_tag=None):
    """
    Diff

    Calculates the diff between Deployed instance model (DI1) and New blueprint version (DB2 = B2 + V2 + I2)

    :param session_token: Session_token of Deployed instance model (DI1)
    :type session_token: str
    :param blueprint_token: Token of The new blueprint (B2)
    :type blueprint_token: str
    :param version_tag: Version_tag to of The new blueprint (V2)
    :type version_tag: str

    :rtype: Invocation
    """
    inputs = xopera_util.inputs_file()

    return InvocationWorkerProcess.diff(session_token, blueprint_token, version_tag, inputs).outputs(), 200
