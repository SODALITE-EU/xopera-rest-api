import datetime
import glob
import grp
import json
import logging as log
import os
import pwd
import re
import shutil
import uuid
from pathlib import Path

import psycopg2

from deployment_preparation.dns import _validate_dns_format
from deployment_preparation.dp_types import Deployment, File, Directory
from deployment_preparation.settings import Settings


class Database:

    def __init__(self):
        self.db_type = "unknown type of database"
        pass

    def disconnect(self):
        """
        closes database connection
        """
        pass

    def check_token_exists(self, blueprint_token: str):
        """
        check if blueprint_token exists in database
        """
        pass

    def get_max_version_id(self, blueprint_token: str):
        """
        returns max version_id among database entries with specified blueprint_token
        """
        pass

    def get_timestamp(self, blueprint_token: str, version_id: int):
        """
        returns timestamp of blueprint with given blueprint_token and version_id
        """
        pass

    def remove_last_job_tag(self, blueprint_token: str):
        """
        nullifies all last_job fields of database entries with blueprint_token
        usage: since only last entry under blueprint_token can have last_job field not null,
        it has to be removed before writting new one.
        """
        pass

    def add_revision(self, deploy: Deployment, version_id: int):
        """
        saves deployment into database
        parameters to be saved: blueprint_token, blueprint_id, tosca_definition,
        ansible_definition, config_file, version_id
        """
        pass

    def update_blueprint_data(self, location: str, blueprint_token: str, last_job: str, timestamp: str):
        """
        updates last_deployment data and last_job to entry,
        referenced by combination of blueprint_token and timestamp
        """
        pass

    def update_deployment_log(self, _id, blueprint_token: str, _log: str, session_token: str, timestamp: str):
        """
        updates deployment log with id, blueprint_token, timestamp, session_token, _log
        """
        pass

    def get_deployment_log(self, blueprint_token: str = None, session_token: str = None):
        """
        Returns deployment log.
        It can query by blueprint_token, session_token or combination of both
        In case of no results returns [0, "not enough parameters"]
        """
        pass

    def get_last_deployment_data(self, blueprint_token, timestamp: str = None, version_id: int = None):
        """
        Returns last deployment data.
        - if timestamp not None -> retrieves by blueprint_token and timestamp
        - if timestamp None and version_id not None -> retrieves by blueprint_token and version_id
        - if both None -> retrieves just by blueprint_token
        In case of no results returns None
        """
        pass

    def get_revision(self, blueprint_token, timestamp: str = None, version_id: int = None):
        """
        Retrieves blueprint as instance of Deployment class from database.
        - if timestamp not None -> retrieves by blueprint_token and timestamp
        - if timestamp None and version_id not None -> retrieves by blueprint_token and version_id
        - if both None -> retrieves just by blueprint_token
        In case of no results returns None
        """
        pass

    def delete_blueprint(self, blueprint_id, timestamp: str = None, version_id: int = None):
        """
        Deletes blueprint(s).
        - if timestamp not None -> delete by blueprint_token and timestamp
        - if timestamp None and version_id not None -> delete by blueprint_token and version_id
        - if both None -> delete all blueprint with blueprint_id
        Method returns number of deleted database entries
        """
        pass

    def last_job(self, blueprint_token, timestamp: datetime = None, version_id: int = None):
        """
        Returns last job.
        - if timestamp not None -> Retrieves last job by blueprint_token and timestamp
        - if timestamp None and version_id not None -> Retrieves last job by blueprint with delete by blueprint_token and version_id
        - if both None -> Checks all entries. Only ne should have last_job field not null, but just in case:
                          1) checks, if any of entries has last_job set to 'deploy'
                          2) checks, if any of entries has last_job set to 'undeploy'
                          3) else, returns None
        In case of no entries, it returns None
        """
        pass


