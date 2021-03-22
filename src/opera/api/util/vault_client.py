import requests
import urllib.parse

from requests.exceptions import ConnectionError

from opera.api.settings import Settings
from opera.api.log import get_logger

adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
session = requests.Session()
for protocol in Settings.connection_protocols:
    session.mount(protocol, adapter)

logger = get_logger(__name__)


def get_secret(secret_path, vault_role, access_token) -> dict:
    logger.info("Obtaining secret from Vault")
    if access_token is None:
        raise ValueError(
            "Vault secret retrieval error. Access token is not provided."
            )
    request = {'jwt': access_token, 'role': vault_role}
    secret_vault_login_uri = Settings.vault_login_uri
    token_request = session.post(secret_vault_login_uri, data=request)
    if not token_request.ok:
        raise ConnectionError(
            "Vault auth error. {}".format(token_request.text)
            )
    vault_token = token_request.json()['auth']['client_token']
    headers = {'X-Vault-Token': vault_token}
    secret_vault_uri = Settings.vault_secret_storage_uri
    secret_request = session.get(
        urllib.parse.urljoin(secret_vault_uri, secret_path), headers=headers
        )
    if not secret_request.ok:
        raise ConnectionError(
            "Vault secret retrieval error. {}".format(secret_request.text)
            )
    return secret_request.json()["data"]
