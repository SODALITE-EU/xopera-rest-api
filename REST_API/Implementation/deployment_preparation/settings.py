import datetime
import json
import logging as log
import os
from pathlib import Path


class Settings:
    implementation_dir = Path(__file__).absolute().parent.parent
    deployment_data = f"{implementation_dir}/model_deployment_data/"
    offline_storage = f"{implementation_dir}/storage/"
    offline_blueprints = "{}blueprints/".format(offline_storage)
    offline_log = "{}log/".format(offline_storage)
    ssh_keys_location = "/root/.ssh/"

    key_pair = ""
    logfile_name = "logs.log"

    verbose = False

    connection = {
        "host": "172.17.0.3",
        "port": 5432,
        "database": "deployment_preparation",
        "user": "postgres",
        "password": "password",
        "connect_timeout": 3
    }

    blueprints_table = "versions"
    log_table = "log"

    @staticmethod
    def datetime_now_to_string():
        return Settings.datetime_to_str(datetime.datetime.now())

    @staticmethod
    def datetime_to_str(timestamp: datetime.datetime):
        return timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')

    @staticmethod
    def str_to_datetime(time_str: str):
        return datetime.datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S.%f')

    @staticmethod
    def load_settings():

        try:
            f = Path(Settings.implementation_dir / "settings" / "default_settings.json").open()
            settings = json.load(f)

            Settings.verbose = settings["run_params"]["verbose"]
            if Settings.verbose:
                log.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
            else:
                log.basicConfig(format="%(levelname)s: %(message)s")

            Settings.connection = settings["postgresql"]["connection"]
            Settings.blueprints_table = settings["postgresql"]["history_table"]
            Settings.log_table = settings["postgresql"]["log_table"]

            f.close()

        except (FileNotFoundError, KeyError):
            log.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
            log.error("Settings failed loading!")

        if "DATABASE_IP" in os.environ:
            print('DATABASE IP from env: ' + str(os.environ["DATABASE_IP"]))
            Settings.connection["host"] = os.environ["DATABASE_IP"]