class OfflineStorage(Database):
    def __init__(self):
        super().__init__()
        self.db_type = 'OfflineStorage'

        if not os.path.exists(Settings.offline_storage):
            os.mkdir(Settings.offline_storage)
        if not os.path.exists(Settings.offline_blueprints):
            os.mkdir(Settings.offline_blueprints)
        if not os.path.exists(Settings.offline_log):
            os.mkdir(Settings.offline_log)

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

    def check_token_exists(self, blueprint_token: str):
        """
        check if blueprint_token exists in database
        """
        location = "{}{}".format(Settings.offline_blueprints, blueprint_token)
        return os.path.exists(location)

    def get_max_version_id(self, blueprint_token: str):
        """
        returns max version_id among database entries with specified blueprint_token
        """
        pattern = "{}{}/*/version_id".format(Settings.offline_blueprints, blueprint_token)

        filenames = glob.glob(pattern)
        version_ids = [int(self.file_read(path)) for path in filenames] + [0]
        return max(version_ids)

    def get_timestamp(self, blueprint_token: str, version_id: int):
        """
        returns timestamp of blueprint with given blueprint_token and version_id
        """
        pattern = "{}{}/*/version_id".format(Settings.offline_blueprints, blueprint_token)
        filenames = glob.glob(pattern)

        timestamp = [path.split('/')[-2] for path in filenames if int(self.file_read(path)) == version_id]
        if len(timestamp) == 0:
            return None
        return Settings.str_to_datetime(timestamp[0])

    def remove_last_job_tag(self, blueprint_token: str):
        """
        nullifies all last_job fields of database entries with blueprint_token
        usage: since only last entry under blueprint_token can have last_job field not null,
        it has to be removed before writting new one.
        """
        # list all last_job files
        pattern = "{}{}/*/last_job".format(Settings.offline_blueprints, blueprint_token)
        filenames = glob.glob(pattern)

        # empty files
        for path in filenames:
            open(path, 'w').close()

    def add_revision(self, deploy: Deployment, version_id: int):
        """
        saves deployment into database
        parameters to be saved: blueprint_token, blueprint_id, tosca_definition,
        ansible_definition, config_file, version_id
        """
        timestamp = Settings.datetime_now_to_string()
        rcfile = None
        if deploy.rc_file is not None:
            rcfile = json.dumps(deploy.rc_file.to_dict())

        location = "{}{}/{}".format(Settings.offline_blueprints, deploy.blueprint_token, timestamp)
        os.makedirs(location)
        self.file_write(location, name="id", content=str(deploy.id))
        self.file_write(location, name="blueprint_token", content=str(deploy.blueprint_token))
        self.file_write(location, name="version_time", content=timestamp)
        self.file_write(location, name="tosca_definition", content=json.dumps(deploy.tosca.to_dict()))
        self.file_write(location, name="ansible_definition", content=json.dumps(deploy.ansible_tree.to_dict()))
        self.file_write(location, name="config_file", content=rcfile)
        self.file_write(location, name="version_id", content=str(version_id))
        self.file_write(location, name="last_deployment_data", content="")
        self.file_write(location, name="last_job", content="")

        log.info('added revision to OfflineStorage database')
        return True

    def update_blueprint_data(self, location: str, blueprint_token: str, last_job: str, timestamp: str):
        """
        updates last_deployment data and last_job to entry,
        referenced by combination of blueprint_token and timestamp
        """
        # just one entry with last_job field is legal
        self.remove_last_job_tag(blueprint_token)
        path = "{}{}/{}".format(Settings.offline_blueprints, blueprint_token, timestamp)
        self.file_write(path=path, name="last_deployment_data",
                        content=json.dumps(Directory.read(Path(location)).to_dict()))
        self.file_write(path=path, name="last_job", content=last_job)

    def update_deployment_log(self, _id, blueprint_token: str, _log: str, session_token: str, timestamp: str):
        """
        updates deployment log with id, blueprint_token, timestamp, session_token, _log
        """
        location = "{}{}".format(Settings.offline_log, session_token)
        if os.path.exists(location):
            shutil.rmtree(location)
        os.makedirs(location)
        self.file_write(location, name="id", content=str(_id))
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
            path = "{}{}".format(Settings.offline_log, session_token)
            try:
                if not self.file_read(path, 'blueprint_token') == str(blueprint_token):
                    # combination of blueprint_token and session_token does not exist
                    return []
            except FileNotFoundError:
                # session_token does not exist
                return []
            return [[Settings.str_to_datetime(self.file_read(path, "timestamp")), self.file_read(path, "_log")]]

        elif blueprint_token is not None:
            pattern = "{}*/blueprint_token".format(Settings.offline_log)
            token_file_paths = ["/".join(path.split('/')[:-1]) for path in glob.glob(pattern) if
                                self.file_read(path) == str(blueprint_token)]
            return [[Settings.str_to_datetime(self.file_read(path, "timestamp")), self.file_read(path, "_log")] for path
                    in token_file_paths]

        elif session_token is not None:
            path = "{}{}".format(Settings.offline_log, session_token)
            try:
                return [[Settings.str_to_datetime(self.file_read(path, "timestamp")), self.file_read(path, "_log")]]
            except FileNotFoundError:
                # session_token does not exist
                return []
        else:
            return []

    def get_last_deployment_data(self, blueprint_token, timestamp: str = None, version_id: int = None):
        """
        Returns last deployment data.
        - if timestamp not None -> retrieves by blueprint_token and timestamp
        - if timestamp None and version_id not None -> retrieves by blueprint_token and version_id
        - if both None -> retrieves just by blueprint_token
        In case of no results returns None
        """

        if timestamp is not None:
            path = "{}{}/{}".format(Settings.offline_blueprints, blueprint_token, Settings.datetime_to_str(timestamp))

        elif version_id is not None:
            pattern = "{}{}/*/version_id".format(Settings.offline_blueprints, blueprint_token)
            try:
                path = ["/".join(path.split('/')[:-1]) for path in glob.glob(pattern) if
                        self.file_read(path) == str(version_id)][0]
            except IndexError:
                return None, None
        else:
            pattern = "{}{}/*/version_time".format(Settings.offline_blueprints, blueprint_token)
            timestamps = [Settings.str_to_datetime(path.split('/')[-2]) for path in glob.glob(pattern)]
            try:
                path = "{}{}/{}".format(Settings.offline_blueprints, blueprint_token,
                                        Settings.datetime_to_str(max(timestamps)))
            except ValueError:
                # token does not exist
                return None, None
        if not os.path.exists(path):
            return None, None

        # return deployment
        deployment = Deployment(id=self.file_read(path, name="id"),
                                blueprint_token=self.file_read(path, name="blueprint_token"),
                                tosca=File.from_dict(json.loads(self.file_read(path, name="tosca_definition"))),
                                ansible_tree=Directory.from_dict(
                                    json.loads(self.file_read(path, name="ansible_definition"))),
                                timestamp=self.file_read(path, name="version_time"),
                                rc_file=File.from_dict(json.loads(self.file_read(path, name="config_file"))),
                                version_id=self.file_read(path, name="version_id"))
        try:
            last_deployment_data = Directory.from_dict(json.loads(self.file_read(path, name="last_deployment_data")))
        except Exception:
            return deployment, None
        return deployment, last_deployment_data

    # noinspection DuplicatedCode
    def get_revision(self, blueprint_token, timestamp: str = None, version_id: int = None):
        """
        Retrieves blueprint as instance of Deployment class from database.
        - if timestamp not None -> retrieves by blueprint_token and timestamp
        - if timestamp None and version_id not None -> retrieves by blueprint_token and version_id
        - if both None -> retrieves just by blueprint_token, last one
        In case of no results returns None
        """
        if timestamp is not None:
            path = "{}{}/{}".format(Settings.offline_blueprints, blueprint_token, Settings.datetime_to_str(timestamp))

        elif version_id is not None:
            pattern = "{}{}/*/version_id".format(Settings.offline_blueprints, blueprint_token)
            try:
                path = ["/".join(path.split('/')[:-1]) for path in glob.glob(pattern) if
                        self.file_read(path) == str(version_id)][0]
            except IndexError:
                return None
        else:
            pattern = "{}{}/*/version_time".format(Settings.offline_blueprints, blueprint_token)
            timestamps = [Settings.str_to_datetime(path.split('/')[-2]) for path in glob.glob(pattern)]
            try:
                path = "{}{}/{}".format(Settings.offline_blueprints, blueprint_token,
                                        Settings.datetime_to_str(max(timestamps)))
            except ValueError:
                # token does not exist
                return None

        if not os.path.exists(path):
            return None

        # return deployment
        deployment = Deployment(id=self.file_read(path, name="id"),
                                blueprint_token=self.file_read(path, name="blueprint_token"),
                                tosca=File.from_dict(json.loads(self.file_read(path, name="tosca_definition"))),
                                ansible_tree=Directory.from_dict(
                                    json.loads(self.file_read(path, name="ansible_definition"))),
                                timestamp=self.file_read(path, name="version_time"),
                                rc_file=File.from_dict(json.loads(self.file_read(path, name="config_file"))),
                                version_id=self.file_read(path, name="version_id"))
        return deployment

    def delete_blueprint(self, blueprint_token, timestamp: str = None, version_id: int = None):
        """
        Deletes blueprint(s).
        - if timestamp not None -> delete by blueprint_token and timestamp
        - if timestamp None and version_id not None -> delete by blueprint_token and version_id
        - if both None -> delete all blueprint with blueprint_id
        Method returns number of deleted database entries
        """
        try:
            if timestamp is not None:
                path = "{}{}/{}".format(Settings.offline_blueprints, blueprint_token,
                                        Settings.datetime_to_str(timestamp))
                rows_affected = 1

            elif version_id is not None:
                pattern = "{}{}/*/version_id".format(Settings.offline_blueprints, blueprint_token)
                path = ["/".join(path.split('/')[:-1]) for path in glob.glob(pattern) if
                        self.file_read(path) == str(version_id)][0]
                rows_affected = 1
            else:
                path = "{}{}".format(Settings.offline_blueprints, blueprint_token)
                rows_affected = len([path for path in glob.glob("{}/*".format(path)) if os.path.isdir(path)])

            if not os.path.exists(path):
                return 0

            # delete
            shutil.rmtree(path)
            return rows_affected
        except (IndexError, FileNotFoundError):
            return 0

    def last_job(self, blueprint_token, timestamp: datetime = None, version_id: int = None):
        """
        Returns last job.
        - if timestamp not None -> Retrieves last job by blueprint_token and timestamp
        - if timestamp None and version_id not None -> Retrieves last job by blueprint with delete by blueprint_token and version_id
        - if both None -> Checks all entries. Only ne should have last_job field not null, but just in case:
                          1) checks, if any of entries has last_job set to 'deploy'
                          2) checks, if any of entries has last_job set to 'undeploy'
                          3) else, returns None
        In case of no entries, it returns None
        """
        try:
            if timestamp is not None:
                path = "{}{}/{}".format(Settings.offline_blueprints, blueprint_token,
                                        Settings.datetime_to_str(timestamp))
                return self.file_read(path, 'last_job')

            elif version_id is not None:
                pattern = "{}{}/*/version_id".format(Settings.offline_blueprints, blueprint_token)
                path = ["/".join(path.split('/')[:-1]) for path in glob.glob(pattern) if
                        self.file_read(path) == str(version_id)][0]
                return self.file_read(path, 'last_job')
            else:
                pattern = "{}{}/*/last_job".format(Settings.offline_blueprints, blueprint_token)
                my_list = [self.file_read(path) for path in glob.glob(pattern)]
                return 'deploy' if 'deploy' in my_list else ('undeploy' if 'undeploy' in my_list else None)
        except (FileNotFoundError, IndexError):
            return None


