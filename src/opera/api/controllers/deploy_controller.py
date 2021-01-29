from opera.api.controllers.background_invocation import InvocationService
from opera.api.log import get_logger
from opera.api.openapi.models import OperationType, Invocation
from opera.api.openapi.models.just_message import JustMessage
from opera.api.service import csardb_service, sqldb_service
from opera.api.settings import Settings
from opera.api.util import xopera_util

logger = get_logger(__name__)

CSAR_db = csardb_service.GitDB(**Settings.git_config)
SQL_database = sqldb_service.connect(Settings.sql_config)
invocation_service = InvocationService()


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

    if not CSAR_db.version_exists(blueprint_token, version_tag):
        return JustMessage(
            f"Did not find blueprint with token: {blueprint_token} and version_id: {version_tag or 'any'}"), 404
    session_token_old = None
    result = invocation_service.invoke(OperationType.DEPLOY_FRESH, blueprint_token, version_tag, session_token_old,
                                       workers, inputs)
    logger.info(f"Deploying '{blueprint_token}', version_tag: {version_tag}")
    return result, 202


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
    if not session_data:
        return JustMessage(f"Session with session_token: {session_token} does not exist, cannot deploy"), 404
    blueprint_token = session_data['blueprint_token']
    version_tag = session_data['version_tag']
    if not CSAR_db.version_exists(blueprint_token, version_tag):
        return JustMessage(
            f"Did not find blueprint with token: {blueprint_token} and version_id: {version_tag or 'any'}"), 404

    result = invocation_service.invoke(OperationType.DEPLOY_CONTINUE, blueprint_token, version_tag, session_token,
                                       workers, inputs, resume)
    logger.info(f"Deploying '{blueprint_token}', version_tag: {version_tag}")
    return result, 202
