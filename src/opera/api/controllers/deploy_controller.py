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
def post_deploy_fresh(blueprint_token, version_tag=None, workers=1):
    """
    Deploy blueprint (fresh)

    :param blueprint_token: token of blueprint
    :type blueprint_token: str
    :param version_tag: version_tag to deploy
    :type version_tag: str
    :param workers: Number of workers
    :type workers: int

    :rtype: Invocation
    """
    inputs = xopera_util.inputs_file()

    session_token_old = None
    result = invocation_service.invoke(OperationType.DEPLOY_FRESH, blueprint_token, version_tag, session_token_old,
                                       workers, inputs)
    logger.info(f"Deploying '{blueprint_token}', version_tag: {version_tag}")
    return result, 202


@security_controller.check_role_auth_session
def post_deploy_continue(session_token, workers=1, resume=True):
    """
    Deploy blueprint (continue)

    :param session_token: token of session
    :type session_token: str
    :param workers: Number of workers
    :type workers: int
    :param resume: Resume deploy
    :type resume: bool

    :rtype: Invocation
    """
    inputs = xopera_util.inputs_file()

    session_data = SQL_database.get_session_data(session_token)
    blueprint_token = session_data['blueprint_token']
    version_tag = session_data['version_tag']

    result = invocation_service.invoke(OperationType.DEPLOY_CONTINUE, blueprint_token, version_tag, session_token,
                                       workers, inputs, resume)
    logger.info(f"Deploying '{blueprint_token}', version_tag: {version_tag}")
    return result, 202
