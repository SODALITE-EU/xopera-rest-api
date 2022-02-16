import uuid
from pathlib import Path

from assertpy import assert_that

from opera.api.controllers.background_invocation import InvocationService, InvocationWorkerProcess
from opera.api.openapi.models import OperationType
from opera.api.openapi.models.invocation import Invocation, InvocationState
from opera.api.settings import Settings
from opera.error import AggregatedOperationError, OperationError


class TestDeploymentExists:

    def test(self, client):
        # TODO fix when functionality implemented
        # blueprint_id = uuid.uuid4()
        # resp = client.put(f"/deployment/exists?blueprint_id={blueprint_id}")
        # assert_that(resp.json).contains('Not implemented')
        pass


class TestDeployFresh:

    def test_no_blueprint(self, client, mocker, patch_db):
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=False)
        mock_version_exists = mocker.MagicMock(name='version_exists', return_value=False)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', new=mock_version_exists)

        blueprint_id = uuid.uuid4()
        resp = client.post(f"/deployment/deploy?blueprint_id={blueprint_id}")
        assert resp.status_code == 404
        assert_that(resp.json).contains('Did not find blueprint')
        mock_version_exists.assert_called_with(str(blueprint_id), None)

    def test_params(self, client, mocker, generic_invocation, inputs_1, patch_auth_wrapper):
        mock_invoke = mocker.MagicMock(name='invoke', return_value=generic_invocation)
        mocker.patch('opera.api.controllers.background_invocation.InvocationService.invoke', new=mock_invoke)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)

        blueprint_id = uuid.uuid4()
        version_id = 'v2.0'
        workers = 42
        deployment_label = 'production'
        resp = client.post(f"/deployment/deploy?blueprint_id={blueprint_id}&version_id={version_id}"
                           f"&workers={workers}&deployment_label={deployment_label}",
                           data=inputs_1)
        assert resp.status_code == 202
        inv_dict = generic_invocation.to_dict()
        assert_that(resp.json).contains_only(*[k for k in inv_dict.keys() if inv_dict[k] is not None])
        mock_invoke.assert_called_with(
            operation_type=OperationType.DEPLOY_FRESH,
            blueprint_id=str(blueprint_id),
            version_id=version_id,
            deployment_label=deployment_label,
            workers=workers,
            inputs={'marker': 'blah'},
            username=None,
            access_token=None
        )

    def test_no_inputs(self, client, mocker, generic_invocation, patch_auth_wrapper):
        mock_invoke = mocker.MagicMock(name='invoke', return_value=generic_invocation)
        mocker.patch('opera.api.controllers.background_invocation.InvocationService.invoke', new=mock_invoke)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)

        blueprint_id = uuid.uuid4()
        resp = client.post(f"/deployment/deploy?blueprint_id={blueprint_id}")
        assert resp.status_code == 202
        mock_invoke.assert_called_with(
            operation_type=OperationType.DEPLOY_FRESH,
            blueprint_id=str(blueprint_id),
            version_id=None,
            deployment_label=None,
            workers=1,
            inputs=None,
            username=None,
            access_token=None
        )


class TestStatus:

    def test_missing(self, client, mocker):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_deployment_status', return_value=None)
        deployment_id = uuid.uuid4()
        resp = client.get(f"/deployment/{deployment_id}/status")
        assert resp.status_code == 404
        assert_that(resp.json).contains('does not exist')

    def test_pending(self, client, generic_invocation: Invocation, patch_auth_wrapper):
        inv = generic_invocation
        inv.state = InvocationState.PENDING
        inv.deployment_id = uuid.uuid4()
        inv_id = uuid.uuid4()
        InvocationService.save_invocation(inv_id, inv)

        resp = client.get(f"/deployment/{inv.deployment_id}/status")
        assert resp.json['state'] == inv.state
        assert resp.status_code == 200

    def test_in_progress(self, client, generic_invocation: Invocation, patch_auth_wrapper):
        inv = generic_invocation
        inv.state = InvocationState.IN_PROGRESS
        inv.deployment_id = uuid.uuid4()
        inv_id = uuid.uuid4()
        InvocationService.save_invocation(inv_id, inv)
        (Path(Settings.STDFILE_DIR) / str(inv.deployment_id)).mkdir(parents=True, exist_ok=True)
        (Path(Settings.STDFILE_DIR) / str(inv.deployment_id) / 'stdout.txt').write_text('stdout')
        (Path(Settings.STDFILE_DIR) / str(inv.deployment_id) / 'stderr.txt').write_text('stderr')

        resp = client.get(f"/deployment/{inv.deployment_id}/status")
        assert resp.json['state'] == inv.state
        assert resp.status_code == 200

    def test_success(self, client, generic_invocation: Invocation, patch_auth_wrapper):
        inv = generic_invocation
        inv.state = InvocationState.SUCCESS
        inv.deployment_id = uuid.uuid4()
        inv_id = uuid.uuid4()
        InvocationService.save_invocation(inv_id, inv)

        resp = client.get(f"/deployment/{inv.deployment_id}/status")
        assert resp.json['state'] == inv.state
        assert resp.status_code == 200

    def test_failed(self, client, generic_invocation: Invocation, patch_auth_wrapper):
        inv = generic_invocation
        inv.state = InvocationState.FAILED
        inv.deployment_id = uuid.uuid4()
        inv_id = uuid.uuid4()
        InvocationService.save_invocation(inv_id, inv)

        resp = client.get(f"/deployment/{inv.deployment_id}/status")
        assert resp.json['state'] == inv.state
        assert resp.status_code == 200

    def test_execution_error(self, mocker, generic_invocation: Invocation):
        inv = generic_invocation
        inv.state = InvocationState.FAILED
        mocker.patch('opera.api.util.xopera_util.try_get_failed_tasks', return_value={"task": "error"})
        exception = AggregatedOperationError("Failed", {"worker1": OperationError("Failed", "node", "Standard", "create")})
        result = InvocationWorkerProcess.try_extract_error(inv, exception)
        assert len(result) == 1
        assert result["node"] == {"create": {"task": "error"}}

