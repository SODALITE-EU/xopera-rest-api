import uuid

from assertpy import assert_that

from opera.api.openapi.models import OperationType, Invocation


class TestUpdate:
    blueprint_token = '4a7b9983-dc27-4e43-b7b3-8b696a550fac'
    version_tag = 'version_tag'
    session_data = {'blueprint_token': blueprint_token, 'version_tag': version_tag}

    def test_no_session_data(self, client, mocker):
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mock_get_session_data = mocker.MagicMock(name='session_data', return_value=None)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data', new=mock_get_session_data)

        session_token = uuid.uuid4()
        resp = client.post(f"/update/{session_token}?blueprint_token={TestUpdate.blueprint_token}")
        assert resp.status_code == 404
        mock_get_session_data.assert_called_with(str(session_token))

    def test_no_blueprint(self, client, mocker):
        mock_version_exists = mocker.MagicMock(name='version_exists', return_value=False)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data',
                     return_value=TestUpdate.session_data)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', new=mock_version_exists)

        session_token = uuid.uuid4()
        resp = client.post(f"/update/{session_token}"
                           f"?blueprint_token={TestUpdate.blueprint_token}"
                           f"&version_tag={TestUpdate.version_tag}")
        assert resp.status_code == 404
        mock_version_exists.assert_called_with(TestUpdate.blueprint_token, TestUpdate.version_tag)

    def test_params(self, client, mocker, generic_invocation: Invocation, inputs_1):
        inv = generic_invocation
        inv.blueprint_token = TestUpdate.blueprint_token
        inv.version_tag = TestUpdate.version_tag
        inv.workers = 42
        inv.resume = False

        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data',
                     return_value=TestUpdate.session_data)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mock_invoke = mocker.MagicMock(name='invoke', return_value=inv)
        mocker.patch('opera.api.controllers.background_invocation.InvocationService.invoke', new=mock_invoke)
        resp = client.post(
            f"/update/{inv.session_token}"
            f"?blueprint_token={inv.blueprint_token}"
            f"&version_tag={inv.version_tag}"
            f"&workers={inv.workers}", data=inputs_1)

        assert resp.status_code == 202
        inv_dict = inv.to_dict()
        assert_that(resp.json).contains_only(*[k for k in inv_dict.keys() if inv_dict[k] is not None])
        mock_invoke.assert_called_with(OperationType.UPDATE, str(inv.blueprint_token), inv.version_tag,
                                       inv.session_token, inv.workers, {'marker': 'blah'})
