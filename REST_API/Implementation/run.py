import json
import logging as log
import time
import uuid
from pathlib import Path

import psycopg2
from flask import Flask, request
from flask_restplus import Api, Resource, fields, inputs
from werkzeug.datastructures import FileStorage

from service import xopera_service, info_service, csardb_service, sqldb_service
from settings import Settings
from util import xopera_util, timestamp_util, git_util

Settings.load_settings()
log.info('RESTapi verbose: {}'.format('True' if Settings.verbose else 'False'))
xopera_util.clean_deployment_data()
if not Settings.testing:
    xopera_util.configure_ssh_keys()

Settings.interpreter = 'python3'
log.info(f'Interpreter: {Settings.interpreter}')

if not Settings.testing:
    for i in range(10):
        try:
            SQL_database = sqldb_service.PostgreSQL(Settings.sql_config)
            log.info('SQL_database: PostgreSQL')
            break
        except psycopg2.Error as e:
            log.error(f"Error while connecting to PostgreSQL for {i+1} time: {str(e)}")
            time.sleep(1)

try:
    SQL_database = sqldb_service.PostgreSQL(Settings.sql_config)
    log.info('SQL_database: PostgreSQL')
except psycopg2.Error as e:
    log.error(f"Error while connecting to PostgreSQL: {str(e)}")
    SQL_database = sqldb_service.OfflineStorage()
    log.info("SQL_database: OfflineStorage")

CSAR_db = csardb_service.GitDB(**Settings.git_config)
log.info(f"GitCsarDB with {str(CSAR_db.connection.git_connector)}")

flask_app = Flask(__name__)
api = Api(app=flask_app, version='0.2.5', title="xOpera REST API",
          description="xOpera REST API with xOpera==0.5.7\n\n"
                      "Standard scenarios of using REST api:\n\n"
                      "FIRST RUN\n"
                      "- GET key pair via ssh/keys/public download and register it on your openstack\n\n"
                      "DEPLOY\n"
                      "1) upload blueprint with POST to /manage\n - new version of existing one must be POSTed to "
                      "/manage/{blueprint_token}\n - save blueprint_metadata, returned by API call -> it is the only "
                      "way of accessing your blueprint afterwards\n "
                      "2) deploy last version of blueprint with POST to /deploy/{blueprint_token}\n"
                      "- optionally, inputs file to be used with template must also be uploaded within same API call\n"
                      "- another version can be specified by version_tag\n"
                      "- save session_token\n"
                      "3) using status_token from with GET to /info/status check status of your job\n"
                      "4) After completion, check logs with GET to /info/log/deployment\n\n"
                      "UNDEPLOY\n"
                      "1) undeploy blueprint with DELETE to /deploy/{blueprint_token}\n"
                      "- optionally, inputs file to be used with template must also be uploaded within same API call\n"
                      " - optionally also in combination with version_tag\n - save session_token\n "
                      "2) using status_token with GET to /info/status check status of your job\n"
                      "3) After completion, check logs with GET to /info/log/deployment\n"
                      "4) Delete all versions of blueprint from database with DELETE to /manage/{blueprint_token}\n"
                      "- to delete just specific version, use version_id or timestamp\n"
                      "- if deployment from template has not been undeployed yet, blueprint cannot be deleted"
                      "-> use 'force' to override\n\n"
                      "ACCESS TO REPOSITORY WITH BLUEPRINTS\n"
                      "- xOpera REST API uses git backend for storing blueprints\n"
                      "- to obtain access, POST to /manage/<blueprint_token>/user endpoint username and invitation "
                      "will be sent\n"
                      "- with GET to /manage/<blueprint_token>/user user can obtain "
                      "list of collaborators and repo url\n\n"
                      "GIT LOGS\n"
                      "- Last transaction details for gitCsarDB can be inspected using "
                      "/info/log/git/{blueprint_token} endpoint.\n"
                      "- optionally, logs inspection can be further specified with version_tag\n"
                      "- if all=True, all logs that satisfy blueprint_token and version_tag conditions will be "
                      "returned\n\n"
          )