class TestHistory:

    def test_not_found(self, client, mocker, patch_auth_wrapper):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_deployment_history', return_value=[])
        deployment_id = uuid.uuid4()
        resp = client.get(f"/deployment/{deployment_id}/history")
        assert resp.status_code == 404
        assert_that(resp.json).contains("History not found")

    def test_success(self, client, mocker, generic_invocation: Invocation, patch_auth_wrapper):
        inv = generic_invocation
        inv.deployment_id = uuid.uuid4()

        mock_log_data = mocker.MagicMock(name='invoke', return_value=[inv])
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_deployment_history', new=mock_log_data)

        resp = client.get(f"/deployment/{inv.deployment_id}/history")
        assert resp.status_code == 200
        assert_that(resp.json).is_length(1)
        inv_dict = inv.to_dict()
        assert_that(resp.json[0]).contains_only(*[k for k in inv_dict.keys() if inv_dict[k] is not None])
        mock_log_data.assert_called_with(str(inv.deployment_id))


class TestDeployContinue:

    def test_no_deployment(self, client, mocker):
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_deployment_status', return_value=None)
        deployment_id = uuid.uuid4()
        resp = client.post(f"/deployment/{deployment_id}/deploy_continue")
        assert resp.status_code == 404
        assert_that(resp.json).contains('does not exist')

    def test_still_running(self, client, mocker, generic_invocation: Invocation, patch_auth_wrapper):
        inv = generic_invocation
        inv.state = InvocationState.IN_PROGRESS
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_deployment_status', return_value=inv)

        deployment_id = uuid.uuid4()
        resp = client.post(f"/deployment/{deployment_id}/deploy_continue")
        assert resp.status_code == 403
        assert_that(resp.json).contains('still running')

    def test_params(self, client, mocker, generic_invocation: Invocation, inputs_1, patch_auth_wrapper):
        inv = generic_invocation
        inv.deployment_id = uuid.uuid4()
        # to pass previous operation test
        inv.state = InvocationState.SUCCESS
        inv.workers = 42
        inv.clean_state = True

        mock_invoke = mocker.MagicMock(name='invoke', return_value=inv)
        mocker.patch('opera.api.controllers.background_invocation.InvocationService.invoke', new=mock_invoke)

        resp = client.post(f"/deployment/{inv.deployment_id}/deploy_continue"
                           f"?workers={inv.workers}&clean_state={inv.clean_state}", data=inputs_1)
        assert resp.status_code == 202
        inv_dict = inv.to_dict()
        assert_that(resp.json).contains_only(*[k for k in inv_dict.keys() if inv_dict[k] is not None])
        mock_invoke.assert_called_with(
            operation_type=OperationType.DEPLOY_CONTINUE,
            blueprint_id=str(inv.blueprint_id),
            version_id=inv.version_id,
            deployment_label=inv.deployment_label,
            deployment_id=str(inv.deployment_id),
            workers=inv.workers,
            inputs={'marker': 'blah'},
            clean_state=inv.clean_state,
            username=None,
            access_token=None
        )


class TestDiff:

    def test_params(self, client, mocker, generic_invocation: Invocation, patch_auth_wrapper):
        inv = generic_invocation
        inv.blueprint_id = uuid.uuid4()
        inv.version_id = 'v1.0'
        inv.deployment_id = uuid.uuid4()
        inv.workers = 42

        class FakeDiff:
            def __init__(self, *args):
                self.out = args

            def outputs(self):
                return self.out

        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mock_invoke = mocker.MagicMock(name='invoke', side_effect=FakeDiff)
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.diff', new=mock_invoke)

        resp = client.put(f"/deployment/{inv.deployment_id}/diff"
                          f"?blueprint_id={inv.blueprint_id}"
                          f"&version_id={inv.version_id}")

        assert resp.status_code == 200
        mock_invoke.assert_called_with(str(inv.deployment_id), str(inv.blueprint_id), inv.version_id, None)


