import uuid

from assertpy import assert_that


class TestValidateExisting:

    def test_no_blueprint(self, client, mocker):
        blueprint_id = uuid.uuid4()
        mock_version_exists = mocker.MagicMock(name='version_exists', return_value=False)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', new=mock_version_exists)

        resp = client.put(f"blueprint/{blueprint_id}/validate")
        assert resp.status_code == 404
        mock_version_exists.assert_called_with(str(blueprint_id), None)

    def test_exception(self, client, mocker):
        blueprint_id = uuid.uuid4()
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mock_validate = mocker.MagicMock(name='validate',
                                         return_value="{}: {}".format(Exception.__class__.__name__,
                                                                      "Exception stacktrace"))

        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.validate', new=mock_validate)
        resp = client.put(f"/blueprint/{blueprint_id}/validate")

        assert resp.status_code == 200
        assert_that(resp.json).contains_only("blueprint_valid", "error")
        assert_that(resp.json['blueprint_valid']).is_false()
        assert_that(resp.json['error']).contains("Exception stacktrace")
        mock_validate.assert_called_with(str(blueprint_id), None, None)

    def test_ok(self, client, mocker, inputs_1):
        blueprint_token = uuid.uuid4()
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mock_validate = mocker.MagicMock(name='validate', return_value=None)
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.validate', new=mock_validate)
        resp = client.put(f"/blueprint/{blueprint_token}/validate", data=inputs_1)

        assert resp.status_code == 200
        assert_that(resp.json).contains_only("blueprint_valid")
        assert_that(resp.json['blueprint_valid']).is_true()
        mock_validate.assert_called_with(str(blueprint_token), None, {'marker': 'blah'})


class TestValidateExistingVersion:

    def test_no_blueprint(self, client, mocker):
        blueprint_id = uuid.uuid4()
        version_id = 'v1.0'
        mock_version_exists = mocker.MagicMock(name='version_exists', return_value=False)
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', new=mock_version_exists)

        resp = client.put(f"blueprint/{blueprint_id}/version/{version_id}/validate")
        assert resp.status_code == 404
        mock_version_exists.assert_called_with(str(blueprint_id), version_id)

    def test_exception(self, client, mocker):
        blueprint_id = uuid.uuid4()
        version_id = 'v1.0'
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mock_validate = mocker.MagicMock(name='validate',
                                         return_value="{}: {}".format(Exception.__class__.__name__,
                                                                      "Exception stacktrace"))
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.validate', new=mock_validate)
        resp = client.put(f"/blueprint/{blueprint_id}/version/{version_id}/validate")

        assert resp.status_code == 200
        assert_that(resp.json).contains_only("blueprint_valid", "error")
        assert_that(resp.json['blueprint_valid']).is_false()
        assert_that(resp.json['error']).contains("Exception stacktrace")
        mock_validate.assert_called_with(str(blueprint_id), version_id, None)

    def test_ok(self, client, mocker, inputs_1):
        blueprint_token = uuid.uuid4()
        version_id = 'v1.0'
        mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
        mock_validate = mocker.MagicMock(name='validate', return_value=None)
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.validate', new=mock_validate)
        resp = client.put(f"/blueprint/{blueprint_token}/version/{version_id}/validate", data=inputs_1)

        assert resp.status_code == 200
        assert_that(resp.json).contains_only("blueprint_valid")
        assert_that(resp.json['blueprint_valid']).is_true()
        mock_validate.assert_called_with(str(blueprint_token), version_id, {'marker': 'blah'})


class TestValidateNew:

    def test_exception(self, client, mocker, csar_1):
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.validate_new',
                     return_value="{}: {}".format(Exception.__class__.__name__, "Exception stacktrace"))
        resp = client.put(f"/blueprint/validate", data=csar_1)

        assert resp.status_code == 200
        assert_that(resp.json).contains_only("blueprint_valid", "error")
        assert_that(resp.json['blueprint_valid']).is_false()
        assert_that(resp.json['error']).contains("Exception stacktrace")

    def test_ok(self, client, mocker, csar_1):
        mocker.patch('opera.api.controllers.background_invocation.InvocationWorkerProcess.validate', return_value=None)
        resp = client.put(f"/blueprint/validate", data=csar_1)

        assert resp.status_code == 200
        assert_that(resp.json).contains_only("blueprint_valid")
        assert_that(resp.json['blueprint_valid']).is_true()
