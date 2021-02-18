import uuid

import validators
from assertpy import assert_that

from opera.api.openapi.models.git_log import GitLog
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
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.save_project_domain', return_value=False)
        mocker.patch('opera.api.controllers.security_controller.check_roles', return_value=True)
        mocker.patch('opera.api.service.csardb_service.GitDB.add_revision', return_value=({'blueprint_id': 'a'}, None))
        domain = '42'
        resp = client.post(f"/blueprint?project_domain={domain}", data=csar_empty, content_type='multipart/form-data')
        assert_that(resp.status_code).is_equal_to(500)
        assert_that(resp.json).contains('Failed to save project data')

    def test_success(self, client, csar_1):
        resp = client.post("/blueprint", data=csar_1)
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json).is_not_none().contains_only('blueprint_id', 'url',
                                                           'version_id', 'users', 'commit_sha', 'timestamp')
        uuid.UUID(resp.get_json()['blueprint_id'])

        assert_that(resp.get_json()['version_id']).is_equal_to('v1.0')

        validators.url(resp.get_json()['url'])


class TestPostMultipleVersions:

    def test_wrong_token(self, client, csar_1):
        blueprint_id = uuid.uuid4()
        resp = client.post(f"/blueprint/{blueprint_id}", data=csar_1)
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json).is_not_none().contains("Did not find blueprint")

    def test_unauthorized(self, client, csar_1, mocker):
        blueprint_id = uuid.uuid4()
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mocker.patch('opera.api.controllers.security_controller.check_roles', return_value=False)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_project_domain', return_value='foo')

        resp = client.post(f"/blueprint/{blueprint_id}", data=csar_1)
        assert_that(resp.status_code).is_equal_to(401)
        assert_that(resp.json).is_not_none().contains("Unauthorized request")

    def test_emtpy_request(self, client, csar_empty, csar_1):
        # prepare blueprint
        resp = client.post("/blueprint", data=csar_1)
        assert_that(resp.status_code).is_equal_to(200)
        token = resp.json['blueprint_id']

        resp = client.post("/blueprint/{}".format(token), data=csar_empty, content_type='multipart/form-data')
        assert_that(resp.status_code).is_equal_to(406)
        assert_that(resp.json).is_not_none().contains("Invalid CSAR")

    def test_success(self, client, csar_1, csar_2):
        # prepare first blueprint
        resp1 = client.post("/blueprint", data=csar_1)
        blueprint_id = resp1.json['blueprint_id']
        # test new version
        resp2 = client.post(f"/blueprint/{blueprint_id}", data=csar_2)
        assert_that(resp2.status_code).is_equal_to(200)
        assert_that(resp2.json).is_not_none().contains_only('blueprint_id', 'url', 'version_id',
                                                            'users', 'commit_sha', 'timestamp')
        assert_that(resp2.json['version_id']).is_equal_to('v2.0')


class TestDelete:

    def test_json_keys_error(self, client):
        resp = client.delete(f"/blueprint/{42}")
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json).is_not_none().contains("Did not find blueprint")

    def test_json_keys_success(self, client, csar_1):
        resp = client.post("/blueprint", data=csar_1)
        blueprint_id = resp.json['blueprint_id']

        resp = client.delete(f"/blueprint/{blueprint_id}")
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json).is_not_none().contains_only('blueprint_id', 'timestamp', 'url')

    def test_delete_before_undeploy(self, client, csar_1, csar_2):
        # # upload local blueprint
        # resp = client.post(f"/blueprint", data=csar_1)
        # blueprint_token = resp.json['blueprint_token']
        #
        # # upload again, mock revision_msg after deploy
        # client.post(f"/blueprint/{blueprint_token}?revision_msg="
        #             f"{git_util.after_job_commit_msg(token=blueprint_token, mode='deploy')}", data=csar_2)
        #
        # # try to delete
        # resp = client.delete(f"/blueprint/{blueprint_token}")
        # assert_that(resp.status_code).is_equal_to(403)
        pass

    def test_force_delete(self, client, csar_1, csar_2):
        # # upload local blueprint
        # resp = client.post(f"/blueprint", data=csar_1)
        # blueprint_token = resp.json['blueprint_token']
        #
        # # upload again, mock revision_msg after deploy
        # client.post(f"/blueprint/{blueprint_token}?revision_msg="
        #             f"{git_util.after_job_commit_msg(token=blueprint_token, mode='deploy')}", data=csar_2)
        #
        # # try to delete with force
        # resp = client.delete(f"/blueprint/{blueprint_token}?force={True}")
        # assert_that(resp.status_code).is_equal_to(200)
        pass

    def test_server_error(self, client, mocker, patch_auth_wrapper):
        mocker.patch('opera.api.service.csardb_service.GitDB.delete_blueprint', return_value=[0, 500])

        blueprint_id = uuid.uuid4()
        resp = client.delete(f"/blueprint/{blueprint_id}")
        assert_that(resp.status_code).is_equal_to(500)
        assert_that(resp.json).is_equal_to('Server error')


