import connexion
import six

from opera.api.openapi.models.just_message import JustMessage  # noqa: E501
from opera.api.openapi import util


def get_deploy_log(blueprint_token=None, session_token=None):  # noqa: E501
    """get_deploy_log

     # noqa: E501

    :param blueprint_token: token of blueprint
    :type blueprint_token: str
    :param session_token: token of session
    :type session_token: str

    :rtype: None
    """
    return 'do some magic!'


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
    return 'do some magic!'


def get_status(format=None, token=None):  # noqa: E501
    """get_status

     # noqa: E501

    :param format: long or short
    :type format: str
    :param token: session_token
    :type token: str

    :rtype: None
    """
    return 'do some magic!'
