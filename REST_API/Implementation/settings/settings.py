import copy
import json
import logging as log
import os
from pathlib import Path


class Settings:
    implementation_dir = Path(__file__).absolute().parent.parent

    # ssh config
    ssh_keys_location = Path("/root/.ssh/")
    key_pair = ""

    # deployment config
    deployment_data = implementation_dir / Path('deployment_data')
    interpreter = None
    logfile_name = "logs.log"

    verbose = ""
    testing = False

    # sql_database config
    sql_config = None
    deployment_log_table = None
    git_log_table = None

    # OfflineStorage database (alternative to sql_database) config
    offline_storage = implementation_dir / Path('storage')
    offline_deployment_log = offline_storage / Path('deployment_log')
    offline_git_log = offline_storage / Path('git_log')

    # gitCsarDB config
    git_config = None
    workdir = Path("/tmp/xopera/git_db/mockConnector")

    @staticmethod
    def load_settings():
        Settings.testing = os.getenv('XOPERA_TESTING', False)
        Settings.git_config = {
            'type': os.getenv('XOPERA_GIT_TYPE', 'mock'),
            'url': os.getenv("XOPERA_GIT_URL", ""),
            'auth_token': os.getenv("XOPERA_GIT_AUTH_TOKEN", ""),
            'mock_workdir': Settings.workdir,

            # optional params
            'workdir': os.getenv("XOPERA_GIT_WORKDIR", "/tmp/git_db"),
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

        Settings.verbose = os.getenv('XOPERA_VERBOSE_MODE', 'warning').casefold()

        _nameToLevel = {
            'critical': log.CRITICAL,
            'fatal': log.FATAL,
            'error': log.ERROR,
            'warn': log.WARNING,
            'warning': log.WARNING,
            'info': log.INFO,
            'debug': log.DEBUG,
            'notset': log.NOTSET,
        }

        log.basicConfig(format="%(levelname)s: %(message)s", level=_nameToLevel.get(Settings.verbose, log.WARNING))

        # prepare git_config for printing
        __debug_git_config = copy.deepcopy(Settings.git_config)
        __debug_git_config['auth_token'] = '****' if __debug_git_config['auth_token'] != "" else None
        __debug_git_config['url'] = None if __debug_git_config['url'] is "" else __debug_git_config['url']
        __debug_git_config['mock_workdir'] = str(__debug_git_config['mock_workdir'])

        log.debug(json.dumps({
            "sql_config": Settings.sql_config,
            "deployment_log_table": Settings.deployment_log_table,
            "git_log_table": Settings.git_log_table,
            "git_config": __debug_git_config,
            "verbose": Settings.verbose
        }, indent=2))