class PostgreSQL(Database):
    def __init__(self, settings):
        super().__init__()
        self.db_type = "PostgreSQL"
        self.connection = psycopg2.connect(**settings)
        self.execute("""
                create table if not exists {} (
                blueprint_token varchar (36) not null,
                blueprint_id varchar (36), 
                version_time timestamp default current_timestamp, 
                tosca_definition json not null, 
                ansible_definition json, 
                config_file json,
                version_id int not null,
                last_deployment_data json,
                last_job varchar (10),
                primary key (blueprint_token, version_time)
                );""".format(Settings.blueprints_table))
        self.execute("""
                        create table if not exists {} (
                        id varchar (36),
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

    def check_token_exists(self, token: str):
        dbcur = self.connection.cursor()
        dbcur.execute("select count(*) from {} where blueprint_token=%s".format(Settings.blueprints_table),
                      (str(token),))
        n = dbcur.fetchall()[0][0]
        # print(token, n)
        dbcur.close()
        return n > 0

    def get_max_version_id(self, token: str):
        dbcur = self.connection.cursor()
        dbcur.execute("select max(version_id) from {} where blueprint_token=%s".format(Settings.blueprints_table),
                      (str(token),))
        max_id = dbcur.fetchall()[0][0] or 0
        # print(token, max_id)
        dbcur.close()

        return max_id

    def get_timestamp(self, blueprint_token: str, version_id: int):
        dbcur = self.connection.cursor()
        dbcur.execute(
            "select version_time from {} where blueprint_token=%s and version_id=%s".format(Settings.blueprints_table),
            (str(blueprint_token), str(version_id)))
        timestamp = dbcur.fetchall()[0][0]
        dbcur.close()
        return timestamp

    def remove_last_job_tag(self, blueprint_token: str):

        self.execute("update {} set last_job=null where blueprint_token=%s".format(Settings.blueprints_table),
                     (str(blueprint_token),))

    def add_revision(self, deploy: Deployment, version_id: int):
        rcfile = None

        if deploy.rc_file is not None:
            rcfile = json.dumps(deploy.rc_file.to_dict())
        self.execute(
            "insert into {} (blueprint_token, blueprint_id, tosca_definition, ansible_definition, config_file, "
            "version_id) values (%s, %s, %s, %s, %s, %s);".format(Settings.blueprints_table),
            (str(deploy.blueprint_token), str(deploy.id), json.dumps(deploy.tosca.to_dict()),
             json.dumps(deploy.ansible_tree.to_dict()), rcfile, version_id))

        log.info('added revision to PostgreSQL database')
        return True

    def update_blueprint_data(self, location: str, blueprint_token: str, last_job: str, timestamp: str):

        # just one entry with last_job field is legal
        self.remove_last_job_tag(blueprint_token)

        self.execute(
            "update {} set last_deployment_data = %s, last_job = %s where blueprint_token = %s and version_time = %s;".format(
                Settings.blueprints_table),
            (json.dumps(Directory.read(Path(location)).to_dict()), last_job, blueprint_token, timestamp))

        log.info('Updated deployment data in PostgreSQL database')

    def update_deployment_log(self, _id, blueprint_token: str, _log: str, session_token: str, timestamp: str):

        self.execute(
            "insert into {} (id, blueprint_token, timestamp, session_token, _log) values (%s, %s, %s, %s, %s)"
                .format(Settings.log_table),
            (str(_id), str(blueprint_token), str(timestamp), str(session_token), str(_log)))

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

    def get_last_deployment_data(self, blueprint_token, timestamp: str = None, version_id: int = None):
        dbcur = self.connection.cursor()
        deployment = self.get_revision(blueprint_token, timestamp, version_id)

        if deployment is None:
            # no results
            return None, None

        if timestamp is not None:
            # get by timestamp
            dbcur.execute(
                """select last_deployment_data from {} where blueprint_token = %s and 
                version_time = %s;""".format(Settings.blueprints_table), (blueprint_token, timestamp))
            line = dbcur.fetchone()

        elif version_id is not None:
            # get by version id
            dbcur.execute(
                """select last_deployment_data from {} where blueprint_token = %s and 
                version_id = %s;""".format(Settings.blueprints_table), (blueprint_token, version_id))
            line = dbcur.fetchone()

        else:
            # get last version, that was deployed
            dbcur.execute(
                """select last_deployment_data from {} where blueprint_token = %s and 
                last_job = 'deploy';""".format(Settings.blueprints_table), (blueprint_token,))
            line = dbcur.fetchone()

        if line is None or len(line) == 0:
            # no results
            return None, None

        last_deployment_data = Directory.from_dict(line[0])

        dbcur.close()
        return deployment, last_deployment_data

    def get_revision(self, blueprint_token, timestamp: str = None, version_id: int = None):
        dbcur = self.connection.cursor()

        if timestamp is not None:
            # get by timestamp
            dbcur.execute(
                """select blueprint_id, tosca_definition, ansible_definition, version_time, config_file, version_id
                from {} where blueprint_token = %s and version_time = %s;""".format(Settings.blueprints_table),
                (blueprint_token, timestamp))
            line = dbcur.fetchone()

        elif version_id is not None:
            # get by version id
            dbcur.execute(
                """select blueprint_id, tosca_definition, ansible_definition, version_time, config_file, version_id
                from {} where blueprint_token = %s and version_id = %s;""".format(Settings.blueprints_table),
                (blueprint_token, version_id))
            line = dbcur.fetchone()

        else:
            # get last version
            dbcur.execute(
                """select blueprint_id, tosca_definition, ansible_definition, version_time, config_file, version_id
                from {} where blueprint_token = %s order by version_time desc limit 1;""".format(
                    Settings.blueprints_table),
                (blueprint_token,))
            line = dbcur.fetchone()

        if line is None or len(line) == 0:
            # no results
            return None

        deployment = Deployment(id=line[0], blueprint_token=blueprint_token,
                                tosca=File.from_dict(line[1]), ansible_tree=Directory.from_dict(line[2]),
                                timestamp=Settings.datetime_to_str(line[3]),
                                rc_file=File.from_dict(line[4]),
                                version_id=line[5])

        dbcur.close()
        return deployment

    def delete_blueprint(self, blueprint_token: str, timestamp: str = None, version_id: int = None):
        dbcur = self.connection.cursor()

        if timestamp is not None:
            # delete by timestamp
            dbcur.execute(
                """with a as (delete from {} where blueprint_token = %s and version_time = %s returning 1) select count( 
                * ) from a;""".format(Settings.blueprints_table),
                (blueprint_token, timestamp))
            rows_affected = dbcur.fetchall()[0][0]

        elif version_id is not None:
            # delete by version id
            dbcur.execute(
                """with a as (delete from {} where blueprint_token = %s and version_id = %s returning 1) select count( 
                * ) from a;""".format(Settings.blueprints_table),
                (blueprint_token, version_id))
            rows_affected = dbcur.fetchall()[0][0]

        else:
            # delete all blueprints with blueprint_token
            dbcur.execute(
                """with a as (delete from {} where blueprint_token = %s returning 1) select count( * ) from a;""".format(
                    Settings.blueprints_table),
                (blueprint_token,))
            rows_affected = dbcur.fetchall()[0][0]

        dbcur.close()
        self.connection.commit()
        log.info('deleted blueprint(s) from PostgreSQL database')
        return rows_affected

    def last_job(self, blueprint_token, timestamp: datetime = None, version_id: int = None):

        database_cursor = self.connection.cursor()

        if timestamp is not None:
            # check by timestamp
            database_cursor.execute(
                """select last_job from {} where blueprint_token = %s and version_time = %s;""".format(
                    Settings.blueprints_table),
                (blueprint_token, timestamp))
            line = database_cursor.fetchall()

        elif version_id is not None:
            # check by version id
            database_cursor.execute(
                """select last_job from {} where blueprint_token = %s and version_id = %s;""".format(
                    Settings.blueprints_table),
                (blueprint_token, version_id))
            line = database_cursor.fetchall()

        else:
            # check all versions
            database_cursor.execute(
                """select last_job from {} where blueprint_token = %s;""".format(
                    Settings.blueprints_table),
                (blueprint_token,))
            line = database_cursor.fetchall()
            my_list = [a[0] for a in line]

            return 'deploy' if 'deploy' in my_list else ('undeploy' if 'undeploy' in my_list else None)

        try:
            last_job_value = line[0][0]
            return last_job_value
        except IndexError:
            return None

    def exists(self, tablename):
        dbcur = self.connection.cursor()
        dbcur.execute("select to_regclass('public.%s')", (tablename,))
        if dbcur.fetchone()[0] == Settings.blueprints_table:
            dbcur.close()
            return True
        dbcur.close()
        return False


def generate(deployment: Deployment, location: str):
    id_file = File(name="id", content=str(deployment.id))
    id_file.write(location + "/")
    token_file = File(name="blueprint_token", content=str(deployment.blueprint_token))
    token_file.write(location + "/")
    deployment.tosca.write(location + "/")
    deployment.ansible_tree.write(location + "/")
    # deployment.rc_file.write(location + "/")
    # hardcoded openrc file, will fix in future version
    generic_rc_file().write(location + "/")


def generate_data(deployment: Deployment, session_token: uuid):
    td = Settings.deployment_data + "{}".format(session_token)
    if os.path.exists(td):
        shutil.rmtree(td)
    os.mkdir(td)
    generate(deployment, td)
    return td


def regenerate(folder: Directory, session_token: uuid):
    td = "{}/{}/".format(Settings.deployment_data, session_token)
    if os.path.exists(td):
        shutil.rmtree(td)
    os.mkdir(td)
    folder.name = str(session_token)
    folder.write(Settings.deployment_data)
    return td


def cleanup(_id: str):
    td = Settings.deployment_data + "{}".format(_id)
    if os.path.exists(td):
        shutil.rmtree(td)
    return td


def configure_ssh_keys():
    keys = glob.glob("{}*xOpera*".format(Settings.ssh_keys_location))
    if len(keys) != 2:
        log.error(
            "Expected exactly 2 keys (public and private) with xOpera substring in name, found {}".format(len(keys)))
        return
    try:
        private_key = [key for key in keys if ".pubk" not in key][0]
        public_key = [key for key in keys if ".pubk" in key][0]
    except IndexError:
        log.error(
            'Wrong file extention. Public key should have ".pubk" and private key should have ".pk" or no extension at all')
        return
    public_key_check = private_key.replace(".pk", "") + ".pubk"
    if public_key != public_key_check:
        log.error(
            'No matching private and public key pair. Public key should have ".pubk" and private key should have ".pk" or no extension at all')
        return

    private_key_new, public_key_new = private_key, public_key
    ip = re.search("\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", private_key)
    if ip is not None:
        ip = ip.group()
        ip_hyphens = ip.replace(".", "-")
        private_key_new, public_key_new = private_key.replace(ip, ip_hyphens), public_key.replace(ip, ip_hyphens)

    private_key_new = private_key_new.replace(".pk", "")
    os.rename(private_key, private_key_new)
    os.rename(public_key, public_key_new)
    uid = pwd.getpwnam('root').pw_uid
    gid = grp.getgrnam('root').gr_gid
    os.chown(private_key_new, uid, gid)
    os.chmod(private_key_new, 0o400)

    config = "ConnectTimeout 5\n" \
             f"IdentityFile {private_key_new}\n" \
             "UserKnownHostsFile=/dev/null\n" \
             "StrictHostKeyChecking=no"
    config_file = File("config", config)
    config_file.write(Settings.ssh_keys_location)

    key_pair = private_key_new.split("/")[-1]
    Settings.key_pair = key_pair
    log.info("key '{}' added".format(Settings.key_pair))


def clean_deployment_data():
    shutil.rmtree(Settings.deployment_data, ignore_errors=True)
    os.mkdir(Settings.deployment_data)
    with open(Settings.deployment_data + ".gitignore", "w") as file:
        file.write("*")


def generic_rc_file():
    path = f"{Settings.implementation_dir}/settings/openrc.sh"
    file = File.read(Path(path))
    return file


def replace_username_and_password(rc_file_path: str, username, password):

    openrc_file = open(rc_file_path, 'r')
    file_lines = openrc_file.readlines()
    openrc_file.close()

    password_lines = [(i, line) for i, line in enumerate(file_lines) if "OS_PASSWORD" in line]
    to_be_removed = password_lines[0]
    to_be_replaced = password_lines[1]
    replacement = f'export OS_PASSWORD="{password}"\n'
    file_lines[to_be_replaced[0]] = replacement
    del file_lines[to_be_removed[0]]

    username_lines = [(i, line) for i, line in enumerate(file_lines) if "OS_USERNAME" in line]
    to_be_replaced = username_lines[0]
    replacement = f'export OS_USERNAME="{username}"\n'
    file_lines[to_be_replaced[0]] = replacement

    echo_lines = [(i, line) for i, line in enumerate(file_lines) if 'echo "Please enter' in line]
    del file_lines[echo_lines[0][0]]

    openrc_file = open(rc_file_path, 'w')
    openrc_file.write("".join(file_lines))
    openrc_file.close()


def validate_blueprint_name(name: str):
    response = _validate_dns_format(name)
    return response is not None, response


def validate_tosca(deployment: Deployment):
    tmp_location = f"/tmp/xopera/{uuid.uuid4()}"
    Path(tmp_location).mkdir(parents=True, exist_ok=True)
    try:
        TOSCA_path = deployment.tosca.write(tmp_location + "/")
        # print(TOSCA_path)
        shutil.rmtree(tmp_location, ignore_errors=True)
    except AttributeError:
        return True, "Tosca is empty"
    # requests.post()
    return False, "tosca_validation not implemented"
