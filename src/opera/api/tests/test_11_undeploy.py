from assertpy import assert_that
from opera.api.openapi.models import OperationType, Invocation
import uuid


class TestUndeploy:
    blueprint_token = '10b2e010-17e1-49c8-ae9e-f16e7e7af261'
    version_tag = 'some_version_tag'
    session_data = {'blueprint_token': blueprint_token, 'version_tag': version_tag}
    session_token = 'fdbffaf9-76de-4e28-9fb7-a16c54192351'

    def test_no_session_data(self, client, mocker):
        mock_get_session_data = mocker.MagicMock(name='session_data', return_value=None)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data', new=mock_get_session_data)

        session_token = uuid.uuid4()
        resp = client.post(f"/undeploy/{session_token}")
        assert resp.status_code == 404
        mock_get_session_data.assert_called_with(str(session_token))

    def test_no_blueprint(self, client, mocker):
        mock_version_exists = mocker.MagicMock(name='version_exists', return_value=False)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data',
                     return_value=TestUndeploy.session_data)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', new=mock_version_exists)

        session_token = uuid.uuid4()
        resp = client.post(f"/undeploy/{session_token}")
        assert resp.status_code == 404
        mock_version_exists.assert_called_with(TestUndeploy.blueprint_token, TestUndeploy.version_tag)

    def test_no_inputs(self, client, mocker, generic_invocation: Invocation):
        mock_invoke = mocker.MagicMock(name='invoke', return_value=generic_invocation)
        mocker.patch('opera.api.controllers.background_invocation.InvocationService.invoke', new=mock_invoke)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data',
                     return_value=TestUndeploy.session_data)
        session_token = str(uuid.uuid4())
        resp = client.post(f"/undeploy/{session_token}")
        assert resp.status_code == 202
        mock_invoke.assert_called_with(OperationType.UNDEPLOY, TestUndeploy.blueprint_token,
                                       TestUndeploy.version_tag, session_token,
                                       1, None)

    def test_params(self, client, mocker, generic_invocation: Invocation, inputs_1):
        inv = generic_invocation
        inv.blueprint_token = TestUndeploy.blueprint_token
        inv.version_tag = TestUndeploy.version_tag
        inv.workers = 42
        inv.resume = False
        inv.session_token = str(uuid.uuid4())

        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data',
                     return_value=TestUndeploy.session_data)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mock_invoke = mocker.MagicMock(name='invoke', return_value=inv)
        mocker.patch('opera.api.controllers.background_invocation.InvocationService.invoke', new=mock_invoke)

        resp = client.post(f"/undeploy/{inv.session_token}?workers={inv.workers}", data=inputs_1)
        assert resp.status_code == 202
        inv_dict = inv.to_dict()
        assert_that(resp.json).contains_only(*[k for k in inv_dict.keys() if inv_dict[k] is not None])
        mock_invoke.assert_called_with(OperationType.UNDEPLOY, str(inv.blueprint_token), inv.version_tag,
                                       str(inv.session_token), inv.workers, {'marker': 'blah'})







