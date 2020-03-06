import json
import logging as log
import uuid
import argparse

import psycopg2
from flask import Flask, request
from flask_restplus import Api, Resource, fields, reqparse, inputs
from werkzeug.datastructures import FileStorage

from deployment_preparation import deployment_io
from deployment_preparation import xopera_link
from deployment_preparation.deployment_io import PostgreSQL, OfflineStorage
from deployment_preparation.dp_types import Deployment
from deployment_preparation.settings import Settings

Settings.load_settings()
print('RESTapi verbose: {}'.format('True' if Settings.verbose else 'False'))
deployment_io.clean_deployment_data()
deployment_io.configure_ssh_keys()

parser = argparse.ArgumentParser(description='xOpera REST API')
parser.add_argument('--interpreter', help="Custom path to python interpreter", type=str, default='python3')
args = parser.parse_args()
Settings.interpreter = args.interpreter
print(f'Interpreter: {Settings.interpreter}')

try:
    database = PostgreSQL(Settings.connection)
    log.info('Database: PostgreSQL')
except psycopg2.Error:
    database = OfflineStorage()
    log.info("Database: OfflineStorage")

flask_app = Flask(__name__)
api = Api(app=flask_app, version='beta', title="xOpera REST api",
          description="Standard scenarios of using REST api:\n\n"
                      "FIRST RUN\n"

                      "- GET key pair via ssh/keys/public download and register it on your openstack\n\n"
                      "DEPLOY\n"
                      "1) upload blueprint with POST to /manage\n - new version of existing one must be POSTed to "
                      "/manage/{blueprint_token}\n - save blueprint_metadata, returned by API call -> it is the only "
                      "way of "
                      "accessing your blueprint afterwards\n "
                      "2) deploy last version of blueprint with POST to /deploy/{blueprint_token}\n"
                      "- optionally, inputs file to be used with template must also be uploaded within same API call\n"
                      "- another version can be specified by version_id or timestamp\n"
                      "- save session_token\n"
                      "3) using status_token from with GET to /info/status check status of your job\n"
                      "4) After completion, check logs with GET to /info/log\n\n"
                      "UNDEPLOY\n"
                      "1) undeploy blueprint with DELETE to /deploy/{blueprint_token}\n"
                      "- optionally, inputs file to be used with template must also be uploaded within same API call\n"
                      " - optionally also in combination with version_id or timestamp\n - save session_token\n "
                      "2) using status_token with GET to /info/status check status of your job\n"
                      "3) After completion, check logs with GET to /info/log\n"
                      "4) Delete all versions of blueprint from database with DELETE to /manage/{blueprint_token}\n"
                      "- to delete just specific version, use version_id or timestamp\n"
                      "- if deployment from template has not been undeployed yet, blueprint cannot be deleted"
                      "-> use 'force' to override\n"
          )

# namespaces
ssh = api.namespace('ssh', description='SSH key management')
manage = api.namespace('manage', description='save or view blueprint')
manage_csar = api.namespace('manage_csar', description='save or view blueprint in csar format')
deploy = api.namespace('deploy', description='deploy or undeploy blueprint')
info = api.namespace('info', description='information about deployment')

# models
tosca_model = api.model('tosca_definition', {
    'name': fields.String(required=True, description='Name of file with TOSCA definition'),
    'type': fields.String(required=True, description='must be set to "file" '),
    'content': fields.String(required=True, description='Content of file with TOSCA definition')
})

ansible_model = api.model('ansible_definition', {
    'name': fields.String(required=True, description='Name of folder or file with ansible playbooks'),
    'type': fields.String(required=True, description='must be set to "dir" or "file"'),
    'content': fields.Raw(required=True, description='Content of file / dir')
})