# namespaces
ssh = api.namespace('ssh', description='SSH key management')
manage = api.namespace('manage', description='save or delete blueprint')
deploy = api.namespace('deploy', description='deploy or undeploy blueprint')
info = api.namespace('info', description='information about deployment')

# models
key_model = api.model('openstack key pair', {
    'key_pair_name': fields.String(required=True, description="Name of xOpera REST API's  private/public key pair"),
    'public_key': fields.String(required=True, description="Rest api's public key")
})

blueprint_metadata_model = api.model('blueprint_metadata', {
    'message': fields.String(required=True, description="return message"),
    "blueprint_token": fields.String(required=True, description="token of blueprint"),
    "session_token": fields.String(required=False, description="token of deploying session"),
    "version_tag": fields.Integer(required=True, description="version_tag blueprint"),
    "timestamp": fields.DateTime(required=True, description="timestamp of database entry")
})

delete_metadata_model = api.model('delete_metadata', {
    'message': fields.String(required=True, description="return message"),
    "blueprint_token": fields.String(required=True, description="token of blueprint"),
    "version_tag": fields.Integer(required=True, description="id of current version of blueprint"),
    # "timestamp": fields.DateTime(required=True, description="timestamp of database entry"),
    "deleted_database_entries": fields.Integer(required=True, description="Number of deleted entries"),
    "force": fields.Boolean(required=True, description="did we do it with force or not")
})

just_message_model = api.model('just_message', {
    "message": fields.String(required=True, description="return message")
})

collaborators_list_model = api.model('collaborators_list', {
    'message': fields.String(required=True, description="return message"),
    'blueprint_token': fields.String(required=True, description="token of blueprint"),
    'repo_url': fields.String(required=True, description="Url to repository"),
    'collaborators': fields.List(fields.String(required=True, description="Collaborator"),
                                 required=True, description='List of collaborators')

})

error_msg_model = api.model('error_msg', {
    'description': fields.String(required=True, description="Error description"),
    'stacktrace': fields.String(required=True, description="Exception stacktrace")
})

# CSAR parser
csar_parser = api.parser()
csar_parser.add_argument('CSAR', location='files', type=FileStorage, required=True,
                         help='TOSCA Cloud Service Archive')
csar_parser.add_argument('revision_msg', type=str, help='Optional comment on submission', required=False)
# csar_parser.add_argument('username', type=str, help='username to assign top repo', required=False)

# CSAR delete parser
csar_delete_parser = api.parser()
csar_delete_parser.add_argument('version_tag', type=str, help='version_tag to delete', required=False)
csar_delete_parser.add_argument('force', type=inputs.boolean, help='force delete blueprint', required=False)


@ssh.route('/keys/public')
class PublicKey(Resource):

    @ssh.response(404, "ssh key pair missing", just_message_model)
    @ssh.response(200, 'OK', key_model)
    def get(self):
        key_name = Settings.key_pair
        try:
            with (Settings.ssh_keys_location / Path(f"{key_name}.pubk")).open('r') as file:
                file_string = "".join(file.readlines())

                return {"key_pair_name": key_name, "public_key": file_string}, 200
        except FileNotFoundError:
            if Settings.key_pair == "":
                return {"message": "Openstack ssh key pair missing"}, 404
            return {"message": "Public key {} not found".format(key_name)}, 404


@info.route('/log/deployment')
class DeployLog(Resource):

    @info.param('session_token', 'token of session')
    @info.param('blueprint_token', 'token of blueprint')
    @info.response(400, "Log file not found", just_message_model)
    @info.response(200, 'OK')  # , log_model)
    def get(self):
        session_token = request.args.get('session_token')
        blueprint_token = request.args.get('blueprint_token')

        data = SQL_database.get_deployment_log(blueprint_token=blueprint_token, session_token=session_token)
        return_data = [{timestamp_util.datetime_to_str(_data[0]): json.loads(_data[1])} for _data in data]
        return_data.sort(key=lambda x: list(x.keys())[0], reverse=True)
        if not return_data:
            return {"message": "Log file not found"}, 400
        return return_data, 200


