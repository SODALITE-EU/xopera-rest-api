import uuid

import validators
from assertpy import assert_that

from opera.api.util import timestamp_util


class TestPostNew:

    def test_no_domain(self, client, csar_empty, mocker):
        mocker.patch('opera.api.controllers.security_controller.check_roles', return_value=False)
        domain = '42'
        resp = client.post(f"/blueprint?project_domain={domain}", data=csar_empty, content_type='multipart/form-data')
        assert_that(resp.status_code).is_equal_to(401)
        assert_that(resp.json).contains('Unauthorized request')

    def test_empty(self, client, csar_empty):
        resp = client.post("/blueprint", data=csar_empty, content_type='multipart/form-data')
        assert_that(resp.status_code).is_equal_to(406)
        assert_that(resp.json).is_not_none().contains("Invalid CSAR")

    def test_no_metadata(self, client, csar_no_meta):
        resp = client.post("/blueprint", data=csar_no_meta, content_type='multipart/form-data')
        assert_that(resp.status_code).is_equal_to(406)
        assert_that(resp.json).is_not_none().contains("Invalid CSAR")

    def test_db_fail(self, client, csar_empty, mocker):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.save_blueprint_meta', return_value=False)
        mocker.patch('opera.api.controllers.security_controller.check_roles', return_value=True)
        mocker.patch('opera.api.service.csardb_service.GitDB.add_revision', return_value=({'blueprint_id': 'a'}, None))
        domain = '42'
        resp = client.post(f"/blueprint?project_domain={domain}", data=csar_empty, content_type='multipart/form-data')
        assert_that(resp.status_code).is_equal_to(500)
        assert_that(resp.json).contains('Failed to save project data')

    def test_success(self, client, csar_1, mocker):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.save_blueprint_meta', return_value=True)
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.save_git_transaction_data')
        mocker.patch('opera.api.controllers.security_controller.check_roles', return_value=True)
        mocker.patch('opera.api.service.csardb_service.GitDB.add_revision', return_value=(
            {
                'message': "Revision saved to GitDB",
                'blueprint_id': uuid.uuid4(),
                'url': 'https://google.com',
                'commit_sha': 'commit_sha',
                'version_id': 'v1.0',
                'users': ['xopera'],
                'timestamp': timestamp_util.datetime_now_to_string()
            }, None))
        revision_msg = 'Another blueprint'
        name = 'Test blueprint'
        aadm_id = str(uuid.uuid4())
        username = 'mihaTrajbaric'
        project_domain = 'SODALITE'
        resp = client.post(f"/blueprint?revision_msg={revision_msg}&blueprint_name={name}&aadm_id={aadm_id}"
                           f"&username={username}&project_domain={project_domain}", data=csar_1)
        assert_that(resp.status_code).is_equal_to(201)
        assert_that(resp.json).is_not_none().contains_only('blueprint_id', 'version_id', 'blueprint_name', 'aadm_id',
                                                           'url',
                                                           'project_domain', 'username', 'commit_sha', 'timestamp')
        uuid.UUID(resp.get_json()['blueprint_id'])

        assert_that(resp.get_json()['version_id']).is_equal_to('v1.0')

        validators.url(resp.get_json()['url'])


