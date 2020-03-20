from pathlib import Path

import git

from Implementation.gitCsarDB.connectors import MockConnector


def test_init_new(mock: MockConnector):
    repo_name = 'test_repo'
    assert mock.init_repo(repo_name), "Could not create 'test_repo'"
    repo_path = mock.workdir / Path(repo_name)
    assert repo_path.exists(), 'Repo path is empty'
    assert git.Repo(repo_path).bare, 'Repo is not bare'


def test_init_existing(mock: MockConnector):
    repo_name = 'test_repo'
    assert mock.init_repo(repo_name), "Could not create 'test_repo', test useless"
    assert not mock.init_repo(repo_name), "method 'init_repo' did not block attempt to reinitialize " \
                                                    "existing repository "


def test_repo_exists_false(mock: MockConnector):
    repo_name = 'test_repo'
    assert not mock.repo_exist(repo_name), "method 'repo_exists' returned True on nonexisting repo"


def test_repo_exists_true(mock: MockConnector):
    repo_name = 'test_repo'
    assert mock.init_repo(repo_name), "Could not create repo, test useless"
    assert mock.repo_exist(repo_name), "method 'repo_exists' returned False on existing repo"


def test_add_collaborator(mock: MockConnector):
    repo_name = 'test_repo'
    username = 'random_user'
    assert mock.init_repo(repo_name), "Could not create repo, test useless"
    assert repo_name in mock.collaborators, "No 'repo_name' key in collaborators dict"
    assert not 'random_name' in mock.collaborators, "Non existing repo key exist in collaborators"
    assert not mock.collaborators[repo_name], "List with collaborators not empty"
    assert mock.add_collaborator(repo_name, username), "Did not return True on success"
    assert len(mock.collaborators[repo_name]) == 1, "List with collaborators should contain just one element"
    assert mock.collaborators[repo_name][0] == username, 'Username was not saved properly'
    assert mock.add_collaborator(repo_name, username), "Did not ignore adding existing user"
    assert len(mock.collaborators[repo_name]) == 1, "repo should have just one collaborator"


def test_get_collaborators(mock: MockConnector):
    repo_name = 'test_repo'
    username1 = 'username1'
    username2 = 'username2'
    mock.init_repo(repo_name)
    mock.add_collaborator(repo_name, username1)
    assert mock.get_collaborators(repo_name)[0] == username1
    mock.add_collaborator(repo_name, username2)
    collaborators = mock.get_collaborators(repo_name)
    assert len(collaborators) == 2
    assert collaborators[0] == username1
    assert collaborators[1] == username2


def test_delete_existing_repo(mock: MockConnector):
    repo_name = 'test_repo'
    mock.init_repo(repo_name)
    assert mock.repo_exist(repo_name), "Could not create repo, test useless"
    assert mock.delete_repo(repo_name) == 0, "Could not delete repo"
    assert not mock.repo_exist(repo_name), "Repo still exist, deletion failed"


def test_delete_non_existing_repo(mock: MockConnector):
    repo_name = 'test_repo'
    assert not mock.repo_exist(repo_name), "Repo existed, test useless"
    assert not mock.delete_repo(repo_name), "Did not fail on deletion of non existing repo"


def test_clone(mock: MockConnector):
    repo_name = 'test_repo'
    mock.init_repo(repo_name)
    assert mock.repo_exist(repo_name), "Could not create repo, test useless"

    desired_path = Path(mock.workdir / 'mock_repo')
    repo = mock.clone(repo_name, workdir=desired_path)
    assert repo is not None
    assert not repo.bare, "Repo does not exist"


def test_clone_non_existing(mock: MockConnector):
    repo_name = 'test_repo'
    assert not mock.repo_exist(repo_name), "Repo exists, test useless"

    desired_path = Path(mock.workdir / 'mock_repo')
    repo = mock.clone(repo_name, workdir=desired_path)
    assert repo is None, "Repo exists"
