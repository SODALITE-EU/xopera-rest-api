import json
import uuid

import psycopg2

from opera.api.log import get_logger
from opera.api.openapi.models import Invocation, InvocationState, Blueprint
from opera.api.settings import Settings
from opera.api.util import timestamp_util, file_util

logger = get_logger(__name__)


def connect(sql_config):
    try:
        database = PostgreSQL(sql_config)
        logger.info('SQL_database: PostgreSQL')
    except psycopg2.Error as e:
        logger.error(f"Error while connecting to PostgreSQL: {str(e)}")
        database = Database()
        logger.info("SQL_database: NoDatabase!")

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

    # TODO Implemented due to update's need for one before last invocation
    #   remove when solved properly
    def get_last_completed_invocation(self, deployment_id: uuid):
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

    def get_blueprint_name(self, blueprint_id: uuid):
        """
        Returns human-readable name for blueprint
        """
        pass

    def update_blueprint_name(self, blueprint_id: uuid, name: str):
        """
        updates blueprint name
        """
        pass

    def get_blueprint_meta(self, blueprint_id: uuid, version_id: str = None):
        """
        returns blueprint (version's) metadata
        """
        pass

    def save_blueprint_meta(self, blueprint_meta: Blueprint):
        """
        saves metadata of blueprint version
        """
        pass

    def delete_blueprint_meta(self, blueprint_id: uuid, version_id: str = None):
        """
        deletes blueprint meta of one or all versions
        """
        pass

    def get_deployments_for_blueprint(self, blueprint_id: uuid):
        """
        Returns [Deployment] for every deployment, created from blueprint
        """
        pass


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
                        state varchar(36),
                        operation varchar(36),
                        timestamp timestamp, 
                        _log text,  
                        primary key (invocation_id)
                        );""".format(Settings.invocation_table))
        self.execute("""
                        create table if not exists {} (
                        blueprint_id varchar (36),
                        version_id varchar(36),
                        name varchar(250),
                        project_domain varchar(250),
                        url text,
                        timestamp timestamp default current_timestamp, 
                        commit_sha text,
                        primary key (timestamp)
                        );""".format(Settings.blueprint_table))

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
                query = "select version_id from {} where deployment_id = '{}' order by timestamp desc limit 1" \
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
            logger.debug(f'Updated dot_opera_data for deployment_id={deployment_id} in PostgreSQL database')
        else:
            logger.error(f'Failed to update dot_opera_data for deployment_id={deployment_id} in PostgreSQL database')
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
            logger.debug(f'Deleted opera_session_data for deployment_id={deployment_id} from PostgreSQL database')
        else:
            logger.error(
                f'Failed to delete opera_session_data for deployment_id={deployment_id} from PostgreSQL database')
        return response

    def update_deployment_log(self, invocation_id: uuid, inv: Invocation):
        """
        updates deployment log with deployment_id, timestamp_submission, invocation_id, _log
        """
        response = self.execute(
            """insert into {} (deployment_id, timestamp, invocation_id, blueprint_id, version_id, state, operation, _log)
               values (%s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (invocation_id) DO UPDATE
                   SET timestamp=excluded.timestamp,
                       state=excluded.state,
                       operation=excluded.operation,
                        _log=excluded._log;"""
                .format(Settings.invocation_table),
            (str(inv.deployment_id), str(inv.timestamp_submission),
             str(invocation_id), str(inv.blueprint_id),
             inv.version_id, inv.state, inv.operation,
             json.dumps(inv.to_dict(), cls=file_util.UUIDEncoder)))
        deployment_id = inv.deployment_id
        if response:
            logger.debug(
                f'Updated deployment log for deployment_id={deployment_id} and invocation_id={invocation_id} in PostgreSQL database')
        else:
            logger.error(
                f'Failed to update deployment log for deployment_id={deployment_id} and invocation_id={invocation_id} '
                f'in PostgreSQL database')
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

    # TODO Implemented due to update's need for one before last invocation
    #   remove when solved properly
    def get_last_completed_invocation(self, deployment_id: uuid):
        history = self.get_deployment_history(deployment_id)
        if len(history) == 0:
            return None
        history_completed = [x for x in history if x.state in (InvocationState.SUCCESS, InvocationState.FAILED)]
        return history_completed[-1]

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
            logger.debug(
                f'Updated git log for blueprint_id={blueprint_id} and version_id={version_id} in PostgreSQL database')
        else:
            logger.error(
                f'Fail to update git log blueprint_id={blueprint_id} and version_id={version_id} in PostgreSQL database')
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
            Settings.blueprint_table, blueprint_id)
        dbcur.execute(query)
        line = dbcur.fetchone()
        if not line:
            return None
        project_domain = line[1]
        dbcur.close()
        return project_domain

    def get_blueprint_name(self, blueprint_id: uuid):
        """
        Returns human-readable name for blueprint
        """
        dbcur = self.connection.cursor()
        query = """select blueprint_id, name from {} where blueprint_id = '{}';""".format(
            Settings.blueprint_table, blueprint_id)
        dbcur.execute(query)
        line = dbcur.fetchone()
        if not line:
            return None
        name = line[1]
        dbcur.close()
        return name

    def update_blueprint_name(self, blueprint_id: uuid, name: str):
        """
        updates blueprint name
        """
        success = self.execute(
            """update {}
                set name = '{}'
                where blueprint_id = '{}'""".format(Settings.blueprint_table, name, str(blueprint_id)))
        if success:
            logger.debug(f'Updated blueprint name={name} for blueprint_id={blueprint_id} in PostgreSQL database')
        else:
            logger.error(f'Fail to update blueprint name={name} for blueprint_id={blueprint_id} in PostgreSQL database')
        return success

    def get_blueprint_meta(self, blueprint_id: uuid, version_id: str = None):
        """
        returns blueprint (version's) metadata
        """
        dbcur = self.connection.cursor()
        version_str = f"and version_id = '{version_id}'" if version_id else ''
        query = """select * from {}
                    where blueprint_id = '{}'
                    {}
                    order by timestamp desc limit 1;""".format(
            Settings.blueprint_table, blueprint_id, version_str)
        dbcur.execute(query)
        line = dbcur.fetchone()
        dbcur.close()
        if not line:
            return None
        blueprint_meta = {
            'blueprint_id': line[0],
            'version_id': line[1],
            'name': line[2],
            'project_domain': line[3],
            'url': line[4],
            'timestamp': timestamp_util.datetime_to_str(line[5]),
            'commit_sha': line[6],
            'deployments': self.get_deployments_for_blueprint(blueprint_id) or None
        }
        return blueprint_meta

    def save_blueprint_meta(self, blueprint_meta: Blueprint):
        """
        saves metadata of blueprint version
        """
        success = self.execute(
            """insert into {} (blueprint_id, version_id, name, project_domain, url, commit_sha) 
            values (%s, %s, %s, %s, %s, %s)""".format(Settings.blueprint_table),
            (str(blueprint_meta.blueprint_id), blueprint_meta.version_id, blueprint_meta.name,
             blueprint_meta.project_domain, blueprint_meta.url, blueprint_meta.commit_sha))
        blueprint_id = blueprint_meta.blueprint_id
        if success:
            logger.debug(f'Updated blueprint meta for blueprint_id={blueprint_id} in PostgreSQL database')
        else:
            logger.error(f'Fail to update blueprint meta for blueprint_id={blueprint_id} in PostgreSQL database')
        return success

    def delete_blueprint_meta(self, blueprint_id: uuid, version_id: str = None):
        """
        deletes blueprint meta of one or all versions
        """
        if version_id:
            success = self.execute(
                "delete from {} where blueprint_id = '{}' and version_id = '{}'"
                    .format(Settings.blueprint_table, str(blueprint_id), version_id))

        else:
            success = self.execute(
                "delete from {} where blueprint_id = '{}'"
                    .format(Settings.blueprint_table, str(blueprint_id)))

        str_version_id = f'and version_id={version_id} ' if version_id else ''

        if success:
            logger.debug(
                f'Deleted blueprint metadata for blueprint_id={blueprint_id} {str_version_id}from PostgreSQL database')
        else:
            logger.error(
                f'Failed to delete blueprint metadata for blueprint_id={blueprint_id} {str_version_id}from PostgreSQL database')

        return success

    def get_deployments_for_blueprint(self, blueprint_id: uuid):
        """
        Returns [Deployment] for every deployment, created from blueprint
        """
        dbcur = self.connection.cursor()
        query = """select distinct on (deployment_id) deployment_id, state, operation, timestamp 
                   from {}
                   where deployment_id in (
                        select deployment_id
                        from {}
                        where blueprint_id = '{}'
                   )
                   order by deployment_id, timestamp desc;""" \
            .format(Settings.invocation_table, Settings.invocation_table, blueprint_id)
        dbcur.execute(query)
        lines = dbcur.fetchall()
        blueprint_list = [
            {
                'deployment_id': line[0],
                'state': line[1],
                'operation': line[2],
                'timestamp': timestamp_util.datetime_to_str(line[3])
            } for line in lines
        ]
        dbcur.close()
        return blueprint_list
