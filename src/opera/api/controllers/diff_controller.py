from opera.api.controllers.background_invocation import InvocationWorkerProcess
from opera.api.openapi.models import Invocation
from opera.api.openapi.models.just_message import JustMessage
from opera.api.service import csardb_service, sqldb_service
from opera.api.settings import Settings
from opera.api.util import xopera_util

CSAR_db = csardb_service.GitDB(**Settings.git_config)
SQL_database = sqldb_service.connect(Settings.sql_config)


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

    if not SQL_database.get_session_data(session_token):
        return JustMessage(f"Session with session_token: {session_token} does not exist, cannot update"), 404
    if not CSAR_db.version_exists(blueprint_token, version_tag):
        return JustMessage(
            f"Did not find blueprint with token: {blueprint_token} and version_id: {version_tag or 'any'}"), 404

    return InvocationWorkerProcess.diff(session_token, blueprint_token, version_tag, inputs).outputs(), 200