blueprint_model = api.model('blueprint', {
    'blueprint_id': fields.String(required=True, description='name of blueprint'),
    'tosca_definition': fields.Nested(tosca_model, required=True, description="TOSCA file"),
    'ansible_definition': fields.Nested(ansible_model, required=True, description="Ansible file or folder"),
    'config_script': fields.String(required=False, description="Vendor configuration script (openrc.sh)"),
    'timestamp': fields.DateTime(required=True, description="timestamp of blueprint")
})

key_model = api.model('openstack key pair', {
    'key_pair_name': fields.String(required=True, description="Name of xOpera REST API's  private/public key pair"),
    'public_key': fields.String(required=True, description="Rest api's public key")
})

blueprint_metadata_model = api.model('blueprint_metadata', {
    'message': fields.String(required=True, description="return message"),
    "id": fields.String(required=True, description="id of blueprint"),
    "blueprint_token": fields.String(required=True, description="token of blueprint"),
    "session_token": fields.String(required=False, description="token of deploying session"),
    "version_id": fields.Integer(required=True, description="id of current version of blueprint"),
    "timestamp": fields.DateTime(required=True, description="timestamp of database entry")
})

delete_metadata_model = api.model('delete_metadata', {
    'message': fields.String(required=True, description="return message"),
    "blueprint_token": fields.String(required=True, description="token of blueprint"),
    "version_id": fields.Integer(required=True, description="id of current version of blueprint"),
    "timestamp": fields.DateTime(required=True, description="timestamp of database entry"),
    "deleted_database_entries": fields.Integer(required=True, description="Number of deleted entries"),
    "force": fields.Boolean(required=True, description="did we do it with force or not")
})

just_message_model = api.model('just_message', {
    "message": fields.String(required=True, description="return message")
})

# args parser
parser = reqparse.RequestParser()
parser.add_argument('timestamp', type=inputs.datetime_from_iso8601, help='timestamp of blueprint version')
parser.add_argument('version_id', type=int, help='id of blueprint version')
parser.add_argument('force', type=inputs.boolean, help='force delete blueprint')

# CSAR parser
csar_parser = api.parser()
csar_parser.add_argument('CSAR', location='files', type=FileStorage, required=True,
                         help='TOSCA Cloud Service Archive')


@ssh.route('/keys/public')
class PublicKey(Resource):

    @ssh.response(404, "ssh key pair missing", just_message_model)
    @ssh.response(200, 'OK', key_model)
    def get(self):
        key_name = Settings.key_pair
        try:
            with open("{}{}.pubk".format(Settings.ssh_keys_location, key_name), 'r') as file:
                file_string = "".join(file.readlines())

                return {"key_pair_name": key_name, "public_key": file_string}, 200
        except FileNotFoundError:
            if Settings.key_pair == "":
                return {"message": "Openstack ssh key pair missing"}, 404
            return {"message": "Public key {} not found".format(key_name)}, 404


@info.route('/log')
class Log(Resource):

    @info.param('session_token', 'token of session')
    @info.param('blueprint_token', 'token of blueprint')
    @info.response(400, "Log file not found", just_message_model)
    @info.response(200, 'OK')  # , log_model)
    def get(self):
        session_token = request.args.get('session_token')
        blueprint_token = request.args.get('blueprint_token')

        data = database.get_deployment_log(blueprint_token=blueprint_token, session_token=session_token)
        return_data = [{Settings.datetime_to_str(_data[0]): json.loads(_data[1])} for _data in data]
        return_data.sort(key=lambda x: list(x.keys())[0], reverse=True)
        if not return_data:
            return {"message": "Log file not found"}, 400
        return return_data, 200


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

        log.info("session_token: '{}'".format(session_token))

        json_output, status_code = xopera_link.check_status(token=session_token, format=return_format)
        log.info(json.dumps(json_output, indent=2, sort_keys=True))
        return json_output, status_code


