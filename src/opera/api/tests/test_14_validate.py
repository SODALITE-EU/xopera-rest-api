import uuid

from assertpy import assert_that


class TestValidate:

    def test_no_blueprint(self, client, mocker):
        blueprint_token = str(uuid.uuid4())
        version_tag = 'version_tag1'
        mock_version_exists = mocker.MagicMock(name='version_exists', return_value=False)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', new=mock_version_exists)

        resp = client.post(f"/validate/{blueprint_token}?version_tag={version_tag}")
        assert resp.status_code == 404
        mock_version_exists.assert_called_with(blueprint_token, version_tag)

    def test_exception(self, client, mocker):
        blueprint_token = str(uuid.uuid4())
        version_tag = 'version_tag3'
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)

        mock_validate = mocker.MagicMock(name='validate', return_value=(Exception.__class__.__name__, "Exception "
                                                                                                      "stacktrace"))
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.validate', new=mock_validate)
        resp = client.post(f"/validate/{blueprint_token}?version_tag={version_tag}")

        assert resp.status_code == 500
        assert_that(resp.json).contains_only("description", "stacktrace")
        mock_validate.assert_called_with(blueprint_token, version_tag, None)

    def test_ok(self, client, mocker, inputs_1):
        blueprint_token = str(uuid.uuid4())
        version_tag = 'version_tag2'
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mock_validate = mocker.MagicMock(name='validate', return_value=None)
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.validate', new=mock_validate)
        resp = client.post(f"/validate/{blueprint_token}?version_tag={version_tag}", data=inputs_1)

        assert resp.status_code == 200
        assert_that(resp.json).contains_only("message")
        mock_validate.assert_called_with(blueprint_token, version_tag, {'marker': 'blah'})