class TestDeleteVersion:

    def test_delete_by_wrong_version_tag(self, client):
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

    def test_delete_before_undeploy(self, client, csar_1, csar_2):
        pass

    def test_force_delete(self, client, csar_1, csar_2):
        pass

    def test_server_error(self, client, mocker, patch_auth_wrapper):
        mocker.patch('opera.api.service.csardb_service.GitDB.delete_blueprint', return_value=[0, 500])

        blueprint_id = uuid.uuid4()
        version_id = 'v1.0'
        resp = client.delete(f"/blueprint/{blueprint_id}/version/{version_id}")
        assert_that(resp.status_code).is_equal_to(500)
        assert_that(resp.json).is_equal_to('Server error')


class TestUser:

    def test_get_users_non_existing_blueprint(self, client):
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

    def test_add_users_to_non_existing_blueprint(self, client):
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

    def test_add_user_success(self, client, csar_1):
        # upload local blueprint
        resp = client.post(f"/blueprint", data=csar_1)
        blueprint_token = resp.json['blueprint_id']
        resp = client.get(f"/blueprint/{blueprint_token}/user")

        assert_that(resp.json).is_empty()

        username = 'foo'
        resp = client.post(f"/blueprint/{blueprint_token}/user/{username}")
        # since this is MockConnector, message should be 'user foo added'
        assert_that(resp.json).is_equal_to('User foo added')
        assert_that(resp.status_code).is_equal_to(201)

        resp = client.get(f"/blueprint/{blueprint_token}/user")
        assert_that(resp.json).is_not_empty().contains_only('foo')

    def test_delete_users_git_error(self, client, mocker, patch_auth_wrapper):
        blueprint_token = uuid.uuid4()
        username = 'foo'
        mocker.patch('opera.api.service.csardb_service.GitDB.check_token_exists', return_value=True)
        mocker.patch('opera.api.service.csardb_service.GitDB.delete_blueprint_user', return_value=[None, 'Error_msg'])

        resp = client.delete(f"/blueprint/{blueprint_token}/user/{username}")
        assert_that(resp.status_code).is_equal_to(500)
        assert_that(resp.json).contains('Could not delete user')

    def test_delete_user_success(self, client, csar_1, patch_auth_wrapper):
        # upload local blueprint
        resp = client.post(f"/blueprint", data=csar_1)
        blueprint_token = resp.json['blueprint_id']
        username = 'foo'
        client.post(f"/blueprint/{blueprint_token}/user/{username}")
        resp = client.get(f"/blueprint/{blueprint_token}/user")
        assert_that(resp.json).contains_only('foo')

        resp = client.delete(f"/blueprint/{blueprint_token}/user/{username}")
        assert_that(resp.json).is_equal_to('User foo deleted')
        assert_that(resp.status_code).is_equal_to(201)
        resp = client.get(f"/blueprint/{blueprint_token}/user")
        assert_that(resp.json).is_empty()


class TestValidateExisting:

    def test_no_blueprint(self, client, mocker):
        blueprint_id = uuid.uuid4()
        mock_version_exists = mocker.MagicMock(name='version_exists', return_value=False)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', new=mock_version_exists)

        resp = client.put(f"blueprint/{blueprint_id}/validate")
        assert resp.status_code == 404
        mock_version_exists.assert_called_with(str(blueprint_id), None)

    def test_exception(self, client, mocker):
        blueprint_id = uuid.uuid4()
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mock_validate = mocker.MagicMock(name='validate',
                                         return_value="{}: {}".format(Exception.__class__.__name__,
                                                                      "Exception stacktrace"))

        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.validate', new=mock_validate)
        resp = client.put(f"/blueprint/{blueprint_id}/validate")

        assert resp.status_code == 500
        assert_that(resp.json).contains("Exception stacktrace")
        mock_validate.assert_called_with(str(blueprint_id), None, None)

    def test_ok(self, client, mocker, inputs_1):
        blueprint_token = uuid.uuid4()
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mock_validate = mocker.MagicMock(name='validate', return_value=None)
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.validate', new=mock_validate)
        resp = client.put(f"/blueprint/{blueprint_token}/validate", data=inputs_1)

        assert resp.status_code == 200
        assert_that(resp.json).contains("Validation OK")
        mock_validate.assert_called_with(str(blueprint_token), None, {'marker': 'blah'})