class TestPostMultipleVersions:

    def test_wrong_token(self, client, csar_1, mocker):
        blueprint_id = uuid.uuid4()
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.version_exists', return_value=False)
        resp = client.post(f"/blueprint/{blueprint_id}", data=csar_1)
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json).is_not_none().contains("Did not find blueprint")

    def test_unauthorized(self, client, csar_1, mocker):
        blueprint_id = uuid.uuid4()
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.version_exists', return_value=False)
        mocker.patch('opera.api.controllers.security_controller.check_roles', return_value=False)
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_project_domain', return_value='foo')

        resp = client.post(f"/blueprint/{blueprint_id}", data=csar_1)
        assert_that(resp.status_code).is_equal_to(401)
        assert_that(resp.json).is_not_none().contains("Unauthorized request")

    def test_emtpy_request(self, client, csar_empty, mocker):
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.version_exists', return_value=True)
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_project_domain', return_value=None)
        mocker.patch('opera.api.service.csardb_service.GitDB.add_revision', return_value=(
            None, "Invalid CSAR: something missing"))
        resp = client.post(f"/blueprint/{uuid.uuid4()}", data=csar_empty, content_type='multipart/form-data')
        print(resp.json)
        assert_that(resp.status_code).is_equal_to(406)
        assert_that(resp.json).is_not_none().contains("Invalid CSAR")

    def test_project_data_saving_error(self, csar_1, client, mocker, patch_auth_wrapper):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.save_blueprint_meta', return_value=False)
        mocker.patch('opera.api.service.csardb_service.GitDB.add_revision', return_value=(
            {
                'message': "Revision saved to GitDB",
                'blueprint_id': uuid.uuid4(),
                'url': 'https://google.com',
                'commit_sha': 'commit_sha',
                'version_id': 'v2.0',
                'users': ['xopera'],
                'timestamp': timestamp_util.datetime_now_to_string()
            }, None))
        resp = client.post(f"/blueprint/{uuid.uuid4()}", data=csar_1)
        assert_that(resp.status_code).is_equal_to(500)
        assert_that(resp.json).contains('Failed to save project data')

    def test_success(self, client, csar_1, mocker, patch_auth_wrapper):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.save_blueprint_meta', return_value=True)
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.version_exists', return_value=True)
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_project_domain', return_value=None)
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.save_git_transaction_data')
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mocker.patch('opera.api.service.csardb_service.GitDB.add_revision', return_value=(
            {
                'message': "Revision saved to GitDB",
                'blueprint_id': uuid.uuid4(),
                'url': 'https://google.com',
                'commit_sha': 'commit_sha',
                'version_id': 'v2.0',
                'users': ['xopera'],
                'timestamp': timestamp_util.datetime_now_to_string()
            }, None))

        # test new version
        resp2 = client.post(f"/blueprint/{uuid.uuid4()}", data=csar_1)
        assert_that(resp2.status_code).is_equal_to(201)
        assert_that(resp2.json).is_not_none().contains_only('blueprint_id', 'url', 'version_id',
                                                            'commit_sha', 'timestamp')
        assert_that(resp2.json['version_id']).is_equal_to('v2.0')


class TestDelete:

    def test_json_keys_error(self, mocker, client, patch_db):
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=False)
        resp = client.delete(f"/blueprint/{42}")
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json).is_not_none().contains("Did not find blueprint")

    def test_json_keys_success(self, client, mocker, patch_auth_wrapper):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.blueprint_used_in_deployment', return_value=False)
        mocker.patch('opera.api.service.csardb_service.GitDB.get_repo_url', return_value=['url', None])
        mocker.patch('opera.api.service.csardb_service.GitDB.delete_blueprint', return_value=[1, 200])
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.delete_blueprint_meta')
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.save_git_transaction_data')

        resp = client.delete(f"/blueprint/{uuid.uuid4()}")
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json).is_not_none().contains_only('blueprint_id', 'timestamp', 'url')

    def test_delete_before_undeploy(self, mocker, client, patch_auth_wrapper):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.blueprint_used_in_deployment', return_value=True)

        # try to delete
        blueprint_id = uuid.uuid4()
        resp = client.delete(f"/blueprint/{blueprint_id}")
        assert_that(resp.status_code).is_equal_to(403)
        assert_that(resp.json).contains("Cannot delete blueprint, deployment with this blueprint exists")

    def test_force_delete(self, mocker, client, patch_auth_wrapper):
        repo_url = 'https://url/to/repo.git'
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.blueprint_used_in_deployment', return_value=True)
        mocker.patch('opera.api.service.csardb_service.GitDB.get_repo_url', return_value=[repo_url, None])
        mocker.patch('opera.api.service.csardb_service.GitDB.delete_blueprint', return_value=[1, 200])

        # delete blueprint
        blueprint_id = uuid.uuid4()
        resp = client.delete(f"/blueprint/{blueprint_id}?force=true")
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json['blueprint_id']).is_equal_to(str(blueprint_id))

    def test_server_error(self, client, mocker, patch_auth_wrapper):
        mocker.patch('opera.api.service.csardb_service.GitDB.delete_blueprint', return_value=[0, 500])

        blueprint_id = uuid.uuid4()
        resp = client.delete(f"/blueprint/{blueprint_id}")
        assert_that(resp.status_code).is_equal_to(500)
        assert_that(resp.json).is_equal_to('Server error')