@deploy.route('/<string:blueprint_token>')
@deploy.param('blueprint_token', 'token of blueprint')
class Deploy(Resource):
    upload_parser = api.parser()
    upload_parser.add_argument('inputs_file', location='files', type=FileStorage, required=False,
                               help='File with inputs for TOSCA template')
    upload_parser.add_argument('timestamp', type=inputs.datetime_from_iso8601, help='timestamp of blueprint version')
    upload_parser.add_argument('version_id', type=int, help='id of blueprint version')

    @deploy.expect(upload_parser)
    # @deploy.param('timestamp', 'timestamp of blueprint')
    # @deploy.param('version_id', 'version_id of blueprint')
    @deploy.response(202, 'Deploy job accepted', blueprint_metadata_model)
    @deploy.response(404, 'Did not find blueprint', just_message_model)
    def post(self, blueprint_token):

        args = Deploy.upload_parser.parse_args()
        timestamp = args.get('timestamp')
        version_id = args.get('version_id')
        file = args.get('inputs_file')

        deployment = database.get_revision(blueprint_token, timestamp, version_id)
        if deployment is None:
            return {"message": 'Did not find blueprint with token: {}, timestamp: {} and version_id: {} '.format(
                blueprint_token, timestamp or 'any', version_id or 'any')}, 404

        session_token = xopera_link.deploy_by_token(blueprint_token=blueprint_token, deployment=deployment,
                                                    inputs_file=file)

        message = "Deploying '{}', session_token: {}".format(blueprint_token, session_token)
        log.info(message)

        deploy_meta = dict()
        deploy_meta["message"] = "Deploy job started, check status via /info/status endpoint"
        deploy_meta["session_token"] = str(session_token)
        blueprint_meta = deployment.metadata()

        return {**deploy_meta, **blueprint_meta}, 202

    @deploy.expect(upload_parser)
    # @deploy.param('timestamp', 'timestamp of blueprint')
    # @deploy.param('version_id', 'version_id of blueprint')
    @deploy.response(202, 'Undeploy job accepted', blueprint_metadata_model)  # , log_model)
    @deploy.response(404, 'Did not find blueprint', just_message_model)
    def delete(self, blueprint_token):

        args = Deploy.upload_parser.parse_args()
        timestamp = args.get('timestamp')
        version_id = args.get('version_id')
        file = args.get('inputs_file')

        deployment, last_deployment_data = database.get_last_deployment_data(blueprint_token, timestamp, version_id)
        if not deployment:
            return {"message": 'Did not find blueprint with token: {}, timestamp: {} and version_id: {} '.format(
                blueprint_token, timestamp or 'any', version_id or 'any')}, 404

        if not last_deployment_data:
            return {
                       "message": 'Blueprint with token: {}, timestamp: {} and version_id: {} has not been deployed yet '.format(
                           blueprint_token, timestamp or 'any', version_id or 'any')}, 404

        session_token = xopera_link.undeploy_by_token(blueprint_token=blueprint_token, blueprint_id=deployment.id,
                                                      blueprint_timestamp=deployment.timestamp,
                                                      directory=last_deployment_data, inputs_file=file)

        message = "Undeploying '{}', session_token: {}".format(blueprint_token, session_token)
        log.info(message)

        deploy_meta = dict()
        deploy_meta["message"] = "Undeploy job started, check status via /info/status endpoint"
        deploy_meta["session_token"] = str(session_token)
        blueprint_meta = deployment.metadata()

        return {**deploy_meta, **blueprint_meta}, 202


