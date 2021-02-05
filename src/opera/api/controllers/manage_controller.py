import connexion

from opera.api.cli import CSAR_db, SQL_database
from opera.api.controllers import security_controller
from opera.api.log import get_logger
from opera.api.openapi.models.collaborators_list import CollaboratorsList
from opera.api.openapi.models.delete_metadata import DeleteMetadata
from opera.api.openapi.models.error_msg import ErrorMsg
from opera.api.openapi.models.git_revision_metadata import GitRevisionMetadata
from opera.api.openapi.models.just_message import JustMessage
from opera.api.settings import Settings
from opera.api.util import git_util

logger = get_logger(__name__)


@security_controller.check_role_auth_blueprint
def delete_manage_csar(blueprint_token, version_tag=None, force=None):
    """
    Delete one or more versions of blueprint

    :param blueprint_token: token of blueprint
    :type blueprint_token: str
    :param version_tag: version_tag to delete
    :type version_tag: str
    :param force: force delete blueprint
    :type force: bool

    :rtype: DeleteMetadata
    """
    if not force:
        last_message, _ = CSAR_db.get_tag_msg(blueprint_token, tag_name=version_tag)
        if last_message is not None:
            if git_util.after_job_commit_msg(token=blueprint_token, mode='deploy') in last_message:
                logger.info('Cannot delete, undeploy not done yet')
                return JustMessage("Cannot delete, deployment has not been undeployed yet"), 403

    repo_url, _ = CSAR_db.get_repo_url(blueprint_token)

    rows_affected, status_code = CSAR_db.delete_blueprint(blueprint_token, version_tag)
    logger.debug(f"Rows affected, status_code: {rows_affected} {status_code}")

    if status_code == 200:
        version_tags = [version_tag] if version_tag else SQL_database.get_version_tags(blueprint_token)
        n_msg = ' a version of ' if version_tag else ' '
        for tag in version_tags:
            SQL_database.save_git_transaction_data(blueprint_token=blueprint_token,
                                                   version_tag=tag,
                                                   revision_msg=f"Deleted{n_msg}blueprint",
                                                   job='delete',
                                                   git_backend=str(CSAR_db.connection.git_connector),
                                                   repo_url=repo_url)

    messages = {
        200: 'Successfully removed',
        404: 'Blueprint or blueprint not found',
        500: 'Server error'
    }

    return DeleteMetadata(
        message=messages[status_code],
        blueprint_token=blueprint_token,
        version_tag=version_tag or 'all',
        deleted_database_entries=rows_affected,
        force=force or False
    ), status_code


@security_controller.check_role_auth_blueprint
def get_git_user_manage(blueprint_token):
    """
    Obtain list of git users with access to repository

    :param blueprint_token: token of blueprint
    :type blueprint_token: str

    :rtype: CollaboratorsList
    """
    user_list, error_msg = CSAR_db.get_blueprint_user_list(blueprint_token=blueprint_token)

    repo_url, repo_error_msg = CSAR_db.get_repo_url(blueprint_token=blueprint_token)

    if user_list is not None and repo_url is not None:
        return CollaboratorsList(
            message=f'Found {len(user_list)} collaborators for repo with blueprint_token {blueprint_token}',
            blueprint_token=str(blueprint_token),
            repo_url=repo_url,
            collaborators=user_list
        ), 200

    return ErrorMsg(f"Could not retrieve list of users for repository with blueprint_id '{blueprint_token}'",
                    error_msg or repo_error_msg), 500


@security_controller.check_role_auth_blueprint
def post_git_user_manage(blueprint_token, username):
    """
    Add ne user to repository

    :param blueprint_token: token of blueprint
    :type blueprint_token: str
    :param username: username of user to be added to repository with blueprint
    :type username: str

    :rtype: JustMessage
    """
    success, error_msg = CSAR_db.add_member_to_blueprint(blueprint_token=blueprint_token, username=username)
    if success:
        return JustMessage(f"invite for user {username} sent"
                           if Settings.git_config['type'] == 'github'
                           else f"user {username} added"), 201

    return ErrorMsg(f"Could not add user {username} to repository with blueprint_id '{blueprint_token}'",
                    error_msg), 500


@security_controller.check_role_auth_blueprint
def post_manage_csar(blueprint_token, revision_msg=None):
    """
    Add new blueprint version to existing blueprint

    :param blueprint_token: token of blueprint
    :type blueprint_token: str
    :param revision_msg: Optional comment on submission
    :type revision_msg: str

    :rtype: GitRevisionMetadata
    """
    file = connexion.request.files['CSAR']

    blueprint_info = SQL_database.get_git_transaction_data(blueprint_token)

    result, response = CSAR_db.add_revision(CSAR=file, revision_msg=revision_msg, blueprint_token=blueprint_token)

    if result is None:
        return JustMessage(f"Invalid CSAR: {response}"), 406

    SQL_database.save_git_transaction_data(blueprint_token=result['blueprint_token'],
                                           version_tag=result['version_tag'],
                                           revision_msg=f"Updated blueprint: {revision_msg}",
                                           job='update',
                                           git_backend=str(CSAR_db.connection.git_connector),
                                           repo_url=result['url'],
                                           commit_sha=result['commit_sha'])

    return GitRevisionMetadata.from_dict(result), 200


def post_new_blueprint_csar(revision_msg=None, project_domain=None):
    """
    Add new blueprint

    :param revision_msg: Optional comment on submission
    :type revision_msg: str
    :param project_domain: Optional project domain this blueprint belongs to
    :type project_domain: str

    :rtype: GitRevisionMetadata
    """
    # check roles
    if project_domain and not security_controller.check_roles(project_domain):
        return JustMessage(f"Unauthorized request for project: {project_domain}"), 401

    file = connexion.request.files['CSAR']

    result, response = CSAR_db.add_revision(CSAR=file, revision_msg=revision_msg)

    if result is None:
        return JustMessage(f"Invalid CSAR: {response}"), 406

    if project_domain and not SQL_database.save_project_domain(result['blueprint_token'], project_domain):
        return JustMessage(f"Failed to save project data: {project_domain}"), 500

    SQL_database.save_git_transaction_data(blueprint_token=result['blueprint_token'],
                                           version_tag=result['version_tag'],
                                           revision_msg=f"Saved new blueprint: {revision_msg}",
                                           job='update',
                                           git_backend=str(CSAR_db.connection.git_connector),
                                           repo_url=result['url'],
                                           commit_sha=result['commit_sha'])

    return GitRevisionMetadata.from_dict(result), 200
