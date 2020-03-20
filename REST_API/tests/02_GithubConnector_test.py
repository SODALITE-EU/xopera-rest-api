import uuid
from pathlib import Path
from unittest.mock import patch

from Implementation.gitCsarDB.connectors import GithubConnector


def test_repo_exists(github_connection: GithubConnector):
    return
    assert github_connection.repo_exist('test_repo'), "Could not access repo on github, that should exist"


def test_repo_exists_mock(github_connection: GithubConnector):
    return
    with patch('REST_API.Implementation.gitCsarDB.connector.Github', autospec=True) as mock_Github:
        mock_Github.get_repo.side_effect = Exception
        github_connection.repo_exist('test_repo')

        pass


def blah():

    """
    with patch('.git', autospec=True) as github_connection:
        assert github_connection.repo_exist('test_repo')
    """


def test_init_and_delete_repo(github_connection: GithubConnector):
    return
    random_repo_name = uuid.uuid4()
    repo_name = github_connection.init_repo(repo_name=str(random_repo_name))
    assert repo_name == f"{github_connection.username}/{random_repo_name}", "init_repo did not return proper repo name"
    assert github_connection.repo_exist(repo_name=str(random_repo_name)), "Repo creation on github.com failed."
    github_connection.delete_repo(str(random_repo_name))
    assert not github_connection.repo_exist(repo_name=str(random_repo_name)), "Repo deletion on github.com failed."


def test_clone(github_connection: GithubConnector):
    return
    workdir_path = Path(f"/tmp/pytest/{uuid.uuid4()}")
    repo = github_connection.clone(repo_name='test_repo', workdir=workdir_path)
    assert not repo.bare
    assert len([file for file in Path(workdir_path / Path('test_repo')).glob("*")]) > 1, "Repo is emtpy"


def test_add_collaborator(github_connection: GithubConnector):
    pass


if __name__ == '__main__':
    test_repo_exists_mock(REST_API.Implementation.gitCsarDB.connector.GithubConnector(auth_token='e65c05b03ef13e83f6debac203bb9ab0a9028745', username='mihaTrajbaric'))
