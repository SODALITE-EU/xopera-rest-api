import uuid

from assertpy import assert_that


class TestOutputs:
    blueprint_token = '4a7b9983-dc27-4e43-b7b3-8b696a550fac'
    version_tag = 'version_tag'
    session_data = {'blueprint_token': blueprint_token, 'version_tag': version_tag}

    def test_no_session_data(self, client, mocker):
        mock_get_session_data = mocker.MagicMock(name='session_data', return_value=None)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data', new=mock_get_session_data)

        session_token = uuid.uuid4()
        resp = client.get(f"/outputs/{session_token}")
        assert resp.status_code == 404
        mock_get_session_data.assert_called_with(str(session_token))

    def test_no_blueprint(self, client, mocker):
        session_token = str(uuid.uuid4())
        mock_version_exists = mocker.MagicMock(name='version_exists', return_value=False)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data',
                     return_value=TestOutputs.session_data)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', new=mock_version_exists)

        resp = client.get(f"/outputs/{session_token}")
        assert resp.status_code == 404
        mock_version_exists.assert_called_with(TestOutputs.blueprint_token, TestOutputs.version_tag)

    def test_exception(self, client, mocker):
        session_token = str(uuid.uuid4())
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data',
                     return_value=TestOutputs.session_data)

        mock_outputs = mocker.MagicMock(name='outputs',
                                        return_value=(None, (Exception.__class__.__name__, "Exception stacktrace")))
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.outputs', new=mock_outputs)
        resp = client.get(f"/outputs/{session_token}")

        assert resp.status_code == 500
        assert_that(resp.json).contains_only("description", "stacktrace")
        mock_outputs.assert_called_with(session_token)

    def test_ok(self, client, mocker):
        session_token = str(uuid.uuid4())
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data',
                     return_value=TestOutputs.session_data)
        mock_outputs = mocker.MagicMock(name='outputs', return_value=({
                                                                          "output1": {
                                                                              "description": "first output",
                                                                              "value": "foo"
                                                                          },
                                                                          "output2": {
                                                                              "description": "second output",
                                                                              "value": "bar"
                                                                          }
                                                                      }, None))
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.outputs', new=mock_outputs)
        resp = client.get(f"/outputs/{session_token}")

        assert resp.status_code == 200
        assert_that(resp.json).contains_only("output1", "output2")
        mock_outputs.assert_called_with(session_token)
