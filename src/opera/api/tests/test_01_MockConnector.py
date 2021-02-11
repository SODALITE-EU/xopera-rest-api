import json
from pathlib import Path

import git

from opera.api.gitCsarDB.connectors import MockConnector


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
    assert not mock.repo_exist(repo_name), "method 'repo_exists' returned True on nonexistent repo"


def test_repo_exists_true(mock: MockConnector):
    repo_name = 'test_repo'
    assert mock.init_repo(repo_name), "Could not create repo, test useless"
    assert mock.repo_exist(repo_name), "method 'repo_exists' returned False on existing repo"


def test_add_collaborator(mock: MockConnector):
    repo_name = 'test_repo'
    username = 'random_user'
    assert mock.init_repo(repo_name), "Could not create repo, test useless"
    collaborators = json.load(mock.collab_file.open('r'))
    assert repo_name in collaborators, "No 'repo_name' key in collaborators dict"
    assert 'random_name' not in collaborators, "Non existing repo key exist in collaborators"
    assert not collaborators[repo_name], "List with collaborators not empty"
    assert mock.add_collaborator(repo_name, username), "Did not return True on success"
    collaborators = json.load(mock.collab_file.open('r'))
    assert len(collaborators[repo_name]) == 1, "List with collaborators should contain just one element"
    assert collaborators[repo_name][0] == username, 'Username was not saved properly'
    assert mock.add_collaborator(repo_name, username), "Did not ignore adding existing user"
    collaborators = json.load(mock.collab_file.open('r'))
    assert len(collaborators[repo_name]) == 1, "repo should have just one collaborator"

    # test adding user to nonexistent repo
    assert not mock.add_collaborator("nonexistent_repo", username)


def test_delete_collaborators(mock: MockConnector, mocker):
    # set up test
    mocker.patch('opera.api.gitCsarDB.connectors.MockConnector.repo_exist', return_value=True)
    repo_name = 'foo'
    user_names = [f"user_{i}" for i in range(5)]
    collaborators = json.load(mock.collab_file.open('r'))
    collaborators[repo_name] = user_names
    json.dump(collaborators, mock.collab_file.open('w'))

    # run test
    assert mock.get_collaborators(repo_name) == user_names
    mock.delete_collaborator(repo_name, user_names[-1])
    assert mock.get_collaborators(repo_name) == user_names[:-1]


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

    # test getting user from nonexistent repo
    assert len(mock.get_collaborators("nonexistent_repo")) == 0


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
    repo = mock.clone(repo_name, repo_dst=desired_path)
    assert repo is not None
    assert not repo.bare, "Repo does not exist"


def test_clone_non_existing(mock: MockConnector):
    repo_name = 'test_repo'
    assert not mock.repo_exist(repo_name), "Repo exists, test useless"

    desired_path = Path(mock.workdir / 'mock_repo')
    repo = mock.clone(repo_name, repo_dst=desired_path)
    assert repo is None, "Repo exists"


def test_tag_exists(mock: MockConnector):
    repo_name = 'test_repo'
    mock.init_repo(repo_name)
    assert not mock.tag_exists(repo_name, 'tag'), "Repo should have no tags"
    desired_path = Path(mock.workdir / 'mock_repo')
    repo = mock.clone(repo_name, repo_dst=desired_path)

    # add some commit
    (desired_path / "file.txt").touch()
    repo.git.add('--all')
    commit_obj = repo.index.commit(message='commit_msg')
    commit_sha = str(commit_obj)
    repo.remotes.origin.push()
    mock.add_tag(repo_name, commit_sha, tag='v1.0', tag_msg='tag msg')
    # assert mock.get_tag_msg(repo_name) == 'tag msg'
    assert mock.tag_exists(repo_name, 'v1.0')

    # add another commit
    (desired_path / "file2.txt").touch()
    repo.git.add('--all')
    commit_obj = repo.index.commit(message='commit_msg')
    commit_sha = str(commit_obj)
    repo.remotes.origin.push()

    assert not mock.tag_exists(repo_name, 'v1.1')
    mock.add_tag(repo_name, commit_sha, tag='v1.1', tag_msg='another tag msg')
    assert mock.get_tag_msg(repo_name) == 'another tag msg'
    assert mock.tag_exists(repo_name, 'v1.1')
    assert mock.tag_exists(repo_name, 'v1.0')


def test_get_tag_msg(mock: MockConnector):
    repo_name = 'test_repo'
    mock.init_repo(repo_name)
    assert mock.get_tag_msg(repo_name) is None, "Repo should have no tags"
    desired_path = Path(mock.workdir / 'mock_repo')
    repo = mock.clone(repo_name, repo_dst=desired_path)

    # add some commit
    (desired_path / "file.txt").touch()
    repo.git.add('--all')
    commit_obj = repo.index.commit(message='commit_msg')
    commit_sha = str(commit_obj)
    repo.remotes.origin.push()

    mock.add_tag(repo_name, commit_sha, tag='v1.0', tag_msg='tag msg')
    assert mock.get_tag_msg(repo_name) == 'tag msg'
    assert mock.get_tag_msg(repo_name, 'v1.0') == 'tag msg'

    # add another commit
    (desired_path / "file2.txt").touch()
    repo.git.add('--all')
    commit_obj = repo.index.commit(message='commit_msg')
    commit_sha = str(commit_obj)
    repo.remotes.origin.push()

    mock.add_tag(repo_name, commit_sha, tag='v1.1', tag_msg='another tag msg')
    assert mock.get_tag_msg(repo_name) == 'another tag msg'
    assert mock.get_tag_msg(repo_name, 'v1.1') == 'another tag msg'
    assert mock.get_tag_msg(repo_name, 'v1.0') == 'tag msg'


def test_get_commits_list(mock: MockConnector):
    repo_name = 'test_repo'
    mock.init_repo(repo_name)
    repo_path = Path(mock.workdir / 'mock_repo')
    repo = mock.clone(repo_name, repo_dst=repo_path)

    # add some commit
    (repo_path / "file.txt").touch()
    repo.git.add('--all')
    commit_msg = 'commit_msg'
    commit_obj = repo.index.commit(message=commit_msg)
    commit_sha = str(commit_obj)
    repo.remotes.origin.push()

    commit_list = mock.get_commits_list(repo_name)
    assert len(commit_list) == 1
    assert commit_list[0][0] == commit_sha
    assert commit_list[0][1] == commit_msg
