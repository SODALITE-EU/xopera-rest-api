import json
import logging as log
import os
import uuid

import psycopg2

from opera.api.openapi.models import Invocation
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

    def save_opera_session_data(self, deployment_id: uuid, tree: dict):
        """
        Saves .opera file tree to database
        """
        pass

    def get_opera_session_data(self, deployment_id: uuid):
        """
        Returns dict with keys [deployment_id, timestamp, tree], where tree is content of .opera dir
        """
        pass

    def delete_opera_session_data(self, deployment_id: uuid):
        """
        Delete session data for deployment
        """
        pass

    def update_deployment_log(self, invocation_id: uuid, inv: Invocation):
        """
        updates deployment log with deployment_id, timestamp, invocation_id, _log
        """
        pass

    def get_deployment_status(self, deployment_id: uuid):
        """
        Get last deployment log
        """
        pass

    def get_deployment_history(self, deployment_id: uuid):
        """
        Get all deployment logs for one deployment
        """
        pass

    def save_git_transaction_data(self, blueprint_id: uuid, version_id: str, revision_msg: str,
                                  job: str, git_backend: str, repo_url: str, commit_sha: str = None):
        """
        Saves transaction data to database
        """
        pass

    def get_git_transaction_data(self, blueprint_id: uuid, version_id: str = None, all: bool = False):
        """
        Gets last git transaction data (if version_id is not None, specific transaction data). If all, it returns all
        git transaction data, that satisfy conditions
        """
        pass

    def get_version_ids(self, blueprint_id: uuid):
        """
        returns list of all version ids for blueprint
        """
        pass

    def get_project_domain(self, blueprint_id: uuid):
        """
        Get project domaing for blueprint
        """
        pass

    def save_project_domain(self, blueprint_id: uuid, project_domain: str):
        """
        returns list of all version tags for blueprint
        """
        pass


