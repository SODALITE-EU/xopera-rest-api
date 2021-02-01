import uuid

from assertpy import assert_that


class TestOutputs:

    def test_no_blueprint(self, client, mocker):
        session_token = str(uuid.uuid4())
        mock_session_data = mocker.MagicMock(name='version_exists', return_value=False)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data', new=mock_session_data)

        resp = client.get(f"/outputs/{session_token}")
        assert resp.status_code == 404
        mock_session_data.assert_called_with(session_token)

    def test_exception(self, client, mocker):
        session_token = str(uuid.uuid4())
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data', return_value=True)

        mock_outputs = mocker.MagicMock(name='outputs', return_value=(None, (Exception.__class__.__name__, "Exception "
                                                                                                           "stacktrace")))
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.outputs', new=mock_outputs)
        resp = client.get(f"/outputs/{session_token}")

        assert resp.status_code == 500
        assert_that(resp.json).contains_only("description", "stacktrace")
        mock_outputs.assert_called_with(session_token)

    def test_ok(self, client, mocker):
        session_token = str(uuid.uuid4())
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_session_data', return_value=True)
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
