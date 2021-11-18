import json
import uuid

import psycopg2
from psycopg2 import sql
from contextlib import contextmanager

from opera.api.log import get_logger
from opera.api.openapi.models import Invocation, InvocationState, BlueprintVersion, OperationType
from opera.api.settings import Settings
from opera.api.util import timestamp_util, file_util

logger = get_logger(__name__)


class SqlDBFailedException(Exception):
    pass


class PostgreSQL:

    @classmethod
    @contextmanager
    def connection(cls):
        try:
            conn = psycopg2.connect(**Settings.sql_config)
            yield conn
            conn.close()
        except psycopg2.Error as e:
            logger.error(f"Error while connecting to PostgreSQL: {str(e)}")
            raise SqlDBFailedException('Could not connect to PostgreSQL DB')

    @classmethod
    @contextmanager
    def cursor(cls):
        with cls.connection() as conn:
            yield conn.cursor()

    @classmethod
    def execute(cls, command, replacements=None):

        with cls.connection() as conn:
            dbcur = conn.cursor()
            try:
                if replacements is not None:
                    dbcur.execute(command, replacements)
                else:
                    dbcur.execute(command)
                conn.commit()
            except psycopg2.Error as e:
                logger.debug(str(e))
                dbcur.execute("ROLLBACK")
                conn.commit()
                return False

        return True

    @classmethod
    def initialize(cls):

        cls.execute("""
                        create table if not exists {} (
                        invocation_id varchar (36), 
                        deployment_id varchar (36),
                        deployment_label varchar(250),
                        blueprint_id varchar (36),
                        version_id varchar(36),
                        state varchar(36),
                        operation varchar(36),
                        timestamp timestamp, 
                        _log text,  
                        primary key (invocation_id)
                        );""".format(Settings.invocation_table))
        cls.execute("""
                        create table if not exists {} (
                        blueprint_id varchar (36),
                        version_id varchar(36),
                        blueprint_name varchar(250),
                        aadm_id varchar(250),
                        username varchar(250),
                        project_domain varchar(250),
                        url text,
                        timestamp timestamp default current_timestamp, 
                        commit_sha text,
                        primary key (timestamp)
                        );""".format(Settings.blueprint_table))

        cls.execute("""
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

        cls.execute("""
                        create table if not exists {} (
                        deployment_id varchar (36),
                        timestamp timestamp default current_timestamp, 
                        tree text,
                        primary key (deployment_id)
                        );""".format(Settings.opera_session_data_table))

    @classmethod
    def version_exists(cls, blueprint_id: uuid, version_id=None) -> bool:
        """
        Checks if, according to records in git_log table blueprint (version) exists
        """
        # TODO change to inspect blueprint table
        # check blueprint has not been deleted
        with cls.cursor() as dbcur:
            stmt = sql.SQL("""select version_id,job  from {git_log_table} 
                                where blueprint_id={blueprint_id} 
                                order by timestamp desc limit 1;""").format(
                git_log_table=sql.Identifier(Settings.git_log_table),
                blueprint_id=sql.Literal(str(blueprint_id))
            )
            dbcur.execute(stmt)
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
                stmt = sql.SQL("""select job from {git_log_table} 
                                    where blueprint_id={blueprint_id} and version_id={version_id}
                                    order by timestamp desc limit 1;""").format(
                    git_log_table=sql.Identifier(Settings.git_log_table),
                    blueprint_id=sql.Literal(str(blueprint_id)),
                    version_id=sql.Literal(version_id)
                )
                dbcur.execute(stmt)
                line = dbcur.fetchone()
                if not line:
                    # blueprint version has never existed
                    logger.debug(f"Blueprint-version {blueprint_id}/{version_id} has never existed")
                    return False
                last_job = line[0]
                if last_job == "delete":
                    # blueprint version has been deleted
                    logger.debug(
                        f"Blueprint-version {blueprint_id}/{version_id} has been deleted, does not exist any more")
                    return False

            # all checks have passed, blueprint (version) exists
            return True

    @classmethod
    def get_deployment_ids(cls, blueprint_id: uuid, version_id: str = None):
        """
        Returns list of deployment_ids od all deployments created from blueprint with blueprint_id (and version_id)
        """
        with cls.cursor() as dbcur:

            if version_id:
                stmt = sql.SQL("""select deployment_id from {invocation_table} 
                                    where blueprint_id = {blueprint_id} and version_id = {version_id}
                                    group by deployment_id;""").format(
                    invocation_table=sql.Identifier(Settings.invocation_table),
                    blueprint_id=sql.Literal(str(blueprint_id)),
                    version_id=sql.Literal(version_id)
                )
            else:
                stmt = sql.SQL("""select deployment_id from {invocation_table} 
                                    where blueprint_id = {blueprint_id}
                                    group by deployment_id;""").format(
                    invocation_table=sql.Identifier(Settings.invocation_table),
                    blueprint_id=sql.Literal(str(blueprint_id))
                )

            dbcur.execute(stmt)
            lines = dbcur.fetchall()
            deployment_ids = [line[0] for line in lines]

            return deployment_ids

    @classmethod
    def blueprint_used_in_deployment(cls, blueprint_id: uuid, version_id: str = None):
        """
        Checks if blueprint is part of any deployment. If version is specified, it checks if it is used in current
        deployment state
        """
        deployment_ids = cls.get_deployment_ids(blueprint_id, version_id)
        if not deployment_ids:
            return False

        if version_id:
            with cls.cursor() as dbcur:
                for deployment_id in deployment_ids:
                    stmt = sql.SQL("""select version_id from {invocation_table} 
                                        where deployment_id = {deployment_id} 
                                        order by timestamp desc limit 1;""").format(
                        invocation_table=sql.Identifier(Settings.invocation_table),
                        deployment_id=sql.Literal(str(deployment_id))
                    )
                    dbcur.execute(stmt)
                    lines = dbcur.fetchall()
                    if lines[0][0] == version_id:
                        return True
                return False
        return True

    @classmethod
    def save_opera_session_data(cls, deployment_id: uuid, tree: dict):
        """
        Saves .opera file tree to database
        """
        tree_str = json.dumps(tree)
        timestamp = timestamp_util.datetime_now_to_string()
        response = cls.execute(
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

    @classmethod
    def get_opera_session_data(cls, deployment_id):
        """
        Returns dict with keys [deployment_id, timestamp, tree], where tree is content of .opera dir
        """
        with cls.cursor() as dbcur:
            stmt = sql.SQL("""select deployment_id, timestamp, tree from {session_data_table} 
                                where deployment_id = {deployment_id};""").format(
                session_data_table=sql.Identifier(Settings.opera_session_data_table),
                deployment_id=sql.Literal(str(deployment_id))
            )
            dbcur.execute(stmt)
            line = dbcur.fetchone()
            if not line:
                return None
            session_data = {
                'deployment_id': line[0],
                'timestamp': timestamp_util.datetime_to_str(line[1]),
                'tree': json.loads(line[2])
            }
            return session_data

    @classmethod
    def delete_opera_session_data(cls, deployment_id: uuid):
        """
        Deletes opera session data
        """
        stmt = sql.SQL("""delete from {session_data_table} 
                            where deployment_id = {deployment_id}""").format(
            session_data_table=sql.Identifier(Settings.opera_session_data_table),
            deployment_id=sql.Literal(str(deployment_id))
        )

        success = cls.execute(stmt)

        if success:
            logger.debug(
                f'Deleted opera_session_data for deployment_id={deployment_id} from PostgreSQL database')
        else:
            logger.error(
                f'Failed to delete opera_session_data for deployment_id={deployment_id} from PostgreSQL database')

        return success

    @classmethod
    def update_deployment_log(cls, invocation_id: uuid, inv: Invocation):
        """
        updates deployment log with deployment_id, timestamp_submission, invocation_id, _log
        """

        response = cls.execute(
            """insert into {} (deployment_id, deployment_label, timestamp, invocation_id, 
                              blueprint_id, version_id, state, operation, _log)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (invocation_id) DO UPDATE
                   SET timestamp=excluded.timestamp,
                       state=excluded.state,
                       operation=excluded.operation,
                        _log=excluded._log;"""
                .format(Settings.invocation_table),
            (str(inv.deployment_id), inv.deployment_label, str(inv.timestamp_submission), str(invocation_id),
             str(inv.blueprint_id),
             inv.version_id, inv.state, inv.operation, json.dumps(inv.to_dict(), cls=file_util.UUIDEncoder)))
        deployment_id = inv.deployment_id
        if response:
            logger.debug(
                f'Updated deployment log for deployment_id={deployment_id} and invocation_id={invocation_id} in PostgreSQL database')
        else:
            logger.error(
                f'Failed to update deployment log for deployment_id={deployment_id} and invocation_id={invocation_id} '
                f'in PostgreSQL database')
        return response

    @classmethod
    def get_deployment_status(cls, deployment_id: uuid):
        """
        Get last deployment log
        """

        with cls.cursor() as dbcur:
            stmt = sql.SQL("""select timestamp, _log from {invocation_table} 
                                where deployment_id = {deployment_id} 
                                order by timestamp desc limit 1;""").format(
                invocation_table=sql.Identifier(Settings.invocation_table),
                deployment_id=sql.Literal(str(deployment_id))
            )

            dbcur.execute(stmt)
            line = dbcur.fetchone()
            if not line:
                return None
            inv = Invocation.from_dict(json.loads(line[1]))

            return inv

    # TODO Implemented due to update's need for one before last invocation
    #   remove when solved properly
    @classmethod
    def get_last_completed_invocation(cls, deployment_id: uuid):
        history = cls.get_deployment_history(deployment_id)
        if len(history) == 0:
            return None
        history_completed = [x for x in history if x.state in (InvocationState.SUCCESS, InvocationState.FAILED)]
        return history_completed[-1]

    @classmethod
    def get_deployment_history(cls, deployment_id: uuid):
        """
        Get all deployment logs for one deployment
        """
        with cls.cursor() as dbcur:
            stmt = sql.SQL("""select timestamp, _log from {invocation_table} 
                                where deployment_id = {deployment_id}
                                order by timestamp;""").format(
                invocation_table=sql.Identifier(Settings.invocation_table),
                deployment_id=sql.Literal(str(deployment_id))
            )

            dbcur.execute(stmt)
            lines = dbcur.fetchall()
            history = [Invocation.from_dict(json.loads(line[1])) for line in lines]

            return history

    @classmethod
    def get_last_invocation_id(cls, deployment_id: uuid):
        """
        This method exists since we do not want to have invocation_id in Invocation object, to not confuse users
        """
        with cls.cursor() as dbcur:
            stmt = sql.SQL("""select timestamp, invocation_id from {invocation_table} 
                                where deployment_id = {deployment_id} 
                                order by timestamp desc limit 1;""").format(
                invocation_table=sql.Identifier(Settings.invocation_table),
                deployment_id=sql.Literal(str(deployment_id))
            )

            dbcur.execute(stmt)
            line = dbcur.fetchone()
            if not line:
                return None
            inv = line[1]

            return inv

    @classmethod
    def save_git_transaction_data(cls, blueprint_id: uuid, revision_msg: str, job: str, git_backend: str,
                                  repo_url: str, version_id: str = None, commit_sha: str = None):
        """
        Saves transaction data to database
        """
        response = cls.execute(
            """insert into {} (blueprint_id, version_id, revision_msg, job, git_backend, repo_url, commit_sha) 
            values (%s, %s, %s, %s, %s, %s, %s)""".format(Settings.git_log_table),
            (str(blueprint_id), version_id, revision_msg, job, git_backend, repo_url, commit_sha))
        if response:
            logger.debug(
                f'Updated git log for blueprint_id={blueprint_id} and version_id={version_id} in PostgreSQL database')
        else:
            logger.error(
                f'Failed to update git log blueprint_id={blueprint_id} and version_id={version_id} in '
                f'PostgreSQL database')
        return response

    @classmethod
    def get_git_transaction_data(cls, blueprint_id: uuid):
        """
        Gets all transaction data for some blueprint
        """
        with cls.cursor() as dbcur:
            stmt = sql.SQL("""select blueprint_id, version_id, revision_msg, job, git_backend, 
                                                     repo_url, commit_sha, timestamp from {git_log_table} 
                                                     where blueprint_id = {blueprint_id}
                                                     order by timestamp desc""").format(
                git_log_table=sql.Identifier(Settings.git_log_table),
                blueprint_id=sql.Literal(str(blueprint_id))
            )

            dbcur.execute(stmt)
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

            return git_transaction_data_list

    @classmethod
    def get_project_domain(cls, blueprint_id: uuid):
        """
        returns project domain for blueprint
        """
        with cls.cursor() as dbcur:
            stmt = sql.SQL("""select blueprint_id, project_domain from {blueprint_table} 
                               where blueprint_id = {blueprint_id};""").format(
                blueprint_table=sql.Identifier(Settings.blueprint_table),
                blueprint_id=sql.Literal(str(blueprint_id))
            )
            dbcur.execute(stmt)
            line = dbcur.fetchone()
            if not line:
                return None
            project_domain = line[1]

            return project_domain

    @classmethod
    def get_blueprint_name(cls, blueprint_id: uuid):
        """
        Returns human-readable name for blueprint
        """
        with cls.cursor() as dbcur:
            stmt = sql.SQL("""select blueprint_id, blueprint_name from {blueprint_table} 
                               where blueprint_id = {blueprint_id}""").format(
                blueprint_table=sql.Identifier(Settings.blueprint_table),
                blueprint_id=sql.Literal(str(blueprint_id)),
            )
            dbcur.execute(stmt)
            line = dbcur.fetchone()
            if not line:
                return None
            name = line[1]
            return name

    @classmethod
    def update_blueprint_name(cls, blueprint_id: uuid, name: str):
        """
        updates blueprint name
        """
        stmt = sql.SQL("""update {blueprint_table}
                set blueprint_name = {blueprint_name}
                where blueprint_id = {blueprint_id}""").format(
            blueprint_table=sql.Identifier(Settings.blueprint_table),
            blueprint_name=sql.Literal(name),
            blueprint_id=sql.Literal(str(blueprint_id))
        )
        success = cls.execute(stmt)
        if success:
            logger.debug(f'Updated blueprint name={name} for blueprint_id={blueprint_id} in PostgreSQL database')
        else:
            logger.error(f'Fail to update blueprint name={name} for blueprint_id={blueprint_id} in PostgreSQL database')
        return success

    @classmethod
    def get_blueprint_meta(cls, blueprint_id: uuid, version_id: str = None):
        """
        returns blueprint (version's) metadata
        """
        with cls.cursor() as dbcur:
            if version_id:
                stmt = sql.SQL("""select blueprint_id, version_id, blueprint_name, aadm_id, username, 
                                           project_domain, url, timestamp, commit_sha from {blueprint_table}
                                            where blueprint_id = {blueprint_id} and version_id = {version_id}
                                            order by timestamp desc limit 1;""").format(
                    blueprint_table=sql.Identifier(Settings.blueprint_table),
                    blueprint_id=sql.Literal(str(blueprint_id)),
                    version_id=sql.Literal(version_id)
                )
            else:
                stmt = sql.SQL("""select blueprint_id, version_id, blueprint_name, aadm_id, username, 
                           project_domain, url, timestamp, commit_sha from {blueprint_table}
                            where blueprint_id = {blueprint_id}
                            order by timestamp desc limit 1;""").format(
                    blueprint_table=sql.Identifier(Settings.blueprint_table),
                    blueprint_id=sql.Literal(str(blueprint_id)),
                )
            dbcur.execute(stmt)
            line = dbcur.fetchone()
            if not line:
                return None
            blueprint_meta = {
                'blueprint_id': line[0],
                'version_id': line[1],
                'blueprint_name': line[2],
                'aadm_id': line[3],
                'username': line[4],
                'project_domain': line[5],
                'url': line[6],
                'timestamp': timestamp_util.datetime_to_str(line[7]),
                'commit_sha': line[8]
            }
            return blueprint_meta

    @classmethod
    def save_blueprint_meta(cls, blueprint_meta: BlueprintVersion):
        """
        saves metadata of blueprint version
        """
        success = cls.execute(
            """insert into {} (blueprint_id, version_id, blueprint_name, aadm_id, username, project_domain, url, commit_sha) 
            values (%s, %s, %s, %s, %s, %s, %s, %s)""".format(Settings.blueprint_table),
            (str(blueprint_meta.blueprint_id), blueprint_meta.version_id, blueprint_meta.blueprint_name,
             blueprint_meta.aadm_id, blueprint_meta.username,
             blueprint_meta.project_domain, blueprint_meta.url, blueprint_meta.commit_sha))
        blueprint_id = blueprint_meta.blueprint_id
        if success:
            logger.debug(f'Updated blueprint meta for blueprint_id={blueprint_id} in PostgreSQL database')
        else:
            logger.error(f'Fail to update blueprint meta for blueprint_id={blueprint_id} in PostgreSQL database')
        return success

    @classmethod
    def delete_blueprint_meta(cls, blueprint_id: uuid, version_id: str = None):
        """
        deletes blueprint meta of one or all versions
        """
        if version_id:
            stmt = sql.SQL("""delete from {blueprint_table} 
                                where blueprint_id = {blueprint_id} and version_id = {version_id}""").format(
                blueprint_table=sql.Identifier(Settings.blueprint_table),
                blueprint_id=sql.Literal(str(blueprint_id)),
                version_id=sql.Literal(version_id),
            )

        else:
            stmt = sql.SQL("""delete from {blueprint_table} 
                                where blueprint_id = {blueprint_id}""").format(
                blueprint_table=sql.Identifier(Settings.blueprint_table),
                blueprint_id=sql.Literal(str(blueprint_id))
            )

        str_version_id = f'and version_id={version_id} ' if version_id else ''

        success = cls.execute(stmt)

        if success:
            logger.debug(
                f'Deleted blueprint metadata for blueprint_id={blueprint_id} {str_version_id}from PostgreSQL database')
        else:
            logger.error(
                f'Failed to delete blueprint metadata for blueprint_id={blueprint_id} {str_version_id}from PostgreSQL database')

        return success

    @classmethod
    def get_inputs(cls, deployment_id: uuid):
        """
        extracts inputs from last invocation, belonging to deployment with this deployment_id
        """
        with cls.cursor() as dbcur:
            stmt = sql.SQL("""select _log::json->>'inputs' from {invocation_table}
                                where deployment_id = {deployment_id}
                                order by timestamp desc limit 1""").format(
                invocation_table=sql.Identifier(Settings.invocation_table),
                deployment_id=sql.Literal(str(deployment_id))
            )
            dbcur.execute(stmt)
            line = dbcur.fetchone()
            if not line:
                return None
            try:
                return json.loads(line[0])
            except (json.decoder.JSONDecodeError, TypeError):
                return None

    @classmethod
    def get_deployments_for_blueprint(cls, blueprint_id: uuid, active: bool):
        """
        Returns [Deployment] for every deployment, created from blueprint
        """
        with cls.cursor() as dbcur:
            stmt = sql.SQL("""select distinct on (deployment_id) deployment_id, state, operation, 
                                timestamp, deployment_label from {invocation_table}
                                where deployment_id in (
                                    select deployment_id
                                    from {invocation_table}
                                    where blueprint_id = {blueprint_id}
                                )
                       order by deployment_id, timestamp desc;""").format(
                invocation_table=sql.Identifier(Settings.invocation_table),
                blueprint_id=sql.Literal(str(blueprint_id)),
            )
            dbcur.execute(stmt)
            lines = dbcur.fetchall()
            deployment_list = [
                {
                    'deployment_id': line[0],
                    'state': line[1],
                    'operation': line[2],
                    'timestamp': timestamp_util.datetime_to_str(line[3]),
                    'last_inputs': cls.get_inputs(line[0]),
                    'deployment_label': line[4]
                } for line in lines
            ]
            deployment_list.sort(key=lambda x: x['timestamp'], reverse=True)
            if active:
                # remove successfully completed undeploy jobs
                deployment_list = [x for x in deployment_list if not (x['operation'] == OperationType.UNDEPLOY and
                                                                      x['state'] == InvocationState.SUCCESS)]

            return deployment_list

    @classmethod
    def get_blueprints_by_user_or_project(cls, username: str = None, project_domain: str = None, active: bool = True):
        """
        Returns [blueprint_id] for every blueprint, that belongs to user or project (or both)
        """
        with cls.cursor() as dbcur:
            if username and not project_domain:
                stmt = sql.SQL("""select distinct on (blueprint_id) blueprint_id, blueprint_name, aadm_id, 
                                    username, project_domain, timestamp from {blueprint_table}
                                    where username={username}""").format(
                    blueprint_table=sql.Identifier(Settings.blueprint_table),
                    username=sql.Literal(username),
                )
            elif not username and project_domain:
                stmt = sql.SQL("""select distinct on (blueprint_id) blueprint_id, blueprint_name, aadm_id, 
                                    username, project_domain, timestamp from {blueprint_table}
                                    where project_domain={project_domain}""").format(
                    blueprint_table=sql.Identifier(Settings.blueprint_table),
                    project_domain=sql.Literal(project_domain)
                )
            else:
                stmt = sql.SQL("""select distinct on (blueprint_id) blueprint_id, blueprint_name, aadm_id, 
                                    username, project_domain, timestamp from {blueprint_table}
                                    where username={username} and project_domain={project_domain}""").format(
                    blueprint_table=sql.Identifier(Settings.blueprint_table),
                    username=sql.Literal(username),
                    project_domain=sql.Literal(project_domain)
                )
            dbcur.execute(stmt)
            lines = dbcur.fetchall()
            blueprint_list = [
                {
                    "blueprint_id": line[0],
                    "blueprint_name": line[1],
                    "aadm_id": line[2],
                    "username": line[3],
                    "project_domain": line[4],
                    "timestamp": timestamp_util.datetime_to_str(line[5])
                } for line in lines
            ]

            if active:
                # remove blueprints with no active deployment

                # get all deployments and their last state and operations
                stmt2 = sql.SQL("""select distinct on (deployment_id) deployment_id, blueprint_id, state, operation, 
                                                timestamp from {invocation_table}
                                                where deployment_id in (
                                                    select deployment_id
                                                    from {invocation_table}
                                                )
                                       order by deployment_id, timestamp desc;""").format(
                    invocation_table=sql.Identifier(Settings.invocation_table)
                )
                dbcur.execute(stmt2)
                lines2 = dbcur.fetchall()

                # get active deployments
                blueprint_ids = [line[1] for line in lines2 if not (line[2] == InvocationState.SUCCESS and
                                                                    line[3] == OperationType.UNDEPLOY)]

                blueprint_list = [x for x in blueprint_list if (x['blueprint_id'] in blueprint_ids)]

            return blueprint_list

    @classmethod
    def delete_deployment(cls, deployment_id: uuid):
        """
        Deletes deployment data
        """
        stmt = sql.SQL("""delete from {invocation_table} 
                            where deployment_id = {deployment_id}""").format(
            invocation_table=sql.Identifier(Settings.invocation_table),
            deployment_id=sql.Literal(str(deployment_id))
        )

        success = cls.execute(stmt)

        if success:
            logger.debug(
                f'Deleted deployment for deployment_id={deployment_id} from PostgreSQL database')
        else:
            logger.error(
                f'Failed to delete deployment for deployment_id={deployment_id} from PostgreSQL database')

        return success
