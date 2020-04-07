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

    # sql_database config
    sql_config = None
    log_table = None

    # OfflineStorage database (alternative to sql_database) config
    offline_storage = implementation_dir / Path('storage')
    offline_log = offline_storage / Path('log')

    # gitCsarDB config
    git_config = None
    workdir = Path("/tmp/xopera/git_db/")

    @staticmethod
    def load_settings():
        Settings.git_config = {
            'type': os.getenv('XOPERA_GIT_TYPE', 'mock'),
            'url': os.getenv("XOPERA_GIT_URL", ""),
            'auth_token': os.getenv("XOPERA_GIT_AUTH_TOKEN", ""),
            'workdir': Settings.workdir

        }

        Settings.sql_config = {
            'host': os.getenv('XOPERA_DATABASE_IP', 'localhost'),
            'port': int(os.getenv("XOPERA_DATABASE_PORT", "5432")),
            'database': os.getenv("XOPERA_DATABASE_NAME", 'xOpera_rest_api'),
            'user': os.getenv("XOPERA_DATABASE_USER", 'postgres'),
            'password': os.getenv("XOPERA_DATABASE_PASSWORD", 'password'),
            'connect_timeout': int(os.getenv("XOPERA_DATABASE_TIMEOUT", '3'))
        }
        Settings.log_table = os.getenv("XOPERA_DATABASE_LOG_TABLE", 'log')

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

        log.debug(json.dumps({
            "sql_config": Settings.sql_config,
            "log_table": Settings.log_table,
            "git_config": {key: (str(value) if isinstance(value, Path) else value) for key, value in Settings.git_config.items()},
            "verbose": Settings.verbose
        }, indent=2))
