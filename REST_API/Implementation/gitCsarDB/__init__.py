from pathlib import Path

from .connectors import GithubConnector, GitlabConnector, MockConnector
from .main import GitCsarDB


def connect(**kwargs):
    if kwargs['type'] == 'gitlab':
        connector = GitlabConnector(url=kwargs['url'], auth_token=kwargs['auth_token'])
    elif kwargs['type'] == 'github':
        connector = GithubConnector(auth_token=kwargs['auth_token'])
    elif kwargs['type'] == 'mock':
        connector = MockConnector(workdir=Path(kwargs['mock_workdir']))
    else:
        raise GitCsarDB.UnsupportedConnectorType(
            f'Unsupported gitCsarDB type, supported: "gitlab", "github", "mock", requested: {kwargs["type"]}')
    try:
        return GitCsarDB(connector=connector, workdir=kwargs['workdir'], repo_prefix=kwargs['repo_prefix'],
                         commit_name=kwargs['commit_name'], commit_mail=kwargs['commit_mail'])
    except KeyError:
        return GitCsarDB(connector=connector)
