from opera.api.cli import SQL_database
from opera.api.controllers import security_controller
from opera.api.log import get_logger
from opera.api.openapi.models import BlueprintVersion, GitLog, Deployment

logger = get_logger(__name__)


@security_controller.check_role_auth_blueprint
def get_blueprint_meta(blueprint_id):  # noqa: E501
    """Get blueprint&#39;s metadata

     # noqa: E501

    :param blueprint_id: Id of blueprint
    :type blueprint_id:

    :rtype: Blueprint
    """
    data = SQL_database.get_blueprint_meta(blueprint_id)
    if not data:
        return "Blueprint meta not found", 404
    return BlueprintVersion.from_dict(data), 200


@security_controller.check_role_auth_blueprint
def get_blueprint_version_meta(blueprint_id, version_id):  # noqa: E501
    """Get blueprint version&#39;s metadata

     # noqa: E501

    :param blueprint_id: Id of blueprint
    :type blueprint_id:
    :param version_id: Id of blueprint version
    :type version_id: str

    :rtype: Blueprint
    """
    data = SQL_database.get_blueprint_meta(blueprint_id, version_id)
    if not data:
        return "Blueprint meta not found", 404
    return BlueprintVersion.from_dict(data), 200


@security_controller.check_role_auth_blueprint
def get_blueprint_name(blueprint_id):  # noqa: E501
    """Get blueprint name

     # noqa: E501

    :param blueprint_id: Id of blueprint
    :type blueprint_id:

    :rtype: str
    """
    name = SQL_database.get_blueprint_name(blueprint_id)
    if not name:
        return "Blueprint name not found", 404
    return name, 200


@security_controller.check_role_auth_blueprint
def post_blueprint_name(blueprint_id, name):  # noqa: E501
    """Change blueprint name

     # noqa: E501

    :param blueprint_id: Id of blueprint
    :type blueprint_id:
    :param name: Desired blueprint name
    :type name: str

    :rtype: str
    """
    if not SQL_database.update_blueprint_name(blueprint_id, name):
        return f"Failed to save project data for blueprint_id={blueprint_id}", 500
    return "Successfully changed name", 201


@security_controller.check_role_auth_blueprint
def get_blueprint_deployments(blueprint_id, active=True):  # noqa: E501
    """Get deployments for current blueprint

     # noqa: E501

    :param blueprint_id: Id of blueprint
    :type blueprint_id:
    :param active: Obtain only list of active deployments.
    :type active: bool

    :rtype: List[Deployment]
    """
    data = SQL_database.get_deployments_for_blueprint(blueprint_id, active)
    if not data:
        return "Deployments not found", 404
    return [Deployment.from_dict(item) for item in data], 200


@security_controller.check_role_auth_project_domain
def get_git_log(blueprint_id):
    """List all update/delete transactions to git repository with blueprint.

    :param blueprint_id: Id of blueprint
    :type blueprint_id:

    :rtype: List[GitLog]
    """
    data = SQL_database.get_git_transaction_data(blueprint_id)
    if not data:
        return "Log not found", 404
    return [GitLog.from_dict(item) for item in data], 200
