import json
import uuid
from pathlib import Path

from assertpy import assert_that

from opera.api.controllers.background_invocation import InvocationService
from opera.api.openapi.models.git_log import GitLog
from opera.api.openapi.models.invocation import Invocation, InvocationState
from opera.api.settings import Settings
from opera.api.util import timestamp_util


class TestStatus:

    def test_missing(self, client):
        token = 'foo'
        resp = client.get(f"/info/status?session_token={token}")
        assert resp.status_code == 404
        assert_that(resp.json).contains_only('message')
        assert_that(resp.json['message']).contains(f'Could not find session with session_token {token}')

    def test_pending(self, client, generic_invocation: Invocation):
        inv = generic_invocation
        inv.state = InvocationState.PENDING
        InvocationService.write_invocation(inv)

        resp = client.get(f"/info/status?session_token={inv.session_token}")
        assert_that(resp.json['session_token'] == inv.state)
        assert resp.status_code == 202

    def test_in_progress(self, client, generic_invocation: Invocation):
        inv = generic_invocation
        inv.state = InvocationState.IN_PROGRESS
        InvocationService.write_invocation(inv)
        (Path(Settings.STDFILE_DIR) / str(inv.session_token)).mkdir(parents=True, exist_ok=True)
        (Path(Settings.STDFILE_DIR) / str(inv.session_token) / 'stdout.txt').write_text('stdout')
        (Path(Settings.STDFILE_DIR) / str(inv.session_token) / 'stderr.txt').write_text('stderr')

        resp = client.get(f"/info/status?session_token={inv.session_token}")
        assert_that(resp.json['session_token'] == inv.state)
        assert resp.status_code == 202

    def test_success(self, client, generic_invocation: Invocation):
        inv = generic_invocation
        inv.state = InvocationState.SUCCESS
        InvocationService.write_invocation(inv)

        resp = client.get(f"/info/status?session_token={inv.session_token}")
        assert_that(resp.json['session_token'] == inv.state)
        assert resp.status_code == 201

    def test_failed(self, client, generic_invocation: Invocation):
        inv = generic_invocation
        inv.state = InvocationState.FAILED
        InvocationService.write_invocation(inv)

        resp = client.get(f"/info/status?session_token={inv.session_token}")
        assert_that(resp.json['session_token'] == inv.state)
        assert resp.status_code == 500


class TestGitLog:

    def test_not_found(self, client, mocker):
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_git_transaction_data', return_value=None)
        blueprint_token = str(uuid.uuid4())
        resp = client.get(f"/info/log/git/{blueprint_token}")
        assert resp.status_code == 400
        assert_that(resp.json).contains_only('message')
        assert resp.json['message'] == "Log file not found"

    def test_keys(self, client, mocker):
        git_data = GitLog(
            blueprint_token=str(uuid.uuid4()),
            commit_sha="commit_sha",
            git_backend="MockConnector",
            job="update",
            repo_url="local",
            revision_msg="rev_msg",
            timestamp=timestamp_util.datetime_now_to_string(),
            version_tag='v1'
        )
        mock_git_data = mocker.MagicMock(name='invoke', return_value=[git_data.to_dict()])
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_git_transaction_data', new=mock_git_data)

        fetch_all = True
        resp = client.get(f"/info/log/git/{git_data.blueprint_token}"
                          f"?version_tag={git_data.version_tag}&fetch_all={fetch_all}")
        assert resp.status_code == 200
        assert_that(resp.json).is_length(1)
        assert_that(resp.json[0]).contains_only(*git_data.to_dict().keys())
        mock_git_data.assert_called_with(git_data.blueprint_token, git_data.version_tag, fetch_all)


class TestDeployLog:

    def test_not_found(self, client, mocker):
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_deployment_log', return_value=None)
        blueprint_token = str(uuid.uuid4())
        resp = client.get(f"/info/log/deployment?blueprint_token={blueprint_token}")
        assert resp.status_code == 400
        assert_that(resp.json).contains_only('message')
        assert resp.json['message'] == "Log file not found"

    def test_keys(self, client, mocker, generic_invocation: Invocation):
        inv = generic_invocation
        inv.blueprint_token = str(uuid.uuid4())
        inv.version_tag = "version_tag"
        inv.session_token = str(uuid.uuid4())

        mock_log_data = mocker.MagicMock(name='invoke', return_value=[('timestamp1', json.dumps(inv.to_dict()))])
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_deployment_log', new=mock_log_data)

        resp = client.get(
            f"/info/log/deployment?blueprint_token={inv.blueprint_token}&session_token={inv.session_token}")
        assert resp.status_code == 200
        assert_that(resp.json).is_length(1)
        inv_dict = inv.to_dict()
        assert_that(resp.json[0]).contains_only(*[k for k in inv_dict.keys() if inv_dict[k] is not None])
        mock_log_data.assert_called_with(inv.blueprint_token, inv.session_token)
