import glob
import json
import logging as log
import os
import shutil
import uuid

import psycopg2

from opera.api.settings import Settings
from opera.api.util import timestamp_util


def connect(sql_config):
    if Settings.USE_OFFLINE_STORAGE:
        return OfflineStorage()
    try:
        database = PostgreSQL(sql_config)
        log.info('SQL_database: PostgreSQL')
    except psycopg2.Error as e:
        log.error(f"Error while connecting to PostgreSQL: {str(e)}")
        database = OfflineStorage()
        log.info("SQL_database: OfflineStorage")

    return database


class Database:

    def __init__(self):
        self.db_type = "unknown type of database"
        pass

    def disconnect(self):
        """
        closes database connection
        """
        pass

    def save_session_data(self, session_token: str, blueprint_token: str, version_tag: str, tree: dict):
        """
        Saves .opera file tree to database
        """
        pass

    def get_session_data(self, session_token):
        """
        Returns [blueprint_token, version_tag, tree], where tree is content of .opera dir
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

    def save_git_transaction_data(self, blueprint_token: uuid, version_tag: str, revision_msg: str, job: str,
                                  git_backend: str, repo_url: str, commit_sha: str = None):
        """
        Saves transaction data to database
        """
        pass

    def get_git_transaction_data(self, blueprint_token: uuid, version_tag: str = None, all: bool = False):
        """
        Gets last git transaction data (if version_tag is not None, specific transaction data). If all, it returns all
        git transaction data, that satisfy conditions
        """
        pass

    def get_version_tags(self, blueprint_token: uuid):
        """
        returns list of all version tags for blueprint
        """
        pass


class OfflineStorage(Database):
    def __init__(self):
        super().__init__()
        self.db_type = 'OfflineStorage'
        self.db_path = Settings.offline_storage.absolute()
        self.deployment_log_path = self.db_path / Settings.deployment_log_table
        self.git_log_path = self.db_path / Settings.git_log_table
        self.dot_opera_data_path = self.db_path / Settings.dot_opera_data_table

        os.makedirs(self.deployment_log_path, exist_ok=True)
        os.makedirs(self.git_log_path, exist_ok=True)
        os.makedirs(self.dot_opera_data_path, exist_ok=True)

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

    def save_session_data(self, session_token: str, blueprint_token: str, version_tag: str, tree: dict):
        data = {
            "tree": tree,
            "blueprint_token": str(blueprint_token),
            "version_tag": str(version_tag),
            "session_token": str(session_token),
            "timestamp": timestamp_util.datetime_now_to_string()
        }
        self.file_write(str(self.dot_opera_data_path), name=session_token, content=json.dumps(data))

    def get_session_data(self, session_token):
        data = json.loads(self.file_read(str(self.dot_opera_data_path), session_token))
        return data

    def get_last_session_data(self, blueprint_token):
        my_list = []
        for session_file in self.dot_opera_data_path.glob('*'):
            if session_file.is_file():
                session_data = json.loads(session_file.read_text())
                if session_data['blueprint_token'] == blueprint_token:
                    my_list.append((session_data['timestamp'], session_file.name))
        try:
            last_session_token = sorted(my_list, key=lambda x: x[0], reverse=True)[0][1]
            return self.get_session_data(last_session_token)
        except IndexError:
            return None

    def update_deployment_log(self, blueprint_token: str, _log: str, session_token: str, timestamp: str):
        """
        updates deployment log with blueprint_token, timestamp, session_token, _log
        """
        location = "{}/{}".format(self.deployment_log_path, session_token)
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
            path = "{}/{}".format(self.deployment_log_path, session_token)
            try:
                if not self.file_read(path, 'blueprint_token') == str(blueprint_token):
                    # combination of blueprint_token and session_token does not exist
                    return []
            except FileNotFoundError:
                # session_token does not exist
                return []
            return [[timestamp_util.str_to_datetime(self.file_read(path, "timestamp")), self.file_read(path, "_log")]]

        elif blueprint_token is not None:
            pattern = "{}/*/blueprint_token".format(self.deployment_log_path)
            token_file_paths = ["/".join(path.split('/')[:-1]) for path in glob.glob(pattern) if
                                self.file_read(path) == str(blueprint_token)]
            return [[timestamp_util.str_to_datetime(self.file_read(path, "timestamp")), self.file_read(path, "_log")]
                    for path
                    in token_file_paths]

        elif session_token is not None:
            path = "{}/{}".format(self.deployment_log_path, session_token)
            try:
                return [
                    [timestamp_util.str_to_datetime(self.file_read(path, "timestamp")), self.file_read(path, "_log")]]
            except FileNotFoundError:
                # session_token does not exist
                return []
        else:
            return []

    def save_git_transaction_data(self, blueprint_token: uuid, version_tag: str,
                                  revision_msg: str, job: str, git_backend: str, repo_url: str, commit_sha: str = None):
        """
        Saves transaction data to database
        """
        try:
            timestamp = timestamp_util.datetime_now_to_string()
            location = self.git_log_path / str(blueprint_token)
            if not location.exists():
                os.makedirs(location)

            git_transaction_data = {
                'blueprint_token': str(blueprint_token),
                'version_tag': version_tag,
                'revision_msg': revision_msg,
                'job': job,
                'git_backend': git_backend,
                'repo_url': repo_url,
                'commit_sha': commit_sha,
                'timestamp': timestamp
            }
            (location / str(timestamp)).write_text(json.dumps(git_transaction_data, indent=2))
        except Exception as e:

            log.error(f'Failed to update git log in OfflineStorage database: {str(e)}')
            return False
        log.info('Updated git log in OfflineStorage database')
        return True

    def get_git_transaction_data(self, blueprint_token, version_tag=None, all=False):
        """
        Gets last git transaction data (if version_tag is not None, specific transaction data)
        """
        location = self.git_log_path / str(blueprint_token)
        logfile_paths = sorted([data for data in location.glob("*")], reverse=True)  # first element was last added
        json_logs = [json.load(file.open('r')) for file in logfile_paths]
        if version_tag:
            json_logs = [json_log for json_log in json_logs if json_log['version_tag'] == version_tag]
        if all:
            return json_logs
        try:
            return [json_logs[0]]
        except IndexError:
            return []

    def get_version_tags(self, blueprint_token: uuid):
        """
        returns list of all version tags for blueprint
        """
        log_data = self.get_git_transaction_data(blueprint_token, all=True)
        all_tags = {json_log['version_tag'] for json_log in log_data}
        deleted_tags = {json_log['version_tag'] for json_log in log_data if json_log['job'] == 'delete'}
        return sorted(list(all_tags - deleted_tags))


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
                        );""".format(Settings.deployment_log_table))

        self.execute("""
                        create table if not exists {} (
                        blueprint_token varchar (36),
                        version_tag varchar(36),
                        timestamp timestamp default current_timestamp, 
                        revision_msg text,
                        job varchar(36), 
                        git_backend text,
                        repo_url text,
                        commit_sha text,
                        primary key (timestamp)
                        );""".format(Settings.git_log_table))

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
        except psycopg2.Error as e:
            log.debug(str(e))
            dbcur.execute("ROLLBACK")
            return False
        dbcur.close()
        self.connection.commit()
        return True

    def save_session_data(self, session_token: str, blueprint_token: str, version_tag: str, tree: dict):
        """
        Saves .opera file tree to database
        """
        pass

    def get_session_data(self, session_token):
        """
        Returns [blueprint_token, version_tag, tree], where tree is content of .opera dir
        """
        pass

    def update_deployment_log(self, blueprint_token: str, _log: str, session_token: str, timestamp: str):

        response = self.execute(
            "insert into {} (blueprint_token, timestamp, session_token, _log) values (%s, %s, %s, %s)"
                .format(Settings.deployment_log_table),
            (str(blueprint_token), str(timestamp), str(session_token), str(_log)))
        if response:
            log.info('Updated deployment log in PostgreSQL database')
        else:
            log.error('Failed to update deployment log in PostgreSQL database')
        return response

    def get_deployment_log(self, blueprint_token: str = None, session_token: str = None):
        """

        :param blueprint_token: token of blueprint
        :param session_token: token of session, that produced log
        :return: list of lists [[timestamp, log],...]
        """

        dbcur = self.connection.cursor()

        if blueprint_token is not None and session_token is not None:
            query = "select timestamp, _log from {} where blueprint_token = '{}' and session_token = '{}' order by " \
                    "timestamp desc;".format(Settings.deployment_log_table, blueprint_token, session_token)

        elif blueprint_token is not None:
            query = "select timestamp, _log from {} where blueprint_token = '{}' order by timestamp desc;".format(
                Settings.deployment_log_table,
                str(blueprint_token))
        elif session_token is not None:
            query = "select timestamp, _log from {} where session_token = '{}';".format(Settings.deployment_log_table,
                                                                                        str(session_token))
        else:
            return []

        dbcur.execute(query)
        lines = dbcur.fetchall()
        dbcur.close()

        return lines

    def save_git_transaction_data(self, blueprint_token: uuid, version_tag: str, revision_msg: str, job: str,
                                  git_backend: str, repo_url: str, commit_sha: str = None):
        """
        Saves transaction data to database
        """
        response = self.execute(
            """insert into {} (blueprint_token, version_tag, revision_msg, job, git_backend, repo_url, commit_sha) 
            values (%s, %s, %s, %s, %s, %s, %s)""".format(Settings.git_log_table),
            (str(blueprint_token), version_tag, revision_msg, job, git_backend, repo_url, commit_sha))
        if response:
            log.info('Updated git log in PostgreSQL database')
        else:
            log.error('Fail to update git log in PostgreSQL database')
        return response

    def get_git_transaction_data(self, blueprint_token: uuid, version_tag: str = None, all: bool = False):
        """
        Gets all transaction data for some blueprint
        """
        inputs = tuple(xi for xi in (str(blueprint_token), version_tag) if xi is not None)
        dbcur = self.connection.cursor()
        query = """select blueprint_token, version_tag, revision_msg, job, git_backend, repo_url, commit_sha, timestamp
         from {} where blueprint_token = %s {} order by timestamp desc {};""".format(
            Settings.git_log_table, "and version_tag = %s" if version_tag else "", "limit 1" if not all else "")

        dbcur.execute(query, inputs)
        lines = dbcur.fetchall()
        git_transaction_data_list = [
            {
                'blueprint_token': line[0],
                'version_tag': line[1],
                'revision_msg': line[2],
                'job': line[3],
                'git_backend': line[4],
                'repo_url': line[5],
                'commit_sha': line[6],
                'timestamp': timestamp_util.datetime_to_str(line[7])
            } for line in lines
        ]
        dbcur.close()

        return git_transaction_data_list

    def get_version_tags(self, blueprint_token: uuid):
        """
        returns list of all version tags for blueprint
        """
        log_data = self.get_git_transaction_data(blueprint_token, all=True)
        all_tags = {json_log['version_tag'] for json_log in log_data}
        deleted_tags = {json_log['version_tag'] for json_log in log_data if json_log['job'] == 'delete'}
        return sorted(list(all_tags - deleted_tags))
