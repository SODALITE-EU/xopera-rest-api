import uuid

from assertpy import assert_that

from opera.api.openapi.models import GitLog, BlueprintVersion, Deployment, InvocationState, OperationType
from opera.api.util import timestamp_util


class TestBlueprintMeta:

    @staticmethod
    def test_not_found(client, mocker, patch_auth_wrapper):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_blueprint_meta', return_value=None)

        blueprint_id = uuid.uuid4()
        resp = client.get(f"/blueprint/{blueprint_id}/meta")
        assert resp.status_code == 404
        assert_that(resp.json).contains('Blueprint meta not found')

    @staticmethod
    def test_success(client, mocker, generic_blueprint_meta, patch_auth_wrapper):
        blueprint_meta: BlueprintVersion = generic_blueprint_meta
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_blueprint_meta',
                     return_value=blueprint_meta.to_dict())

        blueprint_id = uuid.uuid4()
        resp = client.get(f"/blueprint/{blueprint_id}/meta")
        assert resp.status_code == 200
        print(blueprint_meta.to_dict())
        assert_that(resp.json).contains(*[key for key in blueprint_meta.to_dict().keys() if key is not None])


class TestBlueprintVersionMeta:

    @staticmethod
    def test_not_found(client, mocker, patch_auth_wrapper):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_blueprint_meta', return_value=None)

        resp = client.get(f"/blueprint/{uuid.uuid4()}/version/v1.0/meta")
        assert resp.status_code == 404
        assert_that(resp.json).contains('Blueprint meta not found')

    @staticmethod
    def test_success(client, mocker, generic_blueprint_meta, patch_auth_wrapper):
        blueprint_meta: BlueprintVersion = generic_blueprint_meta
        blueprint_meta.deployments = [
            Deployment(
                str(uuid.uuid4()), InvocationState.SUCCESS,
                OperationType.DEPLOY_CONTINUE, timestamp_util.datetime_now_to_string()
            )]
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_blueprint_meta',
                     return_value=blueprint_meta.to_dict())
        mocker.patch('opera.api.service.csardb_service.GitDB.get_blueprint_user_list', return_value=[['foo'], None])

        resp = client.get(f"/blueprint/{uuid.uuid4()}/version/v1.0/meta")
        assert resp.status_code == 200
        assert_that(resp.json).contains(*[key for key in blueprint_meta.to_dict().keys() if key is not None])


class TestBlueprintName:

    @staticmethod
    def test_post_success(mocker, client, patch_auth_wrapper):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.update_blueprint_name', return_value=True)

        resp = client.post(f"/blueprint/{uuid.uuid4()}/name?name=foo")
        assert resp.status_code == 201
        assert_that(resp.json).is_equal_to('Successfully changed name')

    @staticmethod
    def test_post_fail(mocker, client, patch_auth_wrapper):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.update_blueprint_name', return_value=False)

        blueprint_id = uuid.uuid4()
        resp = client.post(f"/blueprint/{blueprint_id}/name?name=foo")
        assert resp.status_code == 500
        assert_that(resp.json).contains('Failed to save', str(blueprint_id))

    @staticmethod
    def test_get_success(mocker, client, patch_auth_wrapper):
        name = 'foo'
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_blueprint_name', return_value=name)

        resp = client.get(f"/blueprint/{uuid.uuid4()}/name")
        assert resp.status_code == 200
        assert_that(resp.json).is_equal_to(name)

    @staticmethod
    def test_get_fail(mocker, client, patch_auth_wrapper):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_blueprint_name', return_value=None)

        resp = client.get(f"/blueprint/{uuid.uuid4()}/name")
        assert resp.status_code == 404
        assert_that(resp.json).contains('not found')


class TestGetDeployments:

    @staticmethod
    def test_success(mocker, client, generic_deployment, patch_auth_wrapper):
        deployment: Deployment = generic_deployment
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_deployments_for_blueprint',
                     return_value=[deployment.to_dict()])
        resp = client.get(f"/blueprint/{uuid.uuid4()}/deployments")
        assert resp.status_code == 200
        assert_that(resp.json).is_equal_to([{k: v for k, v in deployment.to_dict().items() if v is not None}])

    @staticmethod
    def test_fail(mocker, client, patch_auth_wrapper):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_deployments_for_blueprint',
                     return_value=[])

        resp = client.get(f"/blueprint/{uuid.uuid4()}/deployments")
        assert resp.status_code == 404
        assert_that(resp.json).contains('not found')


class TestGitHistory:

    def test_not_found(self, client, mocker, patch_auth_wrapper):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_git_transaction_data', return_value=None)
        blueprint_id = uuid.uuid4()
        resp = client.get(f"/blueprint/{blueprint_id}/git_history")
        assert resp.status_code == 404
        assert_that(resp.json).contains('Log not found')

    def test_no_blueprint(self, client, mocker, patch_db):
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
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_git_transaction_data',
                     return_value=[git_data.to_dict()])
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
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_git_transaction_data', new=mock_git_data)

        resp = client.get(f"/blueprint/{git_data.blueprint_id}/git_history")
        assert resp.status_code == 200
        assert_that(resp.json).is_length(1)
        assert_that(resp.json[0]).contains_only(*git_data.to_dict().keys())
        mock_git_data.assert_called_with(git_data.blueprint_id)