@manage.param('blueprint_token', 'token of blueprint')
@manage.route('/<string:blueprint_token>')
class Manage(Resource):

    @manage.param('timestamp', 'timestamp of blueprint')
    @manage.param('version_id', 'version_id of blueprint')
    @manage.response(200, 'Blueprint found, returned', blueprint_model)
    @manage.response(404, 'Blueprint not found', just_message_model)
    def get(self, blueprint_token):

        args = parser.parse_args()

        timestamp = args.get('timestamp')
        version_id = args.get('version_id')

        deployment = database.get_revision(blueprint_token, timestamp, version_id)
        if deployment is not None:
            deployment.print_metadata()
            return deployment.to_dict(), 200
        else:
            return {"message": 'Did not find blueprint with token: {}, timestamp: {} and version_id: {} '.format(
                blueprint_token, timestamp or 'any', version_id or 'any')}, 404

    @manage.expect(blueprint_model, validate=False)
    @manage.response(200, 'Successfully saved blueprint to database', blueprint_metadata_model)
    @manage.response(404, 'Blueprint token not found', just_message_model)
    @manage.response(406, 'Format not acceptable', just_message_model)
    def post(self, blueprint_token):
        json_input = request.get_json()

        if not database.check_token_exists(blueprint_token):
            return {"message": "Blueprint token does not exist, 'manage' route instead"}, 404
        try:
            blueprint_name = json_input["blueprint_id"]
            invalid_name, response = deployment_io.validate_blueprint_name(blueprint_name)
            # if invalid_name:
            #     return {"message": "blueprint id {} invalid. Must comply with RFC 1123 (section 2.1)"
            #                        "and RFC 952"}, 406
        except Exception:
            pass

        deployment = Deployment.from_dict(blueprint_token=blueprint_token, dictionary=json_input)

        invalid_tosca, response = deployment_io.validate_tosca(deployment)
        if invalid_tosca:
            return {
                       "message": f"Invalid TOSCA: {response}"}, 406

        if deployment is not None:
            version_id = database.get_max_version_id(blueprint_token) + 1
            database.add_revision(deploy=deployment, version_id=version_id)
            timestamp = database.get_timestamp(blueprint_token=blueprint_token, version_id=version_id)
            return {
                       'message': "Saved blueprint to database",
                       "id": deployment.id,
                       "blueprint_token": str(blueprint_token),
                       "version_id": version_id,
                       "timestamp": Settings.datetime_to_str(timestamp)
                   }, 200
        else:
            return {"message": "Format not acceptable!"}, 406

    @manage.param('timestamp', 'timestamp of blueprint')
    @manage.param('version_id', 'version_id of blueprint')
    @manage.param('force', 'force delete (bool)')
    @manage.response(200, 'Successfully removed', delete_metadata_model)
    @manage.response(404, 'Blueprint not found', delete_metadata_model)
    @manage.response(403, 'Did not undeploy yet, not allowed', just_message_model)
    def delete(self, blueprint_token):
        args = parser.parse_args()

        timestamp = args.get('timestamp')
        version_id = args.get('version_id')
        force = args.get('force')

        if not force:
            last_job = database.last_job(blueprint_token=blueprint_token, timestamp=timestamp, version_id=version_id)

            if last_job == 'deploy':
                log.info('Cannot delete, undeploy not done yet')
                return {"message": "Cannot delete, deployment has not been undeployed yet"}, 403

        rows_affected = database.delete_blueprint(blueprint_token, timestamp, version_id)

        delete_metadata = dict()

        if rows_affected != 0:
            status_code = 200
            delete_metadata["message"] = 'Successfully removed'
        else:
            status_code = 404
            delete_metadata["message"] = 'Blueprint(s) not found'

        delete_metadata["blueprint_token"] = blueprint_token
        delete_metadata["version_id"] = version_id or 'any'
        delete_metadata["timestamp"] = 'any' if timestamp is None else Settings.datetime_to_str(timestamp)
        delete_metadata["deleted_database_entries"] = rows_affected
        delete_metadata["force"] = force or False

        return delete_metadata, status_code


