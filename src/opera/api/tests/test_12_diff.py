import uuid

from opera.api.openapi.models import Invocation


class TestDiff:
    blueprint_token = '4a7b9983-dc27-4e43-b7b3-8b696a550fac'
    version_tag = 'version_tag'
    session_data = {'blueprint_token': blueprint_token, 'version_tag': version_tag}

    def test_no_session_data(self, client, mocker):
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mock_get_session_data = mocker.MagicMock(name='session_data', return_value=None)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data', new=mock_get_session_data)

        session_token = uuid.uuid4()
        resp = client.post(f"/diff/{session_token}?blueprint_token={TestDiff.blueprint_token}")
        assert resp.status_code == 404
        mock_get_session_data.assert_called_with(str(session_token))

    def test_no_blueprint(self, client, mocker):
        mock_version_exists = mocker.MagicMock(name='version_exists', return_value=False)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data',
                     return_value=TestDiff.session_data)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', new=mock_version_exists)

        session_token = uuid.uuid4()
        resp = client.post(
            f"/diff/{session_token}?blueprint_token={TestDiff.blueprint_token}&version_tag={TestDiff.version_tag}")
        assert resp.status_code == 404
        mock_version_exists.assert_called_with(TestDiff.blueprint_token, TestDiff.version_tag)

    def test_params(self, client, mocker, generic_invocation: Invocation, inputs_1):
        inv = generic_invocation
        inv.blueprint_token = TestDiff.blueprint_token
        inv.version_tag = TestDiff.version_tag
        inv.workers = 42
        inv.resume = False

        class fake_diff:
            def __init__(self, *args):
                self.out = args

            def outputs(self):
                return self.out

        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data',
                     return_value=TestDiff.session_data)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mock_invoke = mocker.MagicMock(name='invoke', side_effect=fake_diff)
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.diff', new=mock_invoke)

        resp = client.post(
            f"/diff/{inv.session_token}?blueprint_token={inv.blueprint_token}&version_tag={inv.version_tag}")

        assert resp.status_code == 200
        mock_invoke.assert_called_with(str(inv.session_token), str(inv.blueprint_token), inv.version_tag, None)
