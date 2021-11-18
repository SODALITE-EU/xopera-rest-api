import os
import shutil
import uuid
import base64
from pathlib import Path
import psycopg2

import git
import psutil
import pytest

from opera.api.cli import test
from opera.api.gitCsarDB import GitCsarDB
from opera.api.gitCsarDB.connectors import MockConnector
from opera.api.openapi.models import Invocation, InvocationState, OperationType, BlueprintVersion, Deployment
from opera.api.settings import Settings
from opera.api.util import timestamp_util, xopera_util


def pytest_sessionstart(session):
    """
    Called after the Session object has been created and
    before performing collection and entering the run test loop.
    """
    change_API_WORKDIR('.opera-api-pytest')

    shutil.rmtree(Settings.API_WORKDIR, ignore_errors=True)
    xopera_util.init_data()


def pytest_sessionfinish(session, exitstatus):
    """
    Called after whole test run finished, right before
    returning the exit status to the system.
    """
    shutil.rmtree(Settings.API_WORKDIR, ignore_errors=True)


def change_API_WORKDIR(new_workdir: str):
    Settings.API_WORKDIR = new_workdir
    Settings.STDFILE_DIR = f"{Settings.API_WORKDIR}/in_progress"
    Settings.INVOCATION_DIR = f"{Settings.API_WORKDIR}/invocations"
    Settings.DEPLOYMENT_DIR = f"{Settings.API_WORKDIR}/deployment_dir"
    Settings.workdir = Path(Settings.API_WORKDIR) / "git_db/mockConnector"


@pytest.fixture()
def generic_blueprint_meta() -> BlueprintVersion:
    blueprint_meta = BlueprintVersion()
    blueprint_meta.blueprint_id = str(uuid.uuid4())
    blueprint_meta.version_id = 'v1.0'
    blueprint_meta.blueprint_name = 'name'
    blueprint_meta.aadm_id = str(uuid.uuid4())
    blueprint_meta.username = 'username'
    blueprint_meta.project_domain = 'project_domain'
    blueprint_meta.url = 'https://github.com/torvalds/linux'
    blueprint_meta.commit_sha = 'd7c5303fbc8ac874ae3e597a5a0d3707dc0230b4'
    blueprint_meta.timestamp = timestamp_util.datetime_now_to_string()
    return blueprint_meta


@pytest.fixture()
def generic_deployment() -> Deployment:
    dep = Deployment()
    dep.deployment_id = str(uuid.uuid4())
    dep.state = InvocationState.SUCCESS
    # dep.label = 'deployment_label'
    dep.operation = OperationType.DEPLOY_FRESH
    dep.timestamp = timestamp_util.datetime_now_to_string()
    return dep


@pytest.fixture()
def generic_invocation():
    inv = Invocation()
    inv.state = InvocationState.PENDING
    inv.deployment_label = 'TestDeployment'
    inv.blueprint_id = str(uuid.uuid4())
    inv.deployment_id = str(uuid.uuid4())
    inv.version_id = 'v1.0'
    inv.operation = OperationType.DEPLOY_FRESH
    inv.timestamp_submission = timestamp_util.datetime_now_to_string()
    return inv

class FakePostgres:
    def __init__(self, **kwargs):
        pass

    @staticmethod
    def cursor():
        return NoneCursor()

    def commit(self):
        pass

    def close(self):
        pass

# Class to be redefined with custom fetchone or fetchall function
class NoneCursor:
    command = ""
    replacements = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @classmethod
    def execute(cls, command, replacements=None):
        if isinstance(command, psycopg2.sql.Composed):
            cls.command = command._wrapped.__repr__()
        else:
            cls.command = command
        cls.replacements = replacements
        return None

    @classmethod
    def fetchone(cls):
        return None

    @classmethod
    def fetchall(cls):
        return []

    @classmethod
    def close(cls):
        pass

    @classmethod
    def get_command(cls):
        """This method does not exist in real Cursor object, for testing purposes only"""
        return cls.command

    @classmethod
    def get_replacements(cls):
        """This method does not exist in real Cursor object, for testing purposes only"""
        return cls.replacements


@pytest.fixture()
def patch_db(mocker):
    mocker.patch('psycopg2.connect', new=FakePostgres)


@pytest.fixture()
def patch_auth_wrapper(mocker, generic_invocation: Invocation):
    mocker.patch('psycopg2.connect', new=FakePostgres)
    inv = generic_invocation
    inv.state = InvocationState.SUCCESS
    mocker.patch('opera.api.service.sqldb_service.PostgreSQL.version_exists', return_value=True)
    mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
    mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_deployment_status',
                 return_value=inv)
    mocker.patch('opera.api.service.sqldb_service.PostgreSQL.get_project_domain', return_value=None)


