import os
import shutil
import uuid
from pathlib import Path

import git
import psutil
import pytest

from opera.api.cli import test
from opera.api.gitCsarDB import GitCsarDB
from opera.api.gitCsarDB.connectors import MockConnector
from opera.api.openapi.models.invocation import Invocation, InvocationState, OperationType
from opera.api.service import sqldb_service
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
    Settings.offline_storage = Path(Settings.API_WORKDIR) / 'storage'
    Settings.workdir = Path(Settings.API_WORKDIR) / "git_db/mockConnector"


@pytest.fixture()
def generic_invocation():
    inv = Invocation()
    inv.state = InvocationState.PENDING
    inv.blueprint_id = str(uuid.uuid4())
    inv.deployment_id = str(uuid.uuid4())
    inv.version_id = 'v1.0'
    inv.operation = OperationType.DEPLOY_FRESH
    inv.timestamp_submission = timestamp_util.datetime_now_to_string()
    return inv


@pytest.fixture()
def patch_auth_wrapper(mocker, generic_invocation: Invocation):
    inv = generic_invocation
    inv.state = InvocationState.SUCCESS
    mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
    mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_deployment_status',
                 return_value=inv)
    mocker.patch('opera.api.service.sqldb_service.OfflineStorage.get_project_domain', return_value=None)


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


@pytest.fixture(scope="session")
def sql_db():
    return sqldb_service.OfflineStorage()


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