class OfflineStorage(Database):
    def __init__(self):
        super().__init__()
        self.db_type = 'OfflineStorage'
        self.db_path = Settings.offline_storage.absolute()
        self.invocation_path = self.db_path / Settings.invocation_table
        self.git_log_path = self.db_path / Settings.git_log_table
        self.opera_session_data_path = self.db_path / Settings.opera_session_data_table
        self.project_domain_path = self.db_path / Settings.project_domain_table

        os.makedirs(self.invocation_path, exist_ok=True)
        os.makedirs(self.git_log_path, exist_ok=True)
        os.makedirs(self.opera_session_data_path, exist_ok=True)
        os.makedirs(self.project_domain_path, exist_ok=True)

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

    def save_opera_session_data(self, deployment_id: uuid, tree: dict):
        data = {
            "tree": tree,
            "deployment_id": str(deployment_id),
            "timestamp": timestamp_util.datetime_now_to_string()
        }
        self.file_write(str(self.opera_session_data_path), name=str(deployment_id), content=json.dumps(data))

    def get_opera_session_data(self, deployment_id: uuid):
        """
        Returns dict with keys [deployment_id, timestamp, tree], where tree is content of .opera dir
        """
        try:
            opera_session_data = json.loads(self.file_read(str(self.opera_session_data_path), str(deployment_id)))
            return {k: (v if v != 'None' else None) for k, v in opera_session_data.items()}
        except FileNotFoundError:
            return None

    def delete_opera_session_data(self, deployment_id: uuid):
        """
        Delete session data for deployment
        """
        file_path = self.opera_session_data_path / str(deployment_id)
        file_path.unlink(missing_ok=True)

    def update_deployment_log(self, invocation_id: uuid, inv: Invocation):
        """
        updates deployment log with deployment_id, timestamp, invocation_id, _log
        """
        location = "{}/{}".format(self.invocation_path, inv.deployment_id)
        os.makedirs(location, exist_ok=True)
        self.file_write(location, name=str(invocation_id), content=str(json.dumps(inv.to_dict(), indent=2)))

    def get_deployment_status(self, deployment_id: uuid):
        """
        Get last deployment log
        """
        history = self.get_deployment_history(deployment_id)
        return history[-1]

    def get_deployment_history(self, deployment_id: uuid):
        """
        Get all deployment logs for one deployment
        """
        location = self.invocation_path / str(deployment_id)
        history = []
        for file in location.glob('*'):
            inv = Invocation.from_dict(json.loads(file.read_text()))
            history.append(inv)
        return sorted(history, key=lambda x: x.timestamp)

    def save_git_transaction_data(self, blueprint_id: uuid, version_id: str,
                                  revision_msg: str, job: str, git_backend: str, repo_url: str, commit_sha: str = None):
        """
        Saves transaction data to database
        """
        try:
            timestamp = timestamp_util.datetime_now_to_string()
            location = self.git_log_path / str(blueprint_id)
            if not location.exists():
                os.makedirs(location)

            git_transaction_data = {
                'blueprint_id': str(blueprint_id),
                'version_id': version_id,
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

    def get_git_transaction_data(self, blueprint_id, version_id=None, all=False):
        """
        Gets last git transaction data (if version_id is not None, specific transaction data). If all, it returns all
        git transaction data, that satisfy conditions
        """
        location = self.git_log_path / str(blueprint_id)
        logfile_paths = sorted([data for data in location.glob("*")], reverse=True)  # first element was last added
        json_logs = [json.load(file.open('r')) for file in logfile_paths]
        if version_id:
            json_logs = [json_log for json_log in json_logs if json_log['version_id'] == version_id]
        if all:
            return json_logs
        try:
            return [json_logs[0]]
        except IndexError:
            return []

    def get_version_ids(self, blueprint_id: uuid):
        """
        returns list of all version ids for blueprint
        """
        log_data = self.get_git_transaction_data(blueprint_id, all=True)
        all_tags = {json_log['version_id'] for json_log in log_data}
        deleted_tags = {json_log['version_id'] for json_log in log_data if json_log['job'] == 'delete'}
        return sorted(list(all_tags - deleted_tags))

    def get_project_domain(self, blueprint_id: uuid):
        """
        returns project domain for blueprint
        """
        try:
            domain_data = json.loads(self.file_read(str(self.project_domain_path), blueprint_id))
            return {k: (v if v != 'None' else None) for k, v in domain_data.items()}
        except FileNotFoundError:
            return None

    def save_project_domain(self, blueprint_id: uuid, project_domain: str):
        """
        Saves project domain for blueprint
        """
        data = {
            "blueprint_id": str(blueprint_id),
            "project_domain": project_domain
        }
        self.file_write(str(self.project_domain_path), name=blueprint_id, content=json.dumps(data))


class PostgreSQL(Database):
    def __init__(self, settings):
        super().__init__()
        self.db_type = "PostgreSQL"
        self.connection = psycopg2.connect(**settings)
        self.execute("""
                        create table if not exists {} (
                        deployment_id varchar (36), 
                        timestamp timestamp, 
                        invocation_id text, 
                        _log text,
                        primary key (invocation_id)
                        );""".format(Settings.invocation_table))

        self.execute("""
                        create table if not exists {} (
                        blueprint_id varchar (36),
                        version_id varchar(36),
                        timestamp timestamp default current_timestamp, 
                        revision_msg text,
                        job varchar(36), 
                        git_backend text,
                        repo_url text,
                        commit_sha text,
                        primary key (timestamp)
                        );""".format(Settings.git_log_table))

        self.execute("""
                        create table if not exists {} (
                        deployment_id varchar (36),
                        timestamp timestamp default current_timestamp, 
                        tree text,
                        primary key (deployment_id)
                        );""".format(Settings.opera_session_data_table))

        self.execute("""
                        create table if not exists {} (
                        blueprint_id varchar (36),
                        project_domain varchar(250),
                        primary key (blueprint_id)
                        );""".format(Settings.project_domain_table))

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

    def save_opera_session_data(self, deployment_id: uuid, tree: dict):
        """
        Saves .opera file tree to database
        """
        tree_str = json.dumps(tree)
        timestamp = timestamp_util.datetime_now_to_string()
        response = self.execute(
            "insert into {} (deployment_id, timestamp, tree) values (%s, %s, %s)"
                .format(Settings.opera_session_data_table), (str(deployment_id), timestamp, tree_str))
        if response:
            log.info('Updated dot_opera_data in PostgreSQL database')
        else:
            log.error('Failed to update dot_opera_data in PostgreSQL database')
        return response

    def get_opera_session_data(self, deployment_id):
        """
        Returns dict with keys [deployment_id, timestamp, tree], where tree is content of .opera dir
        """
        dbcur = self.connection.cursor()
        query = "select deployment_id, timestamp, tree" \
                " from {} where deployment_id = '{}';" \
            .format(Settings.opera_session_data_table, str(deployment_id))
        dbcur.execute(query)
        line = dbcur.fetchone()
        if not line:
            return None
        session_data = {
            'deployment_id': line[0],
            'timestamp': timestamp_util.datetime_to_str(line[1]),
            'tree': json.loads(line[2])
        }
        dbcur.close()
        return session_data

    def delete_opera_session_data(self, deployment_id: uuid):
        """
        Delete session data for deployment
        """
        response = self.execute(
            "delete from {} where deployment_id = '{}'"
                .format(Settings.opera_session_data_table, str(deployment_id)))
        if response:
            log.info(f'Deleted opera_session_data for {deployment_id} from PostgreSQL database')
        else:
            log.error(f'Failed to delete opera_session_data for {deployment_id} from PostgreSQL database')
        return response

    def update_deployment_log(self, invocation_id: uuid, inv: Invocation):
        """
        updates deployment log with deployment_id, timestamp, invocation_id, _log
        """
        # deployment_id,  timestamp, invocation_id, _log
        response = self.execute(
            "insert into {} (deployment_id, timestamp, invocation_id, _log) values (%s, %s, %s, %s)"
                .format(Settings.invocation_table),
            (str(inv.deployment_id), str(inv.timestamp), str(invocation_id), json.dumps(inv.to_dict())))
        if response:
            log.info('Updated deployment log in PostgreSQL database')
        else:
            log.error('Failed to update deployment log in PostgreSQL database')
        return response

    def get_deployment_status(self, deployment_id: uuid):
        """
        Get last deployment log
        """

        dbcur = self.connection.cursor()

        query = "select timestamp, _log from {} where deployment_id = '{}' order by timestamp desc limit 1;" \
            .format(Settings.invocation_table, deployment_id)

        dbcur.execute(query)
        line = dbcur.fetchone()
        if not line:
            return None
        inv = Invocation.from_dict(json.loads(line[1]))
        dbcur.close()

        return inv

    def get_deployment_history(self, deployment_id: uuid):
        """
        Get all deployment logs for one deployment
        """
        dbcur = self.connection.cursor()

        query = "select timestamp, _log from {} where deployment_id = '{}' order by timestamp;" \
            .format(Settings.invocation_table, deployment_id)

        dbcur.execute(query)
        lines = dbcur.fetchall()
        history = [Invocation.from_dict(json.loads(line[1])) for line in lines]
        dbcur.close()

        return history

    def save_git_transaction_data(self, blueprint_id: uuid, version_id: str, revision_msg: str, job: str,
                                  git_backend: str, repo_url: str, commit_sha: str = None):
        """
        Saves transaction data to database
        """
        response = self.execute(
            """insert into {} (blueprint_id, version_id, revision_msg, job, git_backend, repo_url, commit_sha) 
            values (%s, %s, %s, %s, %s, %s, %s)""".format(Settings.git_log_table),
            (str(blueprint_id), version_id, revision_msg, job, git_backend, repo_url, commit_sha))
        if response:
            log.info('Updated git log in PostgreSQL database')
        else:
            log.error('Fail to update git log in PostgreSQL database')
        return response

    def get_git_transaction_data(self, blueprint_id: uuid, version_id: str = None, all: bool = False):
        """
        Gets all transaction data for some blueprint
        """
        inputs = tuple(xi for xi in (str(blueprint_id), version_id) if xi is not None)
        dbcur = self.connection.cursor()
        query = """select blueprint_id, version_id, revision_msg, job, git_backend, repo_url, commit_sha, timestamp
         from {} where blueprint_id = %s {} order by timestamp desc {};""".format(
            Settings.git_log_table, "and version_id = %s" if version_id else "", "limit 1" if not all else "")

        dbcur.execute(query, inputs)
        lines = dbcur.fetchall()
        git_transaction_data_list = [
            {
                'blueprint_id': line[0],
                'version_id': line[1],
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

    def get_version_ids(self, blueprint_id: uuid):
        """
        returns list of all version ids for blueprint
        """
        log_data = self.get_git_transaction_data(blueprint_id, all=True)
        all_tags = {json_log['version_id'] for json_log in log_data}
        deleted_tags = {json_log['version_id'] for json_log in log_data if json_log['job'] == 'delete'}
        return sorted(list(all_tags - deleted_tags))

    def get_project_domain(self, blueprint_id: uuid):
        """
        returns project domain for blueprint
        """
        dbcur = self.connection.cursor()
        query = """select blueprint_id, project_domain from {} where blueprint_id = '{}';""".format(
            Settings.project_domain_table, blueprint_id)
        dbcur.execute(query)
        line = dbcur.fetchone()
        if not line:
            return None
        project_domain = line[1]
        dbcur.close()
        return project_domain

    def save_project_domain(self, blueprint_id: uuid, project_domain: str):
        """
        Saves project domain for blueprint
        """
        response = self.execute(
            "insert into {} (blueprint_id, project_domain) values (%s, %s)"
            .format(Settings.project_domain_table), (str(blueprint_id), project_domain))
        if response:
            log.info('Updated {} in PostgreSQL database'.format(Settings.project_domain_table))
        else:
            log.error('Failed to update {} in PostgreSQL database'.format(Settings.project_domain_table))
        return response
