from opera.api.controllers.background_invocation import InvocationService
from opera.api.log import get_logger
from opera.api.openapi.models import OperationType, Invocation
from opera.api.openapi.models.just_message import JustMessage
from opera.api.service import csardb_service, sqldb_service
from opera.api.util import xopera_util
from opera.api.settings import Settings

logger = get_logger(__name__)

CSAR_db = csardb_service.GitDB(**Settings.git_config)
SQL_database = sqldb_service.connect(Settings.sql_config)
invocation_service = InvocationService()


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

    if not SQL_database.get_session_data(session_token):
        return JustMessage(f"Session with session_token: {session_token} does not exist, cannot update"), 404
    if not CSAR_db.version_exists(blueprint_token, version_tag):
        return JustMessage(
            f"Did not find blueprint with token: {blueprint_token} and version_id: {version_tag or 'any'}"), 404

    result = invocation_service.invoke(OperationType.UPDATE, blueprint_token, version_tag, session_token,
                                       workers, inputs)
    logger.info(f"Updating '{session_token}' with blueprint '{blueprint_token}', version_tag: {version_tag}")
    return result, 202
