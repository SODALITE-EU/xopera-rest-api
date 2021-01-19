from pathlib import Path
import uuid

import git
import pytest
import os
import shutil
import psutil

from opera.api.cli import test
from opera.api.gitCsarDB import GitCsarDB
from opera.api.gitCsarDB.connectors import MockConnector
from opera.api.util import xopera_util


@pytest.fixture(scope="session")
def client():
    """An application for the tests."""
    try:
        xopera_util.clear_invocation_data()
        xopera_util.init_data()
    except FileExistsError:
        pass
    with test().app.test_client() as client:
        yield client
    kill_tree(os.getpid(), including_parent=False)

    try:
        xopera_util.clear_data()
    except FileExistsError:
        pass


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
def CSAR_unpacked():
    return Path(__file__).parent / 'CSAR_unpacked'


@pytest.fixture
def get_workdir_path():
    workdir_path = Path(__file__).parent / 'workdir' / str(uuid.uuid4())
    os.makedirs(workdir_path)
    yield workdir_path
    shutil.rmtree(workdir_path)


@pytest.fixture
def db():
    return GitCsarDB(connector=MockConnector(workdir=Path(f"/tmp/gitDB/MockConnector/{uuid.uuid4()}")))


@pytest.fixture
def mock():
    return MockConnector(workdir=Path(f'/tmp/gitDB/MockConnector/{uuid.uuid4()}'))


@pytest.fixture
def generic_cloned_repo():
    path_bare = Path(f'/tmp/pytest/{uuid.uuid4()}')
    git.Repo.init(path_bare, bare=True)
    path_cloned = Path(f'/tmp/pytest/{uuid.uuid4()}')
    git.Repo.clone_from(path_bare, path_cloned)
    for i in range(4):
        (path_cloned / Path(f'{i}.txt')).touch()
    return path_cloned


@pytest.fixture
def generic_dir():
    path = Path(f'/tmp/pytest/{uuid.uuid4()}')
    path.mkdir()
    for i in range(4):
        (path / Path(f'{i}-new.txt')).touch()
    return path
