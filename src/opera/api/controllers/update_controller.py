from opera.api.cli import CSAR_db, SQL_database
from opera.api.controllers.background_invocation import InvocationService
from opera.api.log import get_logger
from opera.api.openapi.models import OperationType, Invocation
from opera.api.openapi.models.just_message import JustMessage
from opera.api.util import xopera_util
from opera.api.controllers import security_controller

logger = get_logger(__name__)
invocation_service = InvocationService()

@security_controller.check_role_auth_blueprint
@security_controller.check_role_auth_session
def post_update(session_token, blueprint_token, version_tag=None, workers=1):
    """
    Update

    Deploys Instance model (DI2), where DI2 &#x3D; diff(DI1, (B2,V2,I2)) # noqa: E501

    :param session_token: Session_token of old Deployed instance model (DI1)
    :type session_token: str
    :param blueprint_token: Token of the new blueprint (B2)
    :type blueprint_token: str
    :param version_tag: Version_tag to of the new blueprint (V2)
    :type version_tag: str
    :param workers: Number of workers
    :type workers: int

    :rtype: Invocation
    """
    inputs = xopera_util.inputs_file()

    result = invocation_service.invoke(OperationType.UPDATE, blueprint_token, version_tag, session_token,
                                       workers, inputs)
    logger.info(f"Updating '{session_token}' with blueprint '{blueprint_token}', version_tag: {version_tag}")
    return result, 202