@info.route('/log/git/<string:blueprint_token>')
class GitLog(Resource):
    git_log_parser = api.parser()
    git_log_parser.add_argument('version_tag', type=str, help='version_tag of blueprint', required=False)
    git_log_parser.add_argument('all', type=inputs.boolean, help='show all database entries, not just last one', required=False)

    @info.expect(git_log_parser)
    @info.response(400, "Log file not found", just_message_model)
    @info.response(200, 'OK')  # , log_model)
    def get(self, blueprint_token):

        args = GitLog.git_log_parser.parse_args()
        version_tag = args.get('version_tag')
        all = args.get('all')

        data = SQL_database.get_git_transaction_data(blueprint_token=blueprint_token, version_tag=version_tag, all=all)
        if not data:
            return {"message": "Log file not found"}, 400
        return data, 200


@info.route('/status')
class Status(Resource):

    @info.param('token', 'session_token')
    @info.param('format', 'long or short')
    @info.response(500, "Job failed")
    @info.response(201, 'Job done')  # , log_model)
    @info.response(202, 'Job accepted, still running')  # , log_model)
    def get(self):
        session_token = request.args.get('token')
        return_format = request.args.get('format')

        log.debug("session_token: '{}'".format(session_token))

        json_output, status_code = info_service.check_status(session_token=session_token, format=return_format)
        log.debug(json.dumps(json_output, indent=2, sort_keys=True))
        return json_output, status_code


@deploy.route('/<string:blueprint_token>')
@deploy.param('blueprint_token', 'token of blueprint')
class Deploy(Resource):
    upload_parser = api.parser()
    upload_parser.add_argument('inputs_file', location='files', type=FileStorage, required=False,
                               help='File with inputs for TOSCA template')
    upload_parser.add_argument('version_tag', type=str, help='version_tag to deploy')

    @deploy.expect(upload_parser)
    @deploy.response(202, 'Deploy job accepted', blueprint_metadata_model)
    @deploy.response(404, 'Did not find blueprint', just_message_model)
    def post(self, blueprint_token):

        args = Deploy.upload_parser.parse_args()
        version_tag = args.get('version_tag')
        file = args.get('inputs_file')

        session_token = uuid.uuid4()
        location = xopera_util.deployment_location(session_token=session_token, blueprint_token=blueprint_token)
        log.debug(f"Deploy_location: {location}")

        if CSAR_db.get_revision(blueprint_token=blueprint_token, dst=location, version_tag=version_tag) is None:
            return {"message": 'Did not find blueprint with token: {} and version_id: {} '.format(
                blueprint_token, version_tag or 'any')}, 404

        xopera_util.save_version_tag(deploy_location=location, version_tag=version_tag)

        xopera_service.deploy(deployment_location=location, inputs_file=file)

        log.info("Deploying '{}', session_token: {}".format(blueprint_token, session_token))

        response = {
            "message": "Deploy job started, check status via /info/status endpoint",
            "session_token": str(session_token),
            "blueprint_token": str(blueprint_token),
            "version_tag": version_tag or "last",
            "timestamp": timestamp_util.datetime_now_to_string()
        }
        return response, 202

    @deploy.expect(upload_parser)
    @deploy.response(202, 'Undeploy job accepted', blueprint_metadata_model)
    @deploy.response(404, 'Did not find blueprint', just_message_model)
    @deploy.response(403, 'Undeploy not allowed', just_message_model)
    def delete(self, blueprint_token):

        args = Deploy.upload_parser.parse_args()
        version_tag = args.get('version_tag')
        file = args.get('inputs_file')

        session_token = uuid.uuid4()
        location = xopera_util.deployment_location(session_token=session_token, blueprint_token=blueprint_token)
        log.debug(f"Undeploy_location: {location}")

        if CSAR_db.get_revision(blueprint_token=blueprint_token, dst=location, version_tag=version_tag) is None:
            return {"message": 'Did not find blueprint with token: {} and version_id: {} '.format(
                blueprint_token, version_tag or 'any')}, 404

        last_message, error = CSAR_db.get_last_commit_msg(blueprint_token)
        if last_message is not None:
            if git_util.after_job_commit_msg(token=blueprint_token, mode='deploy') not in last_message:
                return {"message": f"Blueprint with token: {blueprint_token}, and version_tag: {version_tag or 'any'} "
                                   f"has not been deployed yet, cannot undeploy"}, 403

        xopera_util.save_version_tag(deploy_location=location, version_tag=version_tag)

        xopera_service.undeploy(deployment_location=location, inputs_file=file)

        log.info("Undeploying '{}', session_token: {}".format(blueprint_token, session_token))

        response = {
            "message": "Undeploy job started, check status via /info/status endpoint",
            "session_token": str(session_token),
            "blueprint_token": str(blueprint_token),
            "version_tag": version_tag or "last",
            "timestamp": timestamp_util.datetime_now_to_string()
        }
        return response, 202