class TestDeleteVersion:

    def test_delete_by_wrong_version_tag(self, client, mocker, patch_db):
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=False)
        blueprint_id = uuid.uuid4()
        version_id = 'v1.0'
        resp = client.delete(f"/blueprint/{blueprint_id}/version/{version_id}")
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json).contains("Did not find blueprint")

    def test_json_keys_success(self, client, mocker, patch_auth_wrapper):
        mocker.patch('opera.api.service.csardb_service.GitDB.delete_blueprint', return_value=[1, 200])
        mocker.patch('opera.api.service.csardb_service.GitDB.get_repo_url', return_value=['https://url/to/repo', None])

        blueprint_id = uuid.uuid4()
        version_id = 'v1.0'
        resp = client.delete(f"/blueprint/{blueprint_id}/version/{version_id}")

        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json).is_not_none().contains_only('blueprint_id', 'version_id', 'timestamp', 'url')
        assert uuid.UUID(resp.json['blueprint_id']) == blueprint_id
        assert resp.json['version_id'] == version_id

    def test_delete_before_undeploy(self, mocker, client, patch_auth_wrapper):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.blueprint_used_in_deployment', return_value=True)

        # try to delete
        blueprint_id = uuid.uuid4()
        version_id = 'v1.0'
        resp = client.delete(f"/blueprint/{blueprint_id}/version/{version_id}")
        assert_that(resp.status_code).is_equal_to(403)
        assert_that(resp.json).contains("Cannot delete blueprint, deployment with this blueprint exists")

    def test_force_delete(self, mocker, client, patch_auth_wrapper):
        repo_url = 'https://url/to/repo.git'
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.blueprint_used_in_deployment', return_value=True)
        mocker.patch('opera.api.service.csardb_service.GitDB.get_repo_url', return_value=[repo_url, None])
        mocker.patch('opera.api.service.csardb_service.GitDB.delete_blueprint', return_value=[1, 200])

        # delete blueprint
        blueprint_id = uuid.uuid4()
        version_id = 'v1.0'
        resp = client.delete(f"/blueprint/{blueprint_id}/version/{version_id}?force=true")
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json['blueprint_id']).is_equal_to(str(blueprint_id))
        assert_that(resp.json['version_id']).is_equal_to(version_id)

    def test_server_error(self, client, mocker, patch_auth_wrapper):
        mocker.patch('opera.api.service.csardb_service.GitDB.delete_blueprint', return_value=[0, 500])

        blueprint_id = uuid.uuid4()
        version_id = 'v1.0'
        resp = client.delete(f"/blueprint/{blueprint_id}/version/{version_id}")
        assert_that(resp.status_code).is_equal_to(500)
        assert_that(resp.json).is_equal_to('Server error')


