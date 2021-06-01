import connexion

from opera.api.cli import CSAR_db, SQL_database
from opera.api.controllers import security_controller
from opera.api.log import get_logger
from opera.api.openapi.models import Blueprint
from opera.api.settings import Settings
from opera.api.util import timestamp_util

logger = get_logger(__name__)


@security_controller.check_role_auth_blueprint
def delete_git_user(blueprint_id, user_id):
    """Delete user.

    :param blueprint_id: Id of blueprint
    :type blueprint_id: 
    :param user_id: user_id to be removed from repository with blueprint
    :type user_id: str

    :rtype: str
    """
    success, error_msg = CSAR_db.delete_blueprint_user(blueprint_id=blueprint_id, username=user_id)
    if success:
        return f"User {user_id} deleted", 200

    return f"Could not delete user {user_id} from repository with blueprint_id '{blueprint_id}': {error_msg}", 500


@security_controller.check_role_auth_blueprint
def delete_blueprint(blueprint_id, force=None):
    """Delete blueprint.

    :param blueprint_id: Id of blueprint
    :type blueprint_id: 
    :param force: force delete blueprint
    :type force: bool

    :rtype: Blueprint
    """
    if not force:
        if SQL_database.blueprint_used_in_deployment(blueprint_id):
            return "Cannot delete blueprint, deployment with this blueprint exists", 403

    repo_url, _ = CSAR_db.get_repo_url(blueprint_id)

    rows_affected, status_code = CSAR_db.delete_blueprint(blueprint_id)
    logger.debug(f"Rows affected, status_code: {rows_affected} {status_code}")

    if status_code == 200:

        SQL_database.delete_blueprint_meta(blueprint_id)
        SQL_database.save_git_transaction_data(blueprint_id=blueprint_id,
                                               revision_msg=f"Deleted blueprint",
                                               job='delete',
                                               git_backend=str(CSAR_db.connection.git_connector),
                                               repo_url=repo_url)
        return Blueprint(blueprint_id=blueprint_id,
                         url=repo_url,
                         timestamp=timestamp_util.datetime_now_to_string()), 200

    message = {
        200: 'Successfully removed',
        404: 'Blueprint not found',
        500: 'Server error'
    }

    return message[status_code], status_code


@security_controller.check_role_auth_blueprint
def delete_blueprint_version(blueprint_id, version_id, force=None):
    """Delete version of blueprint.

    :param blueprint_id: Id of blueprint
    :type blueprint_id: 
    :param version_id: Id of blueprint version
    :type version_id: str
    :param force: force delete blueprint
    :type force: bool

    :rtype: Blueprint
    """
    if not force:
        if SQL_database.blueprint_used_in_deployment(blueprint_id, version_id):
            return "Cannot delete blueprint, deployment with this blueprint exists", 403

    repo_url, _ = CSAR_db.get_repo_url(blueprint_id)

    rows_affected, status_code = CSAR_db.delete_blueprint(blueprint_id, version_id)
    logger.debug(f"Rows affected, status_code: {rows_affected} {status_code}")

    if status_code == 200:

        SQL_database.delete_blueprint_meta(blueprint_id, version_id)
        SQL_database.save_git_transaction_data(blueprint_id=blueprint_id,
                                               version_id=version_id,
                                               revision_msg=f"Deleted a version of blueprint",
                                               job='delete',
                                               git_backend=str(CSAR_db.connection.git_connector),
                                               repo_url=repo_url)
        return Blueprint(blueprint_id=blueprint_id,
                         version_id=version_id,
                         url=repo_url,
                         timestamp=timestamp_util.datetime_now_to_string()), 200

    message = {
        200: 'Successfully removed',
        404: 'Blueprint version or blueprint not found',
        500: 'Server error'
    }

    return message[status_code], status_code


