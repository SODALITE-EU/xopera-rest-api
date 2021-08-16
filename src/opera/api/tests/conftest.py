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
    Settings.offline_storage = Path(Settings.API_WORKDIR) / 'storage'
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


@pytest.fixture()
def patch_auth_wrapper(mocker, generic_invocation: Invocation):
    inv = generic_invocation
    inv.state = InvocationState.SUCCESS
    mocker.patch('opera.api.service.csardb_service.GitDB.version_exists', return_value=True)
    mocker.patch('opera.api.service.sqldb_service.Database.get_deployment_status',
                 return_value=inv)
    mocker.patch('opera.api.service.sqldb_service.Database.get_project_domain', return_value=None)


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
    key = """
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAxaaVUp8OMqtPnYfF8qmJc8RutAyw4uvzqLWDby6vofKnk6OJ
fpKsS91gYW1h5xMBN/l2dF278+jzi0rPB+1WQ/Izqnsa4t72RxU3tXFBwc7BiT1a
KpEatrovhN1SZF52gidBLQ6A1tzAojSK8v73Z6XWGK1Z7BHzvCoWjfLhBFUyYy9M
nqMhRnoe6QFZz1YXbpPUkKujVne1CxoUE4pTzIgjbZXGKm5CdXc7izFxAS8oD4XG
GSWtouQ9+MNl9bnqE3H5Vl5yL9QVClXtIXAbA69nWPh6OXm+7nLi56u/Oh45c4kn
73+BbYcJCAlArLlG5YUIG3iNCX9F0Ziqi0j8RwIDAQABAoIBAFQCilWj5ZUD28NJ
gomyJgpe4+8Dteu9/sMm48bOQTjEuxW13Ss/jJxybBT9OS/OlCYGkqLDdLAnw9zg
3z6vUotu1ycPTE5CFsv/6L3mddy61OhQe5K8Om6QlMIUkIC45gZMSRetonWxPu+z
BZxjYyVbB7VVeXMt7jt8aDnNkncUP/djo7tAVdf6n4ENF9KTvtc/XIrS7+KrXGVy
Cj39A8cJrBq4UiJAmK6fiLR60/11tCQdbD6d5eS4gpS6rQuTb+6ipYdkQXqWg2in
grUaY8QCMD8fiObypGqMUAzfe108s0bjw4dw0DYfZ2qAwUjtEtt3z9h6esG52k2n
1dYZvQECgYEA68nJACXYEVITB1mmVnvMhBOm4ZDxjJPh+fbCy6IOw11PgSTxt6V8
At17PJ3IOuc+7HF4lDy08RlFVn73TR2uKi9uQaUPzhmgioA76t6rHWn1G1nRL7aZ
3k5HkLyBHLyQyx6x9wK1h8Grvd0dMTrSGMTLkohxhajuDifwygsHZb8CgYEA1pfl
Y0YGwFQfafF2uO0XBFRTQWz73YJfCi48FUW+mV3kyohql5y98rKrpMD4yyAsEHGh
aOQj8GtYQcjuV20kWMuU9Oq17g83h5s0hN17+fBtgHqGDzGZ7ZdXCsTUZHgJrTt8
E4+GRALDDeg8rZK1XylNR4wrK+Dkesq4deohW3kCgYEAzU3d3msVP7+fIf9Ffng9
E6Oo4y85o5YAZY4e/wAUqrdMyr5IWgeVe0kuTRF1jxRbDbWfsDNLucKvRSk4W8VE
KSczcaUvpd1alD4j7dYEWJAyA6apJkpwn8i5N6VrJoJp8PLBMrsBJTvVNnSZPoxg
84AnYWe8sQzuexT77HC9+DECgYAEPYYj2wthG4hvYH0XFGBDDqOChHPJobzdB6La
TMGCaE+QDPgGPOun8w3fOIzx/pXAUW5+Exv+sTBSRHUpNxfjxUoRON4VcSmIvXFh
OrsraivPwRwLCtDe2AG5TcBgp9qRGL7P6CMgDunpyXABggehdMB5LHTh7hS1tHHG
qrS0CQKBgEWVnyfhrr/6M+W6vYNFPoOiibbSMpvAoROmrWGMH0OqOjdOZdRzdrMx
J1kWPkfYW7Di4EFCv9EVWgrYK5AAY7cR/tyO7rZ8jWVcEM61bRvDKkXrq4C9ftFn
b7A7vyoIVkOvwsgaSA/M1xBAPSIBRFgw64zNkT2wm+7VfVlOKjwY
-----END RSA PRIVATE KEY-----
"""
    return key


@pytest.fixture
def invalid_ssh_key():
    key = """
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAxaaVUp8OMqtPnYfF8qmJc8RutAyw4uvzqLWDby6vofKnk6OJ
-----END RSA PRIVATE KEY-----
"""
    return key