@pytest.fixture()
def mock_api_workdir():
    old_workdir = Settings.API_WORKDIR
    path = workdir_path()
    change_API_WORKDIR(path)
    yield path
    change_API_WORKDIR(old_workdir)


@pytest.fixture()
def mock_ssh_keys_loc():
    old_ssh_workdir = Settings.ssh_keys_location
    temp_path = workdir_path()
    Settings.ssh_keys_location = temp_path
    yield temp_path
    Settings.ssh_keys_location = old_ssh_workdir
    Settings.key_pair = ""


@pytest.fixture(scope="session")
def client(session_mocker):
    """An application for the tests."""
    os.environ['LOG_LEVEL'] = 'debug'
    session_mocker.patch('connexion.decorators.security.get_authorization_info', return_value={'scope': ['apiKey']})
    Settings.USE_OFFLINE_STORAGE = True
    with test().app.test_client() as client:
        yield client
    kill_tree(os.getpid(), including_parent=False)


def kill_tree(pid, including_parent=True):
    parent = psutil.Process(pid)
    for child in parent.children(recursive=True):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass

    if including_parent:
        parent.kill()


@pytest.fixture
def csar_1():
    return file_data('CSAR-hello_fast.zip')


@pytest.fixture
def csar_2():
    return file_data('CSAR-hello_fast.zip')


@pytest.fixture
def csar_3():
    return file_data('CSAR-hello_fast.zip')


@pytest.fixture
def csar_inputs():
    return file_data('CSAR-hello_inputs.zip')


@pytest.fixture
def inputs_1():
    return file_data('hello_inputs.yaml', file_type='inputs_file')


@pytest.fixture
def inputs_2():
    return file_data('hello_inputs.yaml', file_type='inputs_file')


@pytest.fixture
def csar_corrupt():
    return file_data('CSAR-hello_corrupt.zip')


@pytest.fixture
def csar_empty():
    return file_data('CSAR-empty.zip')


@pytest.fixture
def csar_no_meta():
    return file_data('CSAR-no-meta.zip')


@pytest.fixture
def csar_clean_state():
    return file_data('CSAR-clean-state.zip')


def file_data(file_name, file_type='CSAR'):
    path_to_csar = Path(__file__).parent / 'CSAR' / file_name
    data = {file_type: (open(path_to_csar, 'rb'), file_name)}
    return data


@pytest.fixture
def csar_unpacked():
    return Path(__file__).parent / 'csar_unpacked'


@pytest.fixture
def get_workdir_path():
    return workdir_path()


def workdir_path():
    path = Path(f"{Settings.API_WORKDIR}/pytest/{uuid.uuid4()}")
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def db():
    return GitCsarDB(connector=MockConnector(workdir=workdir_path()))


@pytest.fixture
def mock():
    return MockConnector(workdir=workdir_path())


@pytest.fixture
def generic_cloned_repo():
    path_bare = workdir_path()
    git.Repo.init(path_bare, bare=True)
    path_cloned = workdir_path()
    git.Repo.clone_from(path_bare, path_cloned)
    for i in range(4):
        (path_cloned / Path(f'{i}.txt')).touch()
    return path_cloned


@pytest.fixture
def generic_dir():
    path = workdir_path()
    for i in range(4):
        (path / Path(f'{i}-new.txt')).touch()
    return path


@pytest.fixture
def inputs_no_secret():
    inputs = {
        "frontend-address": "14.15.11.12",
        "user": "test_user"
    }

    return inputs


@pytest.fixture
def inputs_with_secret():
    inputs = {
        "frontend-address": "14.15.11.12",
        "user": "test_user",
        "_get_secret_ssh": "pds/ssh_key_slurm:pds"
    }

    return inputs

