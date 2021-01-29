from assertpy import assert_that
from opera.api.openapi.models import OperationType, Invocation
import uuid


class TestDeployFresh:

    def test_no_blueprint(self, client, mocker):
        mock_version_exists = mocker.MagicMock(name='version_exists', return_value=False)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', new=mock_version_exists)

        resp = client.post(f"/deploy/fresh/{'42'}")
        assert resp.status_code == 404
        assert_that(resp.json).contains_only('message')
        assert_that(resp.json['message']).contains('Did not find blueprint')
        mock_version_exists.assert_called_with('42', None)

    def test_params(self, client, mocker, generic_invocation, inputs_1):
        mock_invoke = mocker.MagicMock(name='invoke', return_value=generic_invocation)
        mocker.patch('opera.api.controllers.background_invocation.InvocationService.invoke', new=mock_invoke)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)

        blueprint_token = uuid.uuid4()
        version_tag = 'version_tag'
        workers = 42
        resp = client.post(f"/deploy/fresh/{blueprint_token}?version_tag={version_tag}&workers={workers}", data=inputs_1)
        assert resp.status_code == 202
        inv_dict = generic_invocation.to_dict()
        assert_that(resp.json).contains_only(*[k for k in inv_dict.keys() if inv_dict[k] is not None])
        mock_invoke.assert_called_with(OperationType.DEPLOY_FRESH, str(blueprint_token), version_tag, None, workers, {'marker': 'blah'})

    def test_no_inputs(self, client, mocker, generic_invocation):
        mock_invoke = mocker.MagicMock(name='invoke', return_value=generic_invocation)
        mocker.patch('opera.api.controllers.background_invocation.InvocationService.invoke', new=mock_invoke)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)

        resp = client.post(f"/deploy/fresh/42")
        assert resp.status_code == 202
        mock_invoke.assert_called_with('deploy_fresh', '42', None, None, 1, None)


class TestDeployContinue:
    blueprint_token = '4a7b9983-dc27-4e43-b7b3-8b696a550fac'
    version_tag = 'version_tag'
    session_data = {'blueprint_token': blueprint_token, 'version_tag': version_tag}

    def test_no_session_data(self, client, mocker):
        mock_get_session_data = mocker.MagicMock(name='session_data', return_value=None)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data', new=mock_get_session_data)

        session_token = uuid.uuid4()
        resp = client.post(f"/deploy/{session_token}")
        assert resp.status_code == 404
        mock_get_session_data.assert_called_with(str(session_token))

    def test_no_blueprint(self, client, mocker):
        mock_version_exists = mocker.MagicMock(name='version_exists', return_value=False)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data',
                     return_value=TestDeployContinue.session_data)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', new=mock_version_exists)

        session_token = uuid.uuid4()
        resp = client.post(f"/deploy/{session_token}")
        assert resp.status_code == 404
        mock_version_exists.assert_called_with(TestDeployContinue.blueprint_token, TestDeployContinue.version_tag)

    def test_no_inputs(self, client, mocker, generic_invocation: Invocation):
        mock_invoke = mocker.MagicMock(name='invoke', return_value=generic_invocation)
        mocker.patch('opera.api.controllers.background_invocation.InvocationService.invoke', new=mock_invoke)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data',
                     return_value=TestDeployContinue.session_data)
        session_token = 'session_token'
        resp = client.post(f"/deploy/{session_token}")
        assert resp.status_code == 202
        mock_invoke.assert_called_with(OperationType.DEPLOY_CONTINUE, TestDeployContinue.blueprint_token,
                                       TestDeployContinue.version_tag, session_token,
                                       1, None, True)

    def test_params(self, client, mocker, generic_invocation: Invocation, inputs_1):
        inv = generic_invocation
        inv.blueprint_token = TestDeployContinue.blueprint_token
        inv.version_tag = TestDeployContinue.version_tag
        inv.workers = 42
        inv.resume = False

        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data',
                     return_value=TestDeployContinue.session_data)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mock_invoke = mocker.MagicMock(name='invoke', return_value=inv)
        mocker.patch('opera.api.controllers.background_invocation.InvocationService.invoke', new=mock_invoke)

        resp = client.post(f"/deploy/{inv.session_token}?workers={inv.workers}&resume={inv.resume}", data=inputs_1)
        assert resp.status_code == 202
        inv_dict = inv.to_dict()
        assert_that(resp.json).contains_only(*[k for k in inv_dict.keys() if inv_dict[k] is not None])
        mock_invoke.assert_called_with(OperationType.DEPLOY_CONTINUE, str(inv.blueprint_token), inv.version_tag,
                                       inv.session_token, inv.workers, {'marker': 'blah'}, inv.resume)