@security_controller.check_role_auth_blueprint
def get_git_user(blueprint_id):
    """List users with access.

    :param blueprint_id: Id of blueprint
    :type blueprint_id: 

    :rtype: List[str]
    """
    user_list, error_msg = CSAR_db.get_blueprint_user_list(blueprint_id)

    if user_list is not None:
        return user_list, 200

    return f"Could not retrieve list of users for repository with blueprint_id '{blueprint_id}': {error_msg}", 500


@security_controller.check_role_auth_blueprint
def post_git_user(blueprint_id, user_id):
    """Add user to blueprint.

    :param blueprint_id: Id of blueprint
    :type blueprint_id: 
    :param user_id: Username to be added to repository with blueprint
    :type user_id: str

    :rtype: str
    """
    success, error_msg = CSAR_db.add_member_to_blueprint(blueprint_id=blueprint_id, username=user_id)
    if success:
        message = {
            'github': f"Invite for user {user_id} sent",
            'gitlab': f"User {user_id} added",
            'mock': f"User {user_id} added"
        }
        return message[Settings.git_config['type']], 200

    return f"Could not add user {user_id} to repository with blueprint_id '{blueprint_id}': {error_msg}", 500


@security_controller.check_role_auth_blueprint
def post_blueprint(blueprint_id, revision_msg=None):
    """Add new version to existing blueprint.

    :param blueprint_id: Id of blueprint
    :type blueprint_id:
    :param revision_msg: Optional comment on submission
    :type revision_msg: str

    :rtype: Blueprint
    """
    file = connexion.request.files['CSAR']

    result, response = CSAR_db.add_revision(CSAR=file, revision_msg=revision_msg, blueprint_id=blueprint_id)

    if result is None:
        return f"Invalid CSAR: {response}", 406

    blueprint_meta = Blueprint.from_dict(result)

    blueprint_meta.name = SQL_database.get_blueprint_name(blueprint_id)
    blueprint_meta.project_domain = SQL_database.get_project_domain(blueprint_id)

    if not SQL_database.save_blueprint_meta(blueprint_meta):
        return f"Failed to save project data for blueprint_id={blueprint_id}", 500

    SQL_database.save_git_transaction_data(blueprint_id=result['blueprint_id'],
                                           version_id=result['version_id'],
                                           revision_msg=f"Updated blueprint: {revision_msg}",
                                           job='update',
                                           git_backend=str(CSAR_db.connection.git_connector),
                                           repo_url=result['url'],
                                           commit_sha=result['commit_sha'])

    return blueprint_meta, 201


def post_new_blueprint(revision_msg=None, name=None, project_domain=None):
    """Add new blueprint.

    :param revision_msg: Optional comment on submission
    :type revision_msg: str
    :param name: Optional human-readable blueprint name
    :type name: str
    :param project_domain: Optional project domain this blueprint belongs to
    :type project_domain: str

    :rtype: Blueprint
    """
    # check roles
    if project_domain and not security_controller.check_roles(project_domain):
        return f"Unauthorized request for project: {project_domain}", 401

    file = connexion.request.files['CSAR']

    result, response = CSAR_db.add_revision(CSAR=file, revision_msg=revision_msg)

    if result is None:
        return f"Invalid CSAR: {response}", 406

    blueprint_meta = Blueprint.from_dict(result)

    blueprint_meta.name = name
    blueprint_meta.project_domain = project_domain

    if not SQL_database.save_blueprint_meta(blueprint_meta):
        blueprint_id = blueprint_meta.blueprint_id
        return f"Failed to save project data for blueprint_id={blueprint_id}", 500

    SQL_database.save_git_transaction_data(blueprint_id=result['blueprint_id'],
                                           version_id=result['version_id'],
                                           revision_msg=f"Saved new blueprint: {revision_msg}",
                                           job='update',
                                           git_backend=str(CSAR_db.connection.git_connector),
                                           repo_url=result['url'],
                                           commit_sha=result['commit_sha'])

    return blueprint_meta, 201