class TestUser:

    def test_get_users_non_existing_blueprint(self, client, mocker, patch_db):
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=False)
        blueprint_token = uuid.uuid4()
        resp = client.get(f"/blueprint/{blueprint_token}/user")
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json).contains('Did not find blueprint')

    def test_get_users_git_error(self, client, mocker, patch_auth_wrapper):
        blueprint_token = uuid.uuid4()
        mocker.patch('opera.api.service.csardb_service.GitDB.get_blueprint_user_list', return_value=[None, 'Error_msg'])

        resp = client.get(f"/blueprint/{blueprint_token}/user")
        assert_that(resp.status_code).is_equal_to(500)
        assert_that(resp.json).contains('Could not retrieve list of users')

    def test_get_users_success(self, client, mocker, patch_auth_wrapper):
        blueprint_token = str(uuid.uuid4())
        user_list = ['foo', 'bar']
        mocker.patch('opera.api.service.csardb_service.GitDB.get_blueprint_user_list', return_value=[user_list, None])

        resp = client.get(f"/blueprint/{blueprint_token}/user")
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json).is_equal_to(user_list)

    def test_add_users_to_non_existing_blueprint(self, client, mocker, patch_db):
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=False)
        blueprint_token = '42'
        user_id = 'foo'
        resp = client.post(f"/blueprint/{blueprint_token}/user/{user_id}")
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json).contains('Did not find blueprint')

    def test_add_users_git_error(self, client, mocker, patch_auth_wrapper):
        blueprint_token = uuid.uuid4()
        username = 'foo'
        mocker.patch('opera.api.service.csardb_service.GitDB.check_token_exists', return_value=True)
        mocker.patch('opera.api.service.csardb_service.GitDB.add_member_to_blueprint', return_value=[None, 'Error_msg'])

        resp = client.post(f"/blueprint/{blueprint_token}/user/{username}")
        assert_that(resp.status_code).is_equal_to(500)
        assert_that(resp.json).contains('Could not add user')

    def test_add_user_success(self, client, mocker, patch_auth_wrapper):
        mocker.patch('opera.api.service.csardb_service.GitDB.add_member_to_blueprint', return_value=[True, None])
        mocker.patch('opera.api.service.csardb_service.GitDB.get_blueprint_user_list', return_value=[['foo'], None])

        username = 'foo'
        resp = client.post(f"/blueprint/{uuid.uuid4()}/user/{username}")
        # since this is MockConnector, message should be 'user foo added'
        assert_that(resp.json).is_equal_to('User foo added')
        assert_that(resp.status_code).is_equal_to(200)

        resp = client.get(f"/blueprint/{uuid.uuid4()}/user")
        assert_that(resp.json).is_not_empty().contains_only('foo')

    def test_delete_users_git_error(self, client, mocker, patch_auth_wrapper):
        blueprint_token = uuid.uuid4()
        username = 'foo'
        mocker.patch('opera.api.service.csardb_service.GitDB.check_token_exists', return_value=True)
        mocker.patch('opera.api.service.csardb_service.GitDB.delete_blueprint_user', return_value=[None, 'Error_msg'])

        resp = client.delete(f"/blueprint/{blueprint_token}/user/{username}")
        assert_that(resp.status_code).is_equal_to(500)
        assert_that(resp.json).contains('Could not delete user')

    def test_delete_user_success(self, client, mocker, patch_auth_wrapper):
        username = 'foo'
        mocker.patch('opera.api.service.csardb_service.GitDB.delete_blueprint_user', return_value=[True, None])

        resp = client.delete(f"/blueprint/{uuid.uuid4()}/user/{username}")
        assert_that(resp.json).is_equal_to(f'User {username} deleted')
        assert_that(resp.status_code).is_equal_to(200)
        resp = client.get(f"/blueprint/{uuid.uuid4()}/user")
        assert_that(resp.json).is_empty()


class TestGetBlueprintByUserOrDomain:

    def test_missing_params(self, client, mocker, patch_auth_wrapper):
        resp = client.get(f"/blueprint")
        assert_that(resp.status_code).is_equal_to(400)

    def test_no_blueprint(self, client, mocker, patch_auth_wrapper):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_blueprints_by_user_or_project', return_value=None)

        resp = client.get(f"/blueprint?username=foo")
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json).contains('not found')

    def test_success(self, client, mocker, patch_auth_wrapper):
        blueprints = [{
            "blueprint_id": '91df79b1-d78b-4cac-ae24-4edaf49c5030',
            "blueprint_name": 'TestBlueprint',
            "aadm_id": 'aadm_id',
            "username": 'mihaTrajbaric',
            "project_domain": 'SODALITE',
            "timestamp": timestamp_util.datetime_now_to_string()
        }]
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_blueprints_by_user_or_project',
                     return_value=blueprints)
        resp = client.get(f"/blueprint?username=foo")
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(len(resp.json)).is_equal_to(1)
        assert_that(resp.json).is_equal_to(blueprints)
