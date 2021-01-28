import connexion
import yaml

from opera.api.controllers.background_invocation import InvocationService
from opera.api.log import get_logger
from opera.api.openapi.models import OperationType
from opera.api.openapi.models.blueprint_metadata import BlueprintMetadata
from opera.api.openapi.models.just_message import JustMessage
from opera.api.service import csardb_service, sqldb_service
from opera.api.settings import Settings

logger = get_logger(__name__)

CSAR_db = csardb_service.GitDB(**Settings.git_config)
SQL_database = sqldb_service.connect(Settings.sql_config)
invocation_service = InvocationService()


def post_deploy(blueprint_token, version_tag=None, workers=1, resume=False):
    """
    Deploy blueprint

    :param blueprint_token: token of blueprint
    :type blueprint_token: str
    :param version_tag: version_tag to deploy
    :type version_tag: str
    :param workers: Number of workers
    :type workers: int
    :param resume: Resume deploy
    :type resume: bool

    :rtype: BlueprintMetadata
    """
    try:
        inputs_file = connexion.request.files['inputs_file']
        inputs = yaml.safe_load(inputs_file.read().decode('utf-8'))
    except KeyError:
        inputs = None

    if not CSAR_db.version_exists(blueprint_token, version_tag):
        return JustMessage(
            f"Did not find blueprint with token: {blueprint_token} and version_id: {version_tag or 'any'}"), 404

    result = invocation_service.invoke(OperationType.DEPLOY, blueprint_token, version_tag, workers, resume, inputs)
    logger.info(f"Deploying '{blueprint_token}', version_tag: {version_tag}")
    return result, 202