@manage.route("")
class NewBlueprint(Resource):
    @manage.response(200, 'Successfully saved blueprint to database', blueprint_metadata_model)
    @manage.response(406, 'Format not acceptable', just_message_model)
    @manage.expect(blueprint_model, validate=False)
    def post(self):
        json_input = request.get_json()
        blueprint_token = uuid.uuid4()
        version_id = database.get_max_version_id(str(blueprint_token)) + 1

        try:
            blueprint_name = json_input["blueprint_id"]
            invalid_name, response = deployment_io.validate_blueprint_name(blueprint_name)
            # if invalid_name:
            #     return {"message": "blueprint id {} invalid. Must comply with RFC 1123 (section 2.1)"
            #                        "and RFC 952"}, 406
        except Exception:
            pass

        deployment = Deployment.from_dict(blueprint_token=blueprint_token, dictionary=json_input)
        invalid_tosca, response = deployment_io.validate_tosca(deployment)
        if invalid_tosca:
            return {
                       "message": f"Invalid TOSCA: {response}"}, 406

        if deployment is not None:
            database.add_revision(deploy=deployment, version_id=version_id)
            timestamp = database.get_timestamp(blueprint_token=str(blueprint_token), version_id=version_id)
            return {
                       'message': "Saved blueprint to database",
                       "id": deployment.id,
                       "blueprint_token": str(blueprint_token),
                       "version_id": version_id,
                       "timestamp": Settings.datetime_to_str(timestamp)
                   }, 200
        else:
            return {
                       "message": "Format not acceptable!"
                   }, 406


@manage_csar.param('blueprint_token', 'token of blueprint')
@manage_csar.route('/<string:blueprint_token>')
class ManageCsar(Resource):

    @manage_csar.expect(csar_parser)
    @manage_csar.response(200, 'Successfully saved blueprint to database', blueprint_metadata_model)
    @manage_csar.response(404, 'Blueprint token not found', just_message_model)
    @manage_csar.response(406, 'Format not acceptable', just_message_model)
    def post(self, blueprint_token):
        args = csar_parser.parse_args()
        file = args.get('CSAR')

        if not database.check_token_exists(blueprint_token):
            return {"message": "Blueprint token does not exist, 'manage' route instead"}, 404

        # deployment = Deployment.from_dict(blueprint_token=blueprint_token, dictionary=json_input)
        deployment = Deployment.from_csar(blueprint_token=blueprint_token, CSAR=file)

        invalid_tosca, response = deployment_io.validate_tosca(deployment)
        if invalid_tosca:
            return {
                       "message": f"Invalid TOSCA: {response}"}, 406

        if deployment is not None:
            version_id = database.get_max_version_id(blueprint_token) + 1
            database.add_revision(deploy=deployment, version_id=version_id)
            timestamp = database.get_timestamp(blueprint_token=blueprint_token, version_id=version_id)
            return {
                       'message': "Saved blueprint to database",
                       "id": deployment.id,
                       "blueprint_token": str(blueprint_token),
                       "version_id": version_id,
                       "timestamp": Settings.datetime_to_str(timestamp)
                   }, 200
        else:
            return {"message": "Format not acceptable!"}, 406


@manage_csar.route("")
class NewBlueprintCsar(Resource):
    @manage_csar.response(200, 'Successfully saved blueprint to database', blueprint_metadata_model)
    @manage_csar.response(406, 'Format not acceptable', just_message_model)
    @manage_csar.expect(csar_parser)
    def post(self):
        args = csar_parser.parse_args()
        file = args.get('CSAR')
        blueprint_token = uuid.uuid4()
        version_id = database.get_max_version_id(str(blueprint_token)) + 1

        deployment = Deployment.from_csar(blueprint_token=blueprint_token, CSAR=file)
        invalid_tosca, response = deployment_io.validate_tosca(deployment)
        if invalid_tosca:
            return {
                       "message": f"Invalid TOSCA: {response}"}, 406

        if deployment:
            database.add_revision(deploy=deployment, version_id=version_id)
            timestamp = database.get_timestamp(blueprint_token=str(blueprint_token), version_id=version_id)
            return {
                       'message': "Saved blueprint to database",
                       "id": deployment.id,
                       "blueprint_token": str(blueprint_token),
                       "version_id": version_id,
                       "timestamp": Settings.datetime_to_str(timestamp)
                   }, 200
        else:
            return {
                       "message": "Format not acceptable!"
                   }, 406


if __name__ == '__main__':
    flask_app.run(debug=False, host='0.0.0.0')