@pytest.fixture
def valid_ssh_key():
    key = ( 'Ci0tLS0tQkVHSU4gUlNBIFBSSVZBVEUgS0VZLS0tLS0KTUlJRW93SUJBQUtDQVFFQXhhYVZVcDhPTXF0UG5ZZk'
            'Y4cW1KYzhSdXRBeXc0dXZ6cUxXRGJ5NnZvZktuazZPSgpmcEtzUzkxZ1lXMWg1eE1CTi9sMmRGMjc4K2p6aTByU'
            'EIrMVdRL0l6cW5zYTR0NzJSeFUzdFhGQndjN0JpVDFhCktwRWF0cm92aE4xU1pGNTJnaWRCTFE2QTF0ekFvalNLO'
            'HY3M1o2WFdHSzFaN0JIenZDb1dqZkxoQkZVeVl5OU0KbnFNaFJub2U2UUZaejFZWGJwUFVrS3VqVm5lMUN4b1VFNH'
            'BUeklnamJaWEdLbTVDZFhjN2l6RnhBUzhvRDRYRwpHU1d0b3VROStNTmw5Ym5xRTNINVZsNXlMOVFWQ2xYdElYQWJ'
            'BNjluV1BoNk9YbSs3bkxpNTZ1L09oNDVjNGtuCjczK0JiWWNKQ0FsQXJMbEc1WVVJRzNpTkNYOUYwWmlxaTBqOFJ3'
            'SURBUUFCQW9JQkFGUUNpbFdqNVpVRDI4TkoKZ29teUpncGU0KzhEdGV1OS9zTW00OGJPUVRqRXV4VzEzU3Mvakp4eW'
            'JCVDlPUy9PbENZR2txTERkTEFudzl6ZwozejZ2VW90dTF5Y1BURTVDRnN2LzZMM21kZHk2MU9oUWU1SzhPbTZRbE1JV'
            'WtJQzQ1Z1pNU1JldG9uV3hQdSt6CkJaeGpZeVZiQjdWVmVYTXQ3anQ4YURuTmtuY1VQL2Rqbzd0QVZkZjZuNEVORjlL'
            'VHZ0Yy9YSXJTNytLclhHVnkKQ2ozOUE4Y0pyQnE0VWlKQW1LNmZpTFI2MC8xMXRDUWRiRDZkNWVTNGdwUzZyUXVUYis'
            '2aXBZZGtRWHFXZzJpbgpnclVhWThRQ01EOGZpT2J5cEdxTVVBemZlMTA4czBianc0ZHcwRFlmWjJxQXdVanRFdHQzej'
            'loNmVzRzUyazJuCjFkWVp2UUVDZ1lFQTY4bkpBQ1hZRVZJVEIxbW1WbnZNaEJPbTRaRHhqSlBoK2ZiQ3k2SU93MTFQZ'
            '1NUeHQ2VjgKQXQxN1BKM0lPdWMrN0hGNGxEeTA4UmxGVm43M1RSMnVLaTl1UWFVUHpobWdpb0E3NnQ2ckhXbjFHMW5'
            'STDdhWgozazVIa0x5QkhMeVF5eDZ4OXdLMWg4R3J2ZDBkTVRyU0dNVExrb2h4aGFqdURpZnd5Z3NIWmI4Q2dZRUExcG'
            'ZsClkwWUd3RlFmYWZGMnVPMFhCRlJUUVd6NzNZSmZDaTQ4RlVXK21WM2t5b2hxbDV5OThyS3JwTUQ0eXlBc0VIR2gKY'
            'U9RajhHdFlRY2p1VjIwa1dNdVU5T3ExN2c4M2g1czBoTjE3K2ZCdGdIcUdEekdaN1pkWENzVFVaSGdKclR0OApFNCtH'
            'UkFMRERlZzhyWksxWHlsTlI0d3JLK0RrZXNxNGRlb2hXM2tDZ1lFQXpVM2QzbXNWUDcrZklmOUZmbmc5CkU2T280eTg'
            '1bzVZQVpZNGUvd0FVcXJkTXlyNUlXZ2VWZTBrdVRSRjFqeFJiRGJXZnNETkx1Y0t2UlNrNFc4VkUKS1NjemNhVXZwZDF'
            'hbEQ0ajdkWUVXSkF5QTZhcEprcHduOGk1TjZWckpvSnA4UExCTXJzQkpUdlZOblNaUG94Zwo4NEFuWVdlOHNRenVleFQ'
            '3N0hDOStERUNnWUFFUFlZajJ3dGhHNGh2WUgwWEZHQkREcU9DaEhQSm9iemRCNkxhClRNR0NhRStRRFBnR1BPdW44dzNm'
            'T0l6eC9wWEFVVzUrRXh2K3NUQlNSSFVwTnhmanhVb1JPTjRWY1NtSXZYRmgKT3JzcmFpdlB3UndMQ3REZTJBRzVUY0Jnc'
            'DlxUkdMN1A2Q01nRHVucHlYQUJnZ2VoZE1CNUxIVGg3aFMxdEhIRwpxclMwQ1FLQmdFV1ZueWZocnIvNk0rVzZ2WU5GUG'
            '9PaWliYlNNcHZBb1JPbXJXR01IME9xT2pkT1pkUnpkck14Ckoxa1dQa2ZZVzdEaTRFRkN2OUVWV2dyWUs1QUFZN2NSL3R'
            '5TzdyWjhqV1ZjRU02MWJSdkRLa1hycTRDOWZ0Rm4KYjdBN3Z5b0lWa092d3NnYVNBL00xeEJBUFNJQlJGZ3c2NHpOa1Qyd'
            '20rN1ZmVmxPS2p3WQotLS0tLUVORCBSU0EgUFJJVkFURSBLRVktLS0tLQo=' )
    return base64.b64decode(key.encode()).decode("utf-8")


@pytest.fixture
def invalid_ssh_key():
    key = """
MIIEowIBAAKCAQEAxaaVUp8OMqtPnYfF8qmJc8RutAyw4uvzqLWDby6vofKnk6OJ
"""
    return key
