from opera.api.cli import CSAR_db, SQL_database
from opera.api.controllers.background_invocation import InvocationService
from opera.api.log import get_logger
from opera.api.openapi.models import OperationType, Invocation
from opera.api.openapi.models.just_message import JustMessage
from opera.api.util import xopera_util
from opera.api.controllers import security_controller

logger = get_logger(__name__)
invocation_service = InvocationService()


@security_controller.check_role_auth_session
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
    blueprint_token = session_data['blueprint_token']
    version_tag = session_data['version_tag']

    result = invocation_service.invoke(OperationType.UNDEPLOY, blueprint_token, version_tag, session_token, workers,
                                       inputs)
    logger.info(f"Deploying '{blueprint_token}', version_tag: {version_tag} and session_token_old: {session_token}")
    return result, 202
