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
    STDFILE_DIR = f"{API_WORKDIR}/in_progress"
    INVOCATION_DIR = f"{API_WORKDIR}/invocations"
    DEPLOYMENT_DIR = f"{API_WORKDIR}/deployment_dir"

    # sql_database config
    sql_config = None
    deployment_log_table = 'deployment_log'
    git_log_table = 'git_log'
    dot_opera_data_table = 'session_data'

    # OfflineStorage database (alternative to sql_database) config
    USE_OFFLINE_STORAGE = False
    offline_storage = Path(API_WORKDIR) / 'storage'

    # gitCsarDB config
    git_config = None
    workdir = Path(API_WORKDIR) / "git_db/mockConnector"

    @staticmethod
    def load_settings():
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
        Settings.deployment_log_table = os.getenv("XOPERA_DATABASE_DEPLOYMENT_LOG_TABLE", 'deployment_log')
        Settings.git_log_table = os.getenv("XOPERA_DATABASE_GIR_LOG_TABLE", 'git_log')
        Settings.dot_opera_data_table = os.getenv("XOPERA_DATABASE_DOT_OPERA_DATA_TABLE", 'dot_opera_data')

        # prepare git_config for printing
        __debug_git_config = copy.deepcopy(Settings.git_config)
        __debug_git_config['auth_token'] = '****' if __debug_git_config['auth_token'] != "" else None
        __debug_git_config['url'] = None if __debug_git_config['url'] == "" else __debug_git_config['url']
        __debug_git_config['mock_workdir'] = str(__debug_git_config['mock_workdir'])

        logger.debug(json.dumps({
            "sql_config": Settings.sql_config,
            "deployment_log_table": Settings.deployment_log_table,
            "git_log_table": Settings.git_log_table,
            "git_config": __debug_git_config
        }, indent=2))
