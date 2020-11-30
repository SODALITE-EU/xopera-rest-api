import connexion
import uuid
import json

from opera.api.openapi.models.blueprint_metadata import BlueprintMetadata
from opera.api.openapi.models.just_message import JustMessage
from opera.api.service import info_service, csardb_service, sqldb_service
from opera.api.log import get_logger
from opera.api.util import xopera_util, timestamp_util
from opera.api.settings import Settings

logger = get_logger(__name__)

CSAR_db = csardb_service.GitDB(**Settings.git_config)
SQL_database = sqldb_service.connect(Settings.sql_config)


def get_deploy_log(blueprint_token=None, session_token=None):  # noqa: E501
    """get_deploy_log

     # noqa: E501

    :param blueprint_token: token of blueprint
    :type blueprint_token: str
    :param session_token: token of session
    :type session_token: str

    :rtype: None
    """
    data = SQL_database.get_deployment_log(blueprint_token=blueprint_token, session_token=session_token)
    return_data = [{timestamp_util.datetime_to_str(_data[0]): json.loads(_data[1])} for _data in data]
    return_data.sort(key=lambda x: list(x.keys())[0], reverse=True)
    if not return_data:
        return JustMessage("Log file not found"), 400
    return return_data, 200


def get_git_log(blueprint_token, version_tag=None, all=None):  # noqa: E501
    """get_git_log

     # noqa: E501

    :param blueprint_token: 
    :type blueprint_token: str
    :param version_tag: version_tag of blueprint
    :type version_tag: str
    :param all: show all database entries, not just last one
    :type all: bool

    :rtype: None
    """

    data = SQL_database.get_git_transaction_data(blueprint_token=blueprint_token, version_tag=version_tag, all=all)
    if not data:
        return JustMessage("Log file not found"), 400
    return data, 200


def get_status(format=None, token=None):  # noqa: E501
    """get_status

     # noqa: E501

    :param format: long or short
    :type format: str
    :param token: session_token
    :type token: str

    :rtype: None
    """
    logger.debug(f"session_token: '{token}'")

    json_output, status_code = info_service.check_status(session_token=token, format=format)
    logger.debug(json.dumps(json_output, indent=2, sort_keys=True))
    return json_output, status_code
