import copy
import json
import os
from pathlib import Path

from opera.api.log import get_logger

logger = get_logger(__name__)


class Settings:
    implementation_dir = Path(__file__).absolute().parent.parent

    # ssh config
    ssh_keys_location = Path("/root/.ssh/")
    key_pair = ""

    # deployment config
    API_WORKDIR = ".opera-api"
    STDFILE_DIR = None
    INVOCATION_DIR = None
    DEPLOYMENT_DIR = None

    # maximum number of invocations at the same time
    invocation_service_workers = 10

    # PostgreSQL config
    sql_config = None
    invocation_table = 'invocation'
    blueprint_table = 'blueprint'
    git_log_table = 'git_log'
    opera_session_data_table = 'opera_session_data'

    # gitCsarDB config
    git_config = None
    workdir = None

    # Authorization and Authentication config
    oidc_introspection_endpoint_uri = None
    oidc_client_id = None
    oidc_client_secret = None
    vault_secret_storage_uri = None
    vault_login_uri = None
    apiKey = None
    connection_protocols = ["http://", "https://"]
    vault_secret_prefix = "_get_secret"
    secure_workdir = True
    ssh_key_path_template = "ssh/{username}"
    ssh_key_secret_name = "ssh_pkey"

    @staticmethod
    def load_settings():
        Settings.API_WORKDIR = os.getenv("XOPERA_API_WORKDIR", Settings.API_WORKDIR)
        Settings.STDFILE_DIR = f"{Settings.API_WORKDIR}/in_progress"
        Settings.INVOCATION_DIR = f"{Settings.API_WORKDIR}/invocations"
        Settings.DEPLOYMENT_DIR = f"{Settings.API_WORKDIR}/deployment_dir"
        Settings.workdir = Path(Settings.API_WORKDIR) / "git_db/mockConnector"
        Settings.secure_workdir = os.getenv("XOPERA_SECURE_WORKDIR", "True").lower() == "true"

        Settings.git_config = {
            'type': os.getenv('XOPERA_GIT_TYPE', 'mock'),
            'url': os.getenv("XOPERA_GIT_URL", ""),
            'auth_token': os.getenv("XOPERA_GIT_AUTH_TOKEN", ""),
            'mock_workdir': Settings.workdir,

            # optional params
            'workdir': os.getenv("XOPERA_GIT_WORKDIR", f"{Settings.API_WORKDIR}/git_db/mock_db"),
            'repo_prefix': os.getenv("XOPERA_GIT_REPO_PREFIX", "gitDB_"),
            'commit_name': os.getenv("XOPERA_GIT_COMMIT_NAME", "SODALITE-xOpera-REST-API"),
            'commit_mail': os.getenv("XOPERA_GIT_COMMIT_MAIL", "no-email@domain.com"),
            'guest_permissions': os.getenv("XOPERA_GIT_GUEST_PERMISSIONS", "reporter")
        }

        Settings.sql_config = {
            'host': os.getenv('XOPERA_DATABASE_IP', 'localhost'),
            'port': int(os.getenv("XOPERA_DATABASE_PORT", "5432")),
            'database': os.getenv("XOPERA_DATABASE_NAME", 'xOpera_rest_api'),
            'user': os.getenv("XOPERA_DATABASE_USER", 'postgres'),
            'password': os.getenv("XOPERA_DATABASE_PASSWORD", 'password'),
            'connect_timeout': int(os.getenv("XOPERA_DATABASE_TIMEOUT", '3'))
        }

        Settings.oidc_introspection_endpoint_uri = os.getenv("OIDC_INTROSPECTION_ENDPOINT", "")
        Settings.oidc_client_id = os.getenv("OIDC_CLIENT_ID", "sodalite-ide")
        Settings.oidc_client_secret = os.getenv("OIDC_CLIENT_SECRET", "")
        Settings.apiKey = os.getenv("AUTH_API_KEY", "")

        Settings.invocation_service_workers = int(os.getenv("INVOCATION_SERVICE_WORKERS", '10'))

        Settings.vault_secret_storage_uri = os.getenv("VAULT_SECRET_URI", "http://localhost:8200/v1/")
        Settings.vault_login_uri = os.getenv("VAULT_LOGIN_URI", "http://localhost:8200/v1/auth/jwt/login")

        # prepare git_config for printing
        __debug_git_config = copy.deepcopy(Settings.git_config)
        __debug_git_config['auth_token'] = '****' if __debug_git_config['auth_token'] != "" else None
        __debug_git_config['url'] = None if __debug_git_config['url'] == "" else __debug_git_config['url']
        __debug_git_config['mock_workdir'] = str(__debug_git_config['mock_workdir'])

        logger.debug(json.dumps({
            "oicd_config": {
                "introspection_endpoint": Settings.oidc_introspection_endpoint_uri,
                "client_id": Settings.oidc_client_id,
                "client_secret": Settings.oidc_client_secret,
            },
            "vault_config": {
                "secret_storage_uri": Settings.vault_secret_storage_uri,
                "login_uri": Settings.vault_login_uri,
                "secret_prefix": Settings.vault_secret_prefix
            },
            "auth_api_key": Settings.apiKey,
            "invocation_service_workers": Settings.invocation_service_workers,
            "sql_config": Settings.sql_config,
            "git_config": __debug_git_config
        }, indent=2))
