import uuid
from pathlib import Path

import git
import pytest

from Implementation.gitCsarDB import GitCsarDB
from Implementation.gitCsarDB.connectors import GithubConnector
from Implementation.gitCsarDB.connectors import MockConnector


@pytest.fixture
def db():
    return GitCsarDB(connector=MockConnector(workdir=Path(f"/tmp/gitDB/MockConnector/{uuid.uuid4()}")))


@pytest.fixture
def github_connection():
    return GithubConnector(auth_token='some_token')


@pytest.fixture
def mock():
    return MockConnector(workdir=Path(f'/tmp/gitDB/MockConnector/{uuid.uuid4()}'))


@pytest.fixture
def generic_bare_repo():
    path_bare = Path(f'/tmp/pytest/{uuid.uuid4()}')
    git.Repo.init(path_bare, bare=True)
    return path_bare


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