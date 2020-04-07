from pathlib import Path

from .connectors import GithubConnector, GitlabConnector, MockConnector
from .main import GitCsarDB


def connect(**kwargs):
    if kwargs['type'] == 'gitlab':
        connector = GitlabConnector(url=kwargs['url'], auth_token=kwargs['auth_token'])
    elif kwargs['type'] == 'github':
        connector = GithubConnector(auth_token=kwargs['auth_token'])
    elif kwargs['type'] == 'mock':
        connector = MockConnector(workdir=Path(kwargs['workdir']))
    else:
        raise GitCsarDB.UnsupportedConnectorType(f'Unsupported gitCsarDB type, supported: "gitlab", "github", "mock", requested: {kwargs["type"]}')

    return GitCsarDB(connector=connector)
