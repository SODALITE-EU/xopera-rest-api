import json
import os
import uuid

import psycopg2

from opera.api.openapi.models import Invocation
from opera.api.settings import Settings
from opera.api.util import timestamp_util, file_util
from opera.api.log import get_logger

logger = get_logger(__name__)


def connect(sql_config):
    if Settings.USE_OFFLINE_STORAGE:
        return OfflineStorage()
    try:
        database = PostgreSQL(sql_config)
        logger.info('SQL_database: PostgreSQL')
    except psycopg2.Error as e:
        logger.error(f"Error while connecting to PostgreSQL: {str(e)}")
        database = OfflineStorage()
        logger.info("SQL_database: OfflineStorage")

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

    def version_exists(self, blueprint_id: uuid, version_id=None) -> bool:
        """
        Checks if, according to records in git_log table blueprint (version) exists
        """
        pass

    def get_deployment_ids(self, blueprint_id: uuid, version_id: str = None):
        """
        Returns list of deployment_ids od all deployments created from blueprint with blueprint_id
        """
        pass

    def blueprint_used_in_deployment(self, blueprint_id: uuid, version_id: str = None):
        """
        Checks if blueprint is part of any deployment. If version is specified, it checks if it is used in current
        deployment state
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

    def get_last_invocation_id(self, deployment_id: uuid):
        """
        This method exists since we do not want to have invocation_id in Invocation object, to not confuse users
        """
        pass

    def save_git_transaction_data(self, blueprint_id: uuid, revision_msg: str, job: str, git_backend: str,
                                  repo_url: str, version_id: str = None, commit_sha: str = None):
        """
        Saves transaction data to database
        """
        pass

    def get_git_transaction_data(self, blueprint_id: uuid, version_id: str = None, fetch_all: bool = False):
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
        Get project domain for blueprint
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

    def version_exists(self, blueprint_id: uuid, version_id=None) -> bool:
        """
        Checks if, according to records in git_log table blueprint (version) exists
        """
        blueprint_path = self.git_log_path / str(blueprint_id)
        # first log is the most recent
        logs = sorted([json.load(logfile.open('r')) for logfile in blueprint_path.glob('*')], key=lambda x: x['timestamp'], reverse=True)

        # check blueprint has not been deleted
        if not logs:
            # blueprint has never existed
            logger.debug(f"Blueprint {blueprint_id} has never existed")
            return False
        last_version_id, last_job = logs[0]['version_id'], logs[0]['job']
        if last_version_id is None and last_job == "delete":
            # entire blueprint has been deleted
            logger.debug(f"Entire blueprint {blueprint_id} has been deleted, does not exist any more")
            return False

        if version_id:
            logs_version = [log for log in logs if log['version_id'] == version_id]
            # check version has not been deleted
            if not logs_version:
                # blueprint version has never existed
                logger.debug(f"Blueprint-version {blueprint_id}/{version_id} has never existed")
                return False

            last_job = logs_version[0]['job']
            if last_job == "delete":
                # blueprint version has been deleted
                logger.debug(f"Blueprint-version {blueprint_id}/{version_id} has been deleted, does not exist any more")
                return False

        # all checks have passed, blueprint (version) exists
        return True

    def get_deployment_ids(self, blueprint_id: uuid, version_id: str = None):
        """
        Returns list of deployment_ids od all deployments created from blueprint with blueprint_id
        """
        deployment_ids = []
        location = self.invocation_path
        file_paths = [path for path in location.rglob('*') if path.is_file()]
        for file in file_paths:
            inv = Invocation.from_dict(json.loads(file.read_text()))
            if str(inv.blueprint_id) == str(blueprint_id):
                deployment_ids.append(uuid.UUID(inv.deployment_id))

        return list(set(deployment_ids))

    def blueprint_used_in_deployment(self, blueprint_id: uuid, version_id: str = None):
        """
        Checks if blueprint is part of any deployment. If version is specified, it checks if it is used in current
        deployment state
        """
        deployment_ids = self.get_deployment_ids(blueprint_id, version_id)
        if not deployment_ids:
            return False

        if version_id:
            for deployment_id in deployment_ids:
                location = self.invocation_path / str(deployment_id)
                invs = []
                for file in location.glob('*'):
                    inv = Invocation.from_dict(json.loads(file.read_text()))
                    invs.append(inv)
                invs.sort(key=lambda x: x.timestamp)
                if invs[-1].version_id == version_id:
                    return True
            return False

        return True

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
        # TODO change back to unlink(missing_ok=True) when jenkins upgrades to python3.8
        # file_path.unlink(missing_ok=True)
        if file_path.exists():
            file_path.unlink()

    def update_deployment_log(self, invocation_id: uuid, inv: Invocation):
        """
        updates deployment log with deployment_id, timestamp, invocation_id, _log
        """
        location = "{}/{}".format(self.invocation_path, inv.deployment_id)
        os.makedirs(location, exist_ok=True)
        self.file_write(location, name=str(invocation_id),
                        content=str(json.dumps(inv.to_dict(), cls=file_util.UUIDEncoder)))

    def get_deployment_status(self, deployment_id: uuid):
        """
        Get last deployment log
        """
        history = self.get_deployment_history(deployment_id)
        if len(history) == 0:
            return None
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

    def get_last_invocation_id(self, deployment_id: uuid):
        """
        This method exists since we do not want to have invocation_id in Invocation object, to not confuse users
        """
        location = self.invocation_path / str(deployment_id)
        inv_ids = []
        for file in location.glob('*'):
            inv_timestamp = Invocation.from_dict(json.loads(file.read_text())).timestamp
            inv_ids.append((inv_timestamp, file.name))
        inv_ids.sort(key=lambda x: x[0])
        return inv_ids[-1][1]

    def save_git_transaction_data(self, blueprint_id: uuid, revision_msg: str, job: str, git_backend: str,
                                  repo_url: str, version_id: str = None, commit_sha: str = None):
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

            logger.error(f'Failed to update git log in OfflineStorage database: {str(e)}')
            return False
        logger.debug(f'Updated git log for blueprint-version {blueprint_id}/{version_id}, transaction {job} in OfflineStorage database')
        return True

    def get_git_transaction_data(self, blueprint_id, version_id=None, fetch_all=False):
        """
        Gets last git transaction data (if version_id is not None, specific transaction data). If all, it returns all
        git transaction data, that satisfy conditions
        """
        location = self.git_log_path / str(blueprint_id)
        logfile_paths = sorted([data for data in location.glob("*")], reverse=True)  # first element was last added
        json_logs = [json.load(file.open('r')) for file in logfile_paths]
        if version_id:
            json_logs = [json_log for json_log in json_logs if json_log['version_id'] == version_id]
        if fetch_all:
            return json_logs
        try:
            return [json_logs[0]]
        except IndexError:
            return []

    def get_version_ids(self, blueprint_id: uuid):
        """
        returns list of all version ids for blueprint
        """
        log_data = self.get_git_transaction_data(blueprint_id, fetch_all=True)
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
                        invocation_id varchar (36), 
                        deployment_id varchar (36),
                        blueprint_id varchar (36),
                        version_id varchar(36), 
                        timestamp timestamp, 
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
        logger.info('disconnecting PostgreSQL database')
        self.connection.close()

    def execute(self, command, replacements=None):
        dbcur = self.connection.cursor()
        try:
            if replacements is not None:
                dbcur.execute(command, replacements)
            else:
                dbcur.execute(command)
        except psycopg2.Error as e:
            logger.debug(str(e))
            dbcur.execute("ROLLBACK")
            return False
        dbcur.close()
        self.connection.commit()
        return True

    def version_exists(self, blueprint_id: uuid, version_id=None) -> bool:
        """
        Checks if, according to records in git_log table blueprint (version) exists
        """
        # check blueprint has not been deleted
        dbcur = self.connection.cursor()
        query = "select version_id,job  from {} " \
                "where blueprint_id='{}' " \
                "order by timestamp desc limit 1" \
                .format(Settings.git_log_table, blueprint_id)
        dbcur.execute(query)
        line = dbcur.fetchone()
        if not line:
            # blueprint has never existed
            logger.debug(f"Blueprint {blueprint_id} has never existed")
            return False
        last_version_id, last_job = line[0], line[1]
        if last_version_id is None and last_job == "delete":
            # entire blueprint has been deleted
            logger.debug(f"Entire blueprint {blueprint_id} has been deleted, does not exist any more")
            return False

        if version_id:
            # check version has not been deleted
            query = "select job from {} " \
                    "where blueprint_id='{}' and version_id='{}' " \
                    "order by timestamp desc limit 1" \
                    .format(Settings.git_log_table, blueprint_id, version_id)
            dbcur.execute(query)
            line = dbcur.fetchone()
            if not line:
                # blueprint version has never existed
                logger.debug(f"Blueprint-version {blueprint_id}/{version_id} has never existed")
                return False
            last_job = line[0]
            if last_job == "delete":
                # blueprint version has been deleted
                logger.debug(f"Blueprint-version {blueprint_id}/{version_id} has been deleted, does not exist any more")
                return False

        # all checks have passed, blueprint (version) exists
        return True

    def get_deployment_ids(self, blueprint_id: uuid, version_id: str = None):
        """
        Returns list of deployment_ids od all deployments created from blueprint with blueprint_id (and version_id)
        """
        dbcur = self.connection.cursor()

        if version_id:
            query = "select deployment_id from {} where blueprint_id = '{}' and version_id = '{}' " \
                    "group by deployment_id;" \
                .format(Settings.invocation_table, blueprint_id, version_id)
        else:
            query = "select deployment_id from {} where blueprint_id = '{}' group by deployment_id;" \
                .format(Settings.invocation_table, blueprint_id)

        dbcur.execute(query)
        lines = dbcur.fetchall()
        deployment_ids = [uuid.UUID(line[0]) for line in lines]
        dbcur.close()

        return deployment_ids

    def blueprint_used_in_deployment(self, blueprint_id: uuid, version_id: str = None):
        """
        Checks if blueprint is part of any deployment. If version is specified, it checks if it is used in current
        deployment state
        """
        deployment_ids = self.get_deployment_ids(blueprint_id, version_id)
        if not deployment_ids:
            return False

        if version_id:
            dbcur = self.connection.cursor()
            for deployment_id in deployment_ids:
                query = "select version_id from {} where deployment_id = '{}' order by timestamp desc limit 1"\
                    .format(Settings.invocation_table, deployment_id)
                dbcur.execute(query)
                lines = dbcur.fetchall()
                if lines[0][0] == version_id:
                    return True
            dbcur.close()
            return False
        return True

    def save_opera_session_data(self, deployment_id: uuid, tree: dict):
        """
        Saves .opera file tree to database
        """
        tree_str = json.dumps(tree)
        timestamp = timestamp_util.datetime_now_to_string()
        response = self.execute(
            """insert into {} (deployment_id, timestamp, tree)
               values (%s, %s, %s)
               ON CONFLICT (deployment_id) DO UPDATE
                   SET timestamp=excluded.timestamp,
                   tree=excluded.tree;"""
            .format(Settings.opera_session_data_table), (str(deployment_id), timestamp, tree_str))
        if response:
            logger.info('Updated dot_opera_data in PostgreSQL database')
        else:
            logger.error('Failed to update dot_opera_data in PostgreSQL database')
        return response

    def get_opera_session_data(self, deployment_id):
        """
        Returns dict with keys [deployment_id, timestamp, tree], where tree is content of .opera dir
        """
        dbcur = self.connection.cursor()
        query = "select deployment_id, timestamp, tree  from {} where deployment_id = '{}';" \
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
            logger.info(f'Deleted opera_session_data for {deployment_id} from PostgreSQL database')
        else:
            logger.error(f'Failed to delete opera_session_data for {deployment_id} from PostgreSQL database')
        return response

    def update_deployment_log(self, invocation_id: uuid, inv: Invocation):
        """
        updates deployment log with deployment_id, timestamp, invocation_id, _log
        """
        response = self.execute(
            """insert into {} (deployment_id, timestamp, invocation_id, blueprint_id, version_id, _log)
               values (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (invocation_id) DO UPDATE
                   SET timestamp=excluded.timestamp,
                        _log=excluded._log;"""
            .format(Settings.invocation_table),
            (str(inv.deployment_id), str(inv.timestamp),
             str(invocation_id), str(inv.blueprint_id),
             inv.version_id, json.dumps(inv.to_dict(), cls=file_util.UUIDEncoder)))
        if response:
            logger.info('Updated deployment log in PostgreSQL database')
        else:
            logger.error('Failed to update deployment log in PostgreSQL database')
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

    def get_last_invocation_id(self, deployment_id: uuid):
        """
        This method exists since we do not want to have invocation_id in Invocation object, to not confuse users
        """
        dbcur = self.connection.cursor()

        query = "select timestamp, invocation_id from {} where deployment_id = '{}' order by timestamp desc limit 1;" \
            .format(Settings.invocation_table, deployment_id)

        dbcur.execute(query)
        line = dbcur.fetchone()
        if not line:
            return None
        inv = line[1]
        dbcur.close()

        return inv

    def save_git_transaction_data(self, blueprint_id: uuid, revision_msg: str, job: str, git_backend: str,
                                  repo_url: str, version_id: str = None, commit_sha: str = None):
        """
        Saves transaction data to database
        """
        response = self.execute(
            """insert into {} (blueprint_id, version_id, revision_msg, job, git_backend, repo_url, commit_sha) 
            values (%s, %s, %s, %s, %s, %s, %s)""".format(Settings.git_log_table),
            (str(blueprint_id), version_id, revision_msg, job, git_backend, repo_url, commit_sha))
        if response:
            logger.info('Updated git log in PostgreSQL database')
        else:
            logger.error('Fail to update git log in PostgreSQL database')
        return response

    def get_git_transaction_data(self, blueprint_id: uuid, version_id: str = None, fetch_all: bool = False):
        """
        Gets all transaction data for some blueprint
        """
        inputs = tuple(xi for xi in (str(blueprint_id), version_id) if xi is not None)
        dbcur = self.connection.cursor()
        query = """select blueprint_id, version_id, revision_msg, job, git_backend, repo_url, commit_sha, timestamp
         from {} where blueprint_id = %s {} order by timestamp desc {};""".format(
            Settings.git_log_table, "and version_id = %s" if version_id else "", "limit 1" if not fetch_all else "")

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
        log_data = self.get_git_transaction_data(blueprint_id, fetch_all=True)
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
            logger.info('Updated {} in PostgreSQL database'.format(Settings.project_domain_table))
        else:
            logger.error('Failed to update {} in PostgreSQL database'.format(Settings.project_domain_table))
        return response
