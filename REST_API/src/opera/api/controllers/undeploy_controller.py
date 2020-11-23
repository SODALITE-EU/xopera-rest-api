import connexion
import six

from opera.api.openapi.models.blueprint_metadata import BlueprintMetadata  # noqa: E501
from opera.api.openapi.models.just_message import JustMessage  # noqa: E501
from opera.api.openapi import util


def delete_deploy(blueprint_token, version_tag=None, inputs_file=None):  # noqa: E501
    """delete_deploy

     # noqa: E501

    :param blueprint_token: token of blueprint
    :type blueprint_token: str
    :param version_tag: version_tag to deploy
    :type version_tag: str
    :param inputs_file: File with inputs for TOSCA template
    :type inputs_file: str

    :rtype: BlueprintMetadata
    """
    return 'do some magic!'
