from opera.api.controllers.background_invocation import InvocationService
import uuid
from assertpy import assert_that
import pathlib
from opera.api.openapi.models.invocation import Invocation, InvocationState
from opera.api.settings import Settings
from opera.api.util import timestamp_util, file_util
from pathlib import Path
import json
import pytest


class TestInvocationService:
    dot_opera_data = {
        "root_file": "service.yaml",
        "inputs": "{}",
        "instance": "content"
    }
    session_data = {
        'blueprint_token': 'b5578712-6edb-411b-baf4-329e495ff368',
        'version_tag': 'v1.0'
    }
    instance_state = {
        "hello-host-my-workstation": "initial",
        "hello": "started",
        "my-workstation": "started"
    }
    dot_opera_json = {
        "root_file": "service.yaml",
        "inputs": "{}",
        "instances/hello_0--my-workstation_0": "{\n  \"tosca_name\": {\n    \"is_set\": true,\n    \"data\": \"hello-host-my-workstation\"\n  },\n  \"tosca_id\": {\n    \"is_set\": true,\n    \"data\": \"hello_0--my-workstation_0\"\n  },\n  \"state\": {\n    \"is_set\": true,\n    \"data\": \"initial\"\n  }\n}",
        "instances/hello_0": "{\n  \"tosca_name\": {\n    \"is_set\": true,\n    \"data\": \"hello\"\n  },\n  \"tosca_id\": {\n    \"is_set\": true,\n    \"data\": \"hello_0\"\n  },\n  \"state\": {\n    \"is_set\": true,\n    \"data\": \"started\"\n  },\n  \"component_version\": {\n    \"is_set\": false,\n    \"data\": null\n  },\n  \"admin_credential\": {\n    \"is_set\": false,\n    \"data\": null\n  },\n  \"marker\": {\n    \"is_set\": true,\n    \"data\": \"foo\"\n  }\n}",
        "instances/my-workstation_0": "{\n  \"tosca_name\": {\n    \"is_set\": true,\n    \"data\": \"my-workstation\"\n  },\n  \"tosca_id\": {\n    \"is_set\": true,\n    \"data\": \"my-workstation_0\"\n  },\n  \"state\": {\n    \"is_set\": true,\n    \"data\": \"started\"\n  },\n  \"private_address\": {\n    \"is_set\": true,\n    \"data\": \"localhost\"\n  },\n  \"public_address\": {\n    \"is_set\": true,\n    \"data\": \"localhost\"\n  },\n  \"networks\": {\n    \"is_set\": false,\n    \"data\": null\n  },\n  \"ports\": {\n    \"is_set\": false,\n    \"data\": null\n  }\n}"
    }

    @staticmethod
    def test_stdstream_dir():
        session_token = str(uuid.uuid4())
        path = InvocationService.stdstream_dir(session_token)
        assert_that(path).is_instance_of(pathlib.Path)
        assert_that(str(path)).contains(session_token)

    @staticmethod
    def test_stdout_file():
        session_token = str(uuid.uuid4())
        path = InvocationService.stdout_file(session_token)
        assert_that(path).is_instance_of(pathlib.Path)
        assert_that(str(path)).contains(session_token)

    @staticmethod
    def test_stderr_file():
        session_token = str(uuid.uuid4())
        path = InvocationService.stderr_file(session_token)
        assert_that(path).is_instance_of(pathlib.Path)
        assert_that(str(path)).contains(session_token)

    @staticmethod
    def test_deployment_location():
        session_token = str(uuid.uuid4())
        blueprint_token = str(uuid.uuid4())
        path = InvocationService.deployment_location(session_token, blueprint_token)
        assert_that(path).is_instance_of(pathlib.Path)
        assert path.is_absolute()
        assert_that(str(path)).contains(session_token)
        assert_that(str(path)).contains(blueprint_token)

    @staticmethod
    def test_write_invocation(generic_invocation: Invocation):
        inv = generic_invocation
        inv.session_token = str(uuid.uuid4())
        InvocationService.write_invocation(inv)
        inv_path = Path(Settings.INVOCATION_DIR) / f"invocation-{inv.session_token}.json"
        assert inv_path.is_file()
        inv_saved = Invocation.from_dict(json.loads(inv_path.read_text()))
        assert inv_saved == inv

    @staticmethod
    def test_load_invocation(generic_invocation: Invocation):
        inv = generic_invocation
        inv.session_token = str(uuid.uuid4())
        inv.state = InvocationState.PENDING
        (Path(Settings.INVOCATION_DIR) / f"invocation-{inv.session_token}.json").write_text(json.dumps(inv.to_dict()))
        inv_loaded = InvocationService.load_invocation(inv.session_token)
        assert_that(inv_loaded).is_not_none()
        assert inv_loaded == inv

    @staticmethod
    def test_load_invocation_in_progress(generic_invocation: Invocation):
        inv = generic_invocation
        inv.session_token = str(uuid.uuid4())
        inv.state = InvocationState.IN_PROGRESS
        stdout_text = 'Foo bar'
        stderr_text = 'Exception: "Foo bar" != 42'
        (Path(Settings.INVOCATION_DIR) / f"invocation-{inv.session_token}.json").write_text(json.dumps(inv.to_dict()))
        InvocationService.stdstream_dir(inv.session_token).mkdir(parents=True, exist_ok=True)
        Path(InvocationService.stdout_file(inv.session_token)).write_text(stdout_text)
        Path(InvocationService.stderr_file(inv.session_token)).write_text(stderr_text)

        inv_loaded = InvocationService.load_invocation(inv.session_token)
        assert_that(inv_loaded).is_not_none()
        dict_diff = dict(set(inv_loaded.to_dict().items()) - set(inv.to_dict().items()))
        assert dict_diff == {'stdout': stdout_text, 'stderr': stderr_text}

    @staticmethod
    def test_load_inv_missing():
        session_token = str(uuid.uuid4())
        inv_loaded = InvocationService.load_invocation(session_token)
        assert_that(inv_loaded).is_none()

    @staticmethod
    def test_save_to_database(generic_invocation: Invocation, mocker):
        inv = generic_invocation
        mock_sql_db = mocker.MagicMock(name='update_log', return_value=None)
        mocker.patch('opera.api.service.sqldb_service.OfflineStorage.update_deployment_log', new=mock_sql_db)

        InvocationService.save_to_database(inv)
        logfile = json.dumps(inv.to_dict(), indent=2, sort_keys=False)
        mock_sql_db.assert_called_with(inv.blueprint_token, logfile, inv.session_token, inv.timestamp)

    def test_dot_opera_db_save(self, mocker, generic_invocation: Invocation, get_workdir_path: Path):
        inv = generic_invocation
        # prepare generic '.opera' dir
        path = get_workdir_path
        file_util.json_to_dir(self.dot_opera_data, (path / '.opera'))

        mock_sql_db_save = mocker.MagicMock(name='sql_db_save', return_value=None)
        mocker.patch('opera.api.cli.sqldb_service.OfflineStorage.save_session_data', new=mock_sql_db_save)
        InvocationService.save_dot_opera_to_db(inv, path)

        mock_sql_db_save.assert_called_with(inv.session_token, inv.blueprint_token, inv.version_tag,
                                            self.dot_opera_data)

    def test_dot_opera_db_get(self, mocker, generic_invocation: Invocation, get_workdir_path: Path):
        inv = generic_invocation
        path = get_workdir_path
        data = {
            "tree": self.dot_opera_data,
            "blueprint_token": str(inv.blueprint_token),
            "version_tag": str(inv.version_tag),
            "session_token": str(inv.session_token),
            "timestamp": timestamp_util.datetime_now_to_string()
        }
        mock_sql_db_get = mocker.MagicMock(name='sql_db_get', return_value=data)
        mocker.patch('opera.api.cli.sqldb_service.OfflineStorage.get_session_data', new=mock_sql_db_get)

        InvocationService.get_dot_opera_from_db(inv.session_token, path)

        mock_sql_db_get.assert_called_with(inv.session_token)

        assert_that(file_util.dir_to_json((path / '.opera'))).is_equal_to(data['tree'])

    @staticmethod
    def test_dot_opera_db_get_missing(mocker, get_workdir_path: Path, caplog):
        session_token = str(uuid.uuid4())
        mocker.patch('opera.api.cli.sqldb_service.OfflineStorage.get_session_data', return_value=None)
        with pytest.raises(TypeError):
            InvocationService.get_dot_opera_from_db(session_token, get_workdir_path)
        assert "failed" in caplog.text

    def test_prepare_location(self, mocker, get_workdir_path: Path):
        mock_sql_db_get = mocker.MagicMock(name='sql_db_get', return_value=self.session_data)
        mocker.patch('opera.api.cli.sqldb_service.OfflineStorage.get_session_data', new=mock_sql_db_get)
        mock_csar_exists = mocker.MagicMock(name='csar_exists', return_value=True)
        mocker.patch('opera.api.cli.csardb_service.GitDB.get_revision', new=mock_csar_exists)
        mock_get_dot_opera = mocker.MagicMock(name='dot_opera_get', return_value=True)
        mocker.patch('opera.api.controllers.background_invocation.InvocationService.get_dot_opera_from_db',
                     new=mock_get_dot_opera)

        session_token = str(uuid.uuid4())

        InvocationService.prepare_location(session_token, get_workdir_path)

        mock_sql_db_get.assert_called_with(session_token)
        mock_csar_exists.assert_called_with(self.session_data['blueprint_token'], get_workdir_path,
                                            self.session_data['version_tag'])
        mock_get_dot_opera.assert_called_with(session_token, get_workdir_path)

    def test_preapre_location_fail(self, mocker, get_workdir_path: Path, caplog):
        mocker.patch('opera.api.cli.sqldb_service.OfflineStorage.get_session_data', return_value=self.session_data)
        mocker.patch('opera.api.cli.csardb_service.GitDB.get_revision', return_value=None)

        session_token = str(uuid.uuid4())

        with pytest.raises(KeyError):
            InvocationService.prepare_location(session_token, get_workdir_path)
        assert "failed" in caplog.text


    def test_get_instance_state(self, get_workdir_path: Path):
        file_util.json_to_dir(self.dot_opera_json, (get_workdir_path / '.opera'))
        instance_state = InvocationService.get_instance_state(get_workdir_path)
        assert_that(instance_state).is_equal_to(self.instance_state)
