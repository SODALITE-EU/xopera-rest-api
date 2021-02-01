from opera.api.cli import CSAR_db, SQL_database
from opera.api.controllers.background_invocation import InvocationService
from opera.api.log import get_logger
from opera.api.openapi.models import OperationType, Invocation
from opera.api.openapi.models.just_message import JustMessage
from opera.api.util import xopera_util

logger = get_logger(__name__)
invocation_service = InvocationService()


def post_undeploy(session_token, workers=1):
    """

     Undeploy blueprint

    :param session_token: Token of deploy session
    :type session_token: str
    :param workers: Number of workers
    :type workers: int

    :rtype: Invocation
    """
    inputs = xopera_util.inputs_file()

    session_data = SQL_database.get_session_data(session_token)
    if not session_data:
        return JustMessage(f"Session with session_token: {session_token} does not exist, cannot undeploy"), 404
    blueprint_token = session_data['blueprint_token']
    version_tag = session_data['version_tag']

    if not CSAR_db.version_exists(blueprint_token, version_tag):
        return JustMessage(
            f"Did not find blueprint with token: {blueprint_token} and version_id: {version_tag or 'any'}"), 404

    result = invocation_service.invoke(OperationType.UNDEPLOY, blueprint_token, version_tag, session_token, workers,
                                       inputs)
    logger.info(f"Deploying '{blueprint_token}', version_tag: {version_tag} and session_token_old: {session_token}")
    return result, 202
