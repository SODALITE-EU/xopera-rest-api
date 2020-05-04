import uuid
from pathlib import Path

import gitCsarDB as gitCsarDB
from gitCsarDB import GitCsarDB


def test_connect_function():
    db_mock = gitCsarDB.connect(type='mock', mock_workdir='/tmp/blah')
    assert isinstance(db_mock, GitCsarDB)
    assert isinstance(db_mock.git_connector, gitCsarDB.MockConnector)


def test_default_params(db: GitCsarDB):
    assert db.workdir == Path("/tmp/git_db")
    assert db.repo_prefix == 'gitDB_'


def test_token_to_repo_name(db: GitCsarDB):
    token = uuid.uuid4()
    assert db.repo_name(token) == db.repo_prefix + str(token)


def test_repo_name_to_token(db: GitCsarDB):
    assert db.csar_token('wrong_string') is None

    token = uuid.uuid4()
    repo_name = db.repo_prefix + str(token)
    assert db.csar_token(repo_name) == token


def test_empty_repo(db: GitCsarDB, generic_cloned_repo: Path):
    path = Path(generic_cloned_repo)
    assert len([file for file in path.glob("[!.git]*")]) is not 0, "Repo was emtpy before test, could not test"
    db.make_repo_emtpy(path)
    assert len([file for file in path.glob("[!.git]*")]) is 0, "Did not make repo empty"
    assert len([file for file in path.glob("*")]) is not 0, "Also deleted .git subdir"


def test_copy_content(db: GitCsarDB, generic_cloned_repo: Path, generic_dir: Path):
    path = Path(generic_cloned_repo)
    assert len([file for file in path.glob("*-new*")]) is 0, "Repo had new files before test, could not test"
    db.copy_content(Path(generic_dir), path)
    assert len([file for file in path.glob("*-new*")]) is not 0, "Copy failed"


def test_save_new_CSAR(db: GitCsarDB, generic_dir: Path):
    csar_token = uuid.uuid4()
    assert not db.CSAR_exists(csar_token), f"Repo with token {csar_token} already existed, test useless"

    db.save_CSAR(csar_path=generic_dir, csar_token=csar_token)

    assert db.CSAR_exists(csar_token), "Did not correctly saved repo"


def test_get_CSAR(db: GitCsarDB, generic_dir: Path):
    csar_token = uuid.uuid4()
    db.save_CSAR(csar_path=generic_dir, csar_token=csar_token)
    assert db.CSAR_exists(csar_token), "Did not correctly saved repo, test useless"

    repo_path = db.get_CSAR(csar_token=csar_token)
    assert len([file for file in repo_path.glob("[!.git]*")]) > 0, "Repo empty"


def test_save_update_CSAR(db: GitCsarDB, generic_dir: Path):
    csar_token = uuid.uuid4()
    db.save_CSAR(csar_path=generic_dir, csar_token=csar_token)
    assert db.CSAR_exists(csar_token), "Did not correctly saved repo, test useless"
    db.save_CSAR(csar_path=generic_dir, csar_token=csar_token)

    repo_path = db.get_CSAR(csar_token=csar_token, version_tag='v2.0')
    assert len([file for file in repo_path.glob("[!.git]*")]) > 0, "Repo empty"


def test_delete_CSAR(db: GitCsarDB, generic_dir: Path):
    csar_token = uuid.uuid4()
    db.save_CSAR(csar_path=generic_dir, csar_token=csar_token)
    assert db.CSAR_exists(csar_token), "Did not correctly saved repo, test useless"

    assert db.delete_repo(csar_token), "Could not delete"


def test_add_user(db: GitCsarDB, generic_dir: Path):
    csar_token = uuid.uuid4()
    generic_user = 'username'
    db.save_CSAR(csar_path=generic_dir, csar_token=csar_token)
    assert db.CSAR_exists(csar_token), "Did not correctly saved repo, test useless"

    assert db.add_user(csar_token, generic_user), "could not save user"