class TestUpdate:

    def test_still_running(self, client, mocker, generic_invocation: Invocation, patch_auth_wrapper):
        inv = generic_invocation
        inv.state = InvocationState.IN_PROGRESS
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_deployment_status', return_value=inv)

        resp = client.post(f"/deployment/{inv.deployment_id}/update"
                           f"?blueprint_id={inv.blueprint_id}"
                           f"&version_id={inv.version_id}")
        assert resp.status_code == 403
        assert_that(resp.json).contains('still running')

    def test_params(self, client, mocker, generic_invocation: Invocation, inputs_1, patch_auth_wrapper):
        inv = generic_invocation
        inv.deployment_id = uuid.uuid4()
        # to pass previous operation test
        inv.state = InvocationState.SUCCESS
        inv.workers = 42

        mock_invoke = mocker.MagicMock(name='invoke', return_value=inv)
        mocker.patch('opera.api.controllers.background_invocation.InvocationService.invoke', new=mock_invoke)

        resp = client.post(f"/deployment/{inv.deployment_id}/update"
                           f"?blueprint_id={inv.blueprint_id}"
                           f"&version_id={inv.version_id}"
                           f"&workers={inv.workers}", data=inputs_1)

        assert resp.status_code == 202
        inv_dict = inv.to_dict()
        assert_that(resp.json).contains_only(*[k for k in inv_dict.keys() if inv_dict[k] is not None])
        mock_invoke.assert_called_with(
            operation_type=OperationType.UPDATE,
            blueprint_id=str(inv.blueprint_id),
            version_id=inv.version_id,
            deployment_id=str(inv.deployment_id),
            workers=inv.workers,
            inputs={'marker': 'blah'},
            username=None,
            access_token=None
        )


class TestUndeploy:

    def test_still_running(self, client, mocker, generic_invocation: Invocation, patch_auth_wrapper):
        inv = generic_invocation
        inv.state = InvocationState.IN_PROGRESS
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_deployment_status', return_value=inv)

        resp = client.post(f"/deployment/{inv.deployment_id}/undeploy")
        assert resp.status_code == 403
        assert_that(resp.json).contains('still running')

    def test_params(self, client, mocker, generic_invocation: Invocation, inputs_1, patch_auth_wrapper):
        inv = generic_invocation
        inv.deployment_id = uuid.uuid4()
        # to pass previous operation test
        inv.state = InvocationState.SUCCESS
        inv.workers = 42

        mock_invoke = mocker.MagicMock(name='invoke', return_value=inv)
        mocker.patch('opera.api.controllers.background_invocation.InvocationService.invoke', new=mock_invoke)

        resp = client.post(f"/deployment/{inv.deployment_id}/undeploy?workers={inv.workers}", data=inputs_1)
        assert resp.status_code == 202
        inv_dict = inv.to_dict()
        assert_that(resp.json).contains_only(*[k for k in inv_dict.keys() if inv_dict[k] is not None])
        mock_invoke.assert_called_with(
            operation_type=OperationType.UNDEPLOY,
            blueprint_id=str(inv.blueprint_id),
            version_id=inv.version_id,
            deployment_label=inv.deployment_label,
            deployment_id=str(inv.deployment_id),
            workers=inv.workers,
            inputs={'marker': 'blah'},
            username=None,
            access_token=None
        )


class TestDeleteDeployment:

    def test_still_running(self, client, mocker, generic_invocation: Invocation, patch_auth_wrapper):
        inv = generic_invocation
        inv.state = InvocationState.IN_PROGRESS
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_deployment_status', return_value=inv)

        resp = client.delete(f"/deployment/{inv.deployment_id}")
        assert resp.status_code == 403
        assert_that(resp.json).contains('still running')

    def test_fail(self, client, mocker, generic_invocation: Invocation, patch_auth_wrapper):
        inv = generic_invocation
        inv.deployment_id = uuid.uuid4()
        # to pass previous operation test
        inv.state = InvocationState.SUCCESS
        inv.workers = 42

        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.delete_deployment', return_value=False)
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.delete_opera_session_data', return_value=True)

        resp = client.delete(f"/deployment/{inv.deployment_id}")
        assert resp.status_code == 500
        assert_that(resp.json).contains("Failed to delete")

    def test_params(self, client, mocker, generic_invocation: Invocation, patch_auth_wrapper):
        inv = generic_invocation
        inv.deployment_id = uuid.uuid4()
        # to pass previous operation test
        inv.state = InvocationState.SUCCESS
        inv.workers = 42

        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.delete_deployment', return_value=True)
        mocker.patch('opera.api.service.sqldb_service.PostgreSQL.delete_opera_session_data', return_value=True)

        resp = client.delete(f"/deployment/{inv.deployment_id}")
        assert resp.status_code == 200
        assert_that(resp.json).contains("deleted")
