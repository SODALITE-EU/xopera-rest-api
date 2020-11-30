import connexion
import uuid

from opera.api.openapi.models.blueprint_metadata import BlueprintMetadata
from opera.api.openapi.models.just_message import JustMessage
from opera.api.service import csardb_service, sqldb_service, xopera_service
from opera.api.log import get_logger
from opera.api.util import xopera_util, timestamp_util
from opera.api.settings import Settings

logger = get_logger(__name__)

CSAR_db = csardb_service.GitDB(**Settings.git_config)
SQL_database = sqldb_service.connect(Settings.sql_config)


def post_deploy(blueprint_token, version_tag=None):
    """post_deploy

     # noqa: E501

    :param blueprint_token: token of blueprint
    :type blueprint_token: str
    :param version_tag: version_tag to deploy
    :type version_tag: str

    :rtype: BlueprintMetadata
    """
    try:
        file = connexion.request.files['inputs_file']
    except KeyError:
        file = None
    session_token = uuid.uuid4()
    location = xopera_util.deployment_location(session_token=session_token, blueprint_token=blueprint_token)
    logger.debug(f"Deploy_location: {location}")

    if CSAR_db.get_revision(blueprint_token=blueprint_token, dst=location, version_tag=version_tag) is None:
        return JustMessage(f"Did not find blueprint with token: {blueprint_token} and version_id: {version_tag or 'any'}"), 404

    xopera_util.save_version_tag(deploy_location=location, version_tag=version_tag)

    xopera_service.deploy(deployment_location=location, inputs_file=file)

    logger.info(f"Deploying '{blueprint_token}', session_token: {session_token}")

    response = {
        "message": "Deploy job started, check status via /info/status endpoint",
        "session_token": str(session_token),
        "blueprint_token": str(blueprint_token),
        "version_tag": version_tag or "last",
        "timestamp": timestamp_util.datetime_now_to_string()
    }
    return BlueprintMetadata.from_dict(response), 202