class TestValidateExistingVersion:

    def test_no_blueprint(self, client, mocker):
        blueprint_id = uuid.uuid4()
        version_id = 'v1.0'
        mock_version_exists = mocker.MagicMock(name='version_exists', return_value=False)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', new=mock_version_exists)

        resp = client.put(f"blueprint/{blueprint_id}/version/{version_id}/validate")
        assert resp.status_code == 404
        mock_version_exists.assert_called_with(str(blueprint_id), version_id)

    def test_exception(self, client, mocker):
        blueprint_id = uuid.uuid4()
        version_id = 'v1.0'
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mock_validate = mocker.MagicMock(name='validate',
                                         return_value="{}: {}".format(Exception.__class__.__name__,
                                                                      "Exception stacktrace"))
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.validate', new=mock_validate)
        resp = client.put(f"/blueprint/{blueprint_id}/version/{version_id}/validate")

        assert resp.status_code == 500
        assert_that(resp.json).contains("Exception stacktrace")
        mock_validate.assert_called_with(str(blueprint_id), version_id, None)

    def test_ok(self, client, mocker, inputs_1):
        blueprint_token = uuid.uuid4()
        version_id = 'v1.0'
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mock_validate = mocker.MagicMock(name='validate', return_value=None)
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.validate', new=mock_validate)
        resp = client.put(f"/blueprint/{blueprint_token}/version/{version_id}/validate", data=inputs_1)

        assert resp.status_code == 200
        assert_that(resp.json).contains("Validation OK")
        mock_validate.assert_called_with(str(blueprint_token), version_id, {'marker': 'blah'})


class TestValidateNew:

    def test_exception(self, client, mocker, csar_1):
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.validate_new',
                     return_value="{}: {}".format(Exception.__class__.__name__, "Exception stacktrace"))
        resp = client.put(f"/blueprint/validate", data=csar_1)

        assert resp.status_code == 500
        assert_that(resp.json).contains("Exception stacktrace")

    def test_ok(self, client, mocker, csar_1):
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.validate', return_value=None)
        resp = client.put(f"/blueprint/validate", data=csar_1)

        assert resp.status_code == 200
        assert_that(resp.json).contains("Validation OK")


class TestGitHistory:

    def test_not_found(self, client, mocker, patch_auth_wrapper):
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_git_transaction_data', return_value=None)
        blueprint_id = uuid.uuid4()
        resp = client.get(f"/blueprint/{blueprint_id}/git_history")
        assert resp.status_code == 400
        assert_that(resp.json).contains('Log not found')

    def test_no_blueprint(self, client, mocker):
        # assert endpoint works even when blueprint is gone
        blueprint_id = uuid.uuid4()
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=False)
        git_data = GitLog(
            blueprint_id=str(blueprint_id),
            commit_sha="commit_sha",
            git_backend="MockConnector",
            job="update",
            repo_url="local",
            revision_msg="rev_msg",
            timestamp=timestamp_util.datetime_now_to_string(),
            version_id='v1.0'
        )
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_git_transaction_data', return_value=[git_data.to_dict()])
        blueprint_id = uuid.uuid4()
        resp = client.get(f"/blueprint/{blueprint_id}/git_history")
        assert resp.status_code == 200

    def test_keys(self, client, mocker, patch_auth_wrapper):
        git_data = GitLog(
            blueprint_id=str(uuid.uuid4()),
            commit_sha="commit_sha",
            git_backend="MockConnector",
            job="update",
            repo_url="local",
            revision_msg="rev_msg",
            timestamp=timestamp_util.datetime_now_to_string(),
            version_id='v1.0'
        )
        mock_git_data = mocker.MagicMock(name='invoke', return_value=[git_data.to_dict()])
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_git_transaction_data', new=mock_git_data)

        resp = client.get(f"/blueprint/{git_data.blueprint_id}/git_history")
        assert resp.status_code == 200
        assert_that(resp.json).is_length(1)
        assert_that(resp.json[0]).contains_only(*git_data.to_dict().keys())
        mock_git_data.assert_called_with(git_data.blueprint_id, fetch_all=True)
