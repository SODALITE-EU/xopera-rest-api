import glob
import logging as log
import os
import shutil

import psycopg2

from settings import Settings
from util import timestamp_util


class Database:

    def __init__(self):
        self.db_type = "unknown type of database"
        pass

    def disconnect(self):
        """
        closes database connection
        """
        pass

    def update_deployment_log(self, blueprint_token: str, _log: str, session_token: str, timestamp: str):
        """
        updates deployment log with blueprint_token, timestamp, session_token, _log
        """
        pass

    def get_deployment_log(self, blueprint_token: str = None, session_token: str = None):
        """
        Returns deployment log.
        It can query by blueprint_token, session_token or combination of both
        In case of no results returns [0, "not enough parameters"]
        """
        pass


class OfflineStorage(Database):
    def __init__(self):
        super().__init__()
        self.db_type = 'OfflineStorage'

        if not Settings.offline_storage.exists():
            Settings.offline_storage.mkdir()
        if not Settings.offline_log.exists():
            Settings.offline_log.exists()

    @staticmethod
    def file_write(path, content, name=None):
        if name is not None:
            path = path + "/" + name
        open_file = open(path, "w")
        open_file.write(content)
        open_file.close()

    @staticmethod
    def file_read(path, name=None):
        if name is not None:
            path = path + "/" + name
        open_file = open(path, "r")
        text = open_file.read()
        open_file.close()
        return text.strip()

    def disconnect(self):
        # does not need to do anything
        pass

    def update_deployment_log(self, blueprint_token: str, _log: str, session_token: str, timestamp: str):
        """
        updates deployment log with blueprint_token, timestamp, session_token, _log
        """
        location = "{}/{}".format(Settings.offline_log, session_token)
        if os.path.exists(location):
            shutil.rmtree(location)
        os.makedirs(location)
        self.file_write(location, name="blueprint_token", content=str(blueprint_token))
        self.file_write(location, name="timestamp", content=str(timestamp))
        self.file_write(location, name="session_token", content=str(session_token))
        self.file_write(location, name="_log", content=str(_log))

    def get_deployment_log(self, blueprint_token: str = None, session_token: str = None):
        """
        Returns deployment log.
        It can query by blueprint_token, session_token or combination of both
        In case of no results returns [0, "not enough parameters"]
        """
        if blueprint_token is not None and session_token is not None:
            path = "{}/{}".format(Settings.offline_log, session_token)
            try:
                if not self.file_read(path, 'blueprint_token') == str(blueprint_token):
                    # combination of blueprint_token and session_token does not exist
                    return []
            except FileNotFoundError:
                # session_token does not exist
                return []
            return [[timestamp_util.str_to_datetime(self.file_read(path, "timestamp")), self.file_read(path, "_log")]]

        elif blueprint_token is not None:
            pattern = "{}/*/blueprint_token".format(Settings.offline_log)
            token_file_paths = ["/".join(path.split('/')[:-1]) for path in glob.glob(pattern) if
                                self.file_read(path) == str(blueprint_token)]
            return [[timestamp_util.str_to_datetime(self.file_read(path, "timestamp")), self.file_read(path, "_log")]
                    for path
                    in token_file_paths]

        elif session_token is not None:
            path = "{}/{}".format(Settings.offline_log, session_token)
            try:
                return [
                    [timestamp_util.str_to_datetime(self.file_read(path, "timestamp")), self.file_read(path, "_log")]]
            except FileNotFoundError:
                # session_token does not exist
                return []
        else:
            return []


class PostgreSQL(Database):
    def __init__(self, settings):
        super().__init__()
        self.db_type = "PostgreSQL"
        self.connection = psycopg2.connect(**settings)
        self.execute("""
                        create table if not exists {} (
                        blueprint_token varchar (36), 
                        timestamp timestamp, 
                        session_token text, 
                        _log text,
                        primary key (session_token)
                        );""".format(Settings.log_table))

    def disconnect(self):
        log.info('disconnecting PostgreSQL database')
        self.connection.close()

    def execute(self, command, replacements=None):
        dbcur = self.connection.cursor()
        try:
            if replacements is not None:
                dbcur.execute(command, replacements)
            else:
                dbcur.execute(command)
        except psycopg2.Error:
            dbcur.execute("ROLLBACK")
        dbcur.close()
        self.connection.commit()
        return dbcur

    def update_deployment_log(self, blueprint_token: str, _log: str, session_token: str, timestamp: str):

        self.execute(
            "insert into {} (blueprint_token, timestamp, session_token, _log) values (%s, %s, %s, %s, %s)"
            .format(Settings.log_table), (str(blueprint_token), str(timestamp), str(session_token), str(_log)))

        log.info('Updated deployment log in PostgreSQL database')

    def get_deployment_log(self, blueprint_token: str = None, session_token: str = None):
        """

        :param blueprint_token: token of blueprint
        :param session_token: token of session, that produced log
        :return: list of lists [[timestamp, log],...]
        """

        dbcur = self.connection.cursor()

        if blueprint_token is not None and session_token is not None:
            query = "select timestamp, _log from {} where blueprint_token = '{}' and session_token = '{}' order by " \
                    "timestamp desc;".format(Settings.log_table, blueprint_token, session_token)

        elif blueprint_token is not None:
            query = "select timestamp, _log from {} where blueprint_token = '{}' order by timestamp desc;".format(
                Settings.log_table,
                str(blueprint_token))
        elif session_token is not None:
            query = "select timestamp, _log from {} where session_token = '{}';".format(Settings.log_table,
                                                                                        str(session_token))
        else:
            return []

        dbcur.execute(query)
        lines = dbcur.fetchall()
        dbcur.close()

        return lines