@manage.route('/<string:blueprint_token>/user')
@manage.param('blueprint_token', 'token of blueprint')
class GitUserManage(Resource):
    user_parser = api.parser()
    user_parser.add_argument('username', type=str, required=True,
                             help='username of user to be added to repository with blueprint')

    @manage.expect(user_parser)
    @manage.response(201, 'invite sent', just_message_model)
    @manage.response(404, 'blueprint not found', just_message_model)
    @manage.response(500, 'DB error when adding user', error_msg_model)
    def post(self, blueprint_token):

        args = GitUserManage.user_parser.parse_args()
        username = args.get('username')
        if not CSAR_db.check_token_exists(blueprint_token=blueprint_token):
            return f"Blueprint with token {blueprint_token} does not exist", 404

        success, error_msg = CSAR_db.add_member_to_blueprint(blueprint_token=blueprint_token, username=username)
        if success:
            return f"invite for user {username} sent" if Settings.git_config[
                                                             'type'] == 'github' else f"user {username} added", 201
        response = {
            'description': f"Could not add user {username} to repository with blueprint_id '{blueprint_token}'",
            'stacktrace': error_msg
        }
        return response, 500

    @manage.response(200, 'user list returned', just_message_model)
    @manage.response(404, 'blueprint not found', collaborators_list_model)
    @manage.response(500, 'DB error when getting user list', error_msg_model)
    def get(self, blueprint_token):
        if not CSAR_db.check_token_exists(blueprint_token=blueprint_token):
            return f"Blueprint with token {blueprint_token} does not exist", 404

        user_list, error_msg = CSAR_db.get_blueprint_user_list(blueprint_token=blueprint_token)

        repo_url, repo_error_msg = CSAR_db.get_repo_url(blueprint_token=blueprint_token)

        if user_list is not None and repo_url is not None:
            response = {
                'message': f'Found {len(user_list)} collaborators for repo with blueprint_token {blueprint_token}',
                'blueprint_token': str(blueprint_token),
                'repo_url': repo_url,
                'collaborators': user_list
            }
            return response, 200
        response = {
            'description': f"Could not retrieve list of users for repository with blueprint_id '{blueprint_token}'",
            'stacktrace': error_msg or repo_error_msg
        }
        return response, 500


@manage.param('blueprint_token', 'token of blueprint')
@manage.route('/<string:blueprint_token>')
class ManageCsar(Resource):
    """
    @manage.param('version_tag', 'version_tag of blueprint')
    # @manage.response(200, 'Blueprint found, returned', blueprint_model)
    # @manage.response(404, 'Blueprint not found', just_message_model)
    # @manage.representation('application/zip')
    @manage.produces(['application/zip'])
    def get(self, blueprint_token):

        args = parser.parse_args()

        version_tag = args.get('version_id')

        path = CSAR_db.get_revision_as_CSAR(blueprint_token=blueprint_token, dst=Path(f'/tmp/{uuid.uuid4()}'),
                                            version_tag=version_tag)
        if path is not None:
            # deployment.print_metadata()
            return send_file(path, as_attachment=True, attachment_filename=f'{blueprint_token}-CSAR.zip', mimetype='application/zip'), 200
        else:
            return {"message": 'Did not find blueprint with token: {} and version_id: {} '.format(
                blueprint_token, version_tag or 'any')}, 404

    """

    @manage.expect(csar_delete_parser)
    @manage.response(200, 'Successfully removed', delete_metadata_model)
    @manage.response(404, 'Blueprint not found', delete_metadata_model)
    @manage.response(403, 'Did not undeploy yet, not allowed', just_message_model)
    def delete(self, blueprint_token):
        args = csar_delete_parser.parse_args()

        version_tag = args.get('version_tag')
        force = args.get('force')

        if not force:
            last_message, _ = CSAR_db.get_last_commit_msg(blueprint_token)
            if last_message is not None:
                if git_util.after_job_commit_msg(token=blueprint_token, mode='deploy') in last_message:
                    log.info('Cannot delete, undeploy not done yet')
                    return {"message": "Cannot delete, deployment has not been undeployed yet"}, 403

        repo_url, _ = CSAR_db.get_repo_url(blueprint_token)

        rows_affected, status_code = CSAR_db.delete_blueprint(blueprint_token, version_tag)
        log.debug(f"Rows affected, status_code: {rows_affected} {status_code}")

        if status_code == 200:
            version_tags = [version_tag] if version_tag else SQL_database.get_version_tags(blueprint_token)
            for tag in version_tags:

                SQL_database.save_git_transaction_data(blueprint_token=blueprint_token,
                                                       version_tag=tag,
                                                       revision_msg=f"Deleted {'one version of ' if version_tag else ''}blueprint",
                                                       job='delete',
                                                       git_backend=str(CSAR_db.connection.git_connector),
                                                       repo_url=repo_url)

        delete_metadata = dict()

        if status_code == 200:
            delete_metadata["message"] = 'Successfully removed'
            if not version_tag:
                rows_affected = 'all'
        elif status_code == 404:
            if rows_affected == 0:
                delete_metadata["message"] = 'Tag not found'
            else:
                delete_metadata["message"] = 'Blueprint not found'
        else:  # status code 500
            delete_metadata["message"] = 'Server error'

        delete_metadata["blueprint_token"] = blueprint_token
        delete_metadata["version_tag"] = version_tag or 'all'
        delete_metadata["deleted_database_entries"] = rows_affected
        delete_metadata["force"] = force or False

        return delete_metadata, status_code

    @manage.expect(csar_parser)
    @manage.response(200, 'Successfully saved blueprint to database', blueprint_metadata_model)
    @manage.response(404, 'Blueprint token not found', just_message_model)
    @manage.response(406, 'Format not acceptable', just_message_model)
    def post(self, blueprint_token):
        args = csar_parser.parse_args()
        file = args.get('CSAR')
        message = args.get('revision_msg')

        if not CSAR_db.check_token_exists(blueprint_token):
            return {"message": "Blueprint token does not exist, 'manage' route instead"}, 404

        result, response = CSAR_db.add_revision(CSAR=file, revision_msg=message, blueprint_token=blueprint_token)

        if result is None:
            return {"message": f"Invalid CSAR: {response}"}, 406

        SQL_database.save_git_transaction_data(blueprint_token=result['blueprint_token'],
                                               version_tag=result['version_tag'],
                                               revision_msg=f"Updated blueprint: {message}",
                                               job='update',
                                               git_backend=str(CSAR_db.connection.git_connector),
                                               repo_url=result['url'],
                                               commit_sha=result['commit_sha'])

        return result, 200


@manage.route("")
class NewBlueprintCsar(Resource):
    @manage.response(200, 'Successfully saved blueprint to database', blueprint_metadata_model)
    @manage.response(406, 'Format not acceptable', just_message_model)
    @manage.expect(csar_parser)
    def post(self):
        args = csar_parser.parse_args()
        file = args.get('CSAR')
        message = args.get('revision_msg')

        result, response = CSAR_db.add_revision(CSAR=file, revision_msg=message)

        if result is None:
            return {"message": f"Invalid CSAR: {response}"}, 406

        SQL_database.save_git_transaction_data(blueprint_token=result['blueprint_token'],
                                               version_tag=result['version_tag'],
                                               revision_msg=f"Saved new blueprint: {message}",
                                               job='update',
                                               git_backend=str(CSAR_db.connection.git_connector),
                                               repo_url=result['url'],
                                               commit_sha=result['commit_sha'])

        return result, 200


if __name__ == '__main__':
    flask_app.run(debug=False, host='0.0.0.0')
