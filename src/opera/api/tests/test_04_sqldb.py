import datetime
import logging
import uuid

import psycopg2
from assertpy import assert_that

from opera.api.openapi.models import BlueprintVersion
from opera.api.service.sqldb_service import PostgreSQL
from opera.api.util import timestamp_util


# PostgreSQL tests


class FakePostgres:
    def __init__(self, **kwargs):
        pass

    @staticmethod
    def cursor():
        return NoneCursor()

    def commit(self):
        pass


# Class to be redefined with custom fetchone or fetchall function
class NoneCursor:
    command = ""
    replacements = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @classmethod
    def execute(cls, command, replacements=None):
        cls.command = command
        cls.replacements = replacements

    @classmethod
    def fetchone(cls):
        return None

    @classmethod
    def fetchall(cls):
        return None

    @classmethod
    def close(cls):
        pass

    @classmethod
    def get_command(cls):
        """This method does not exist in real Cursor object, for testing purposes only"""
        return cls.command

    @classmethod
    def get_replacements(cls):
        """This method does not exist in real Cursor object, for testing purposes only"""
        return cls.replacements


class PsycopgErrorCursor(NoneCursor):

    @classmethod
    def execute(cls, command, replacements=None):
        if command != "ROLLBACK":
            raise psycopg2.Error
        return None


class BlueprintDeletedCursor(NoneCursor):

    @classmethod
    def fetchone(cls):

        # last db entry for this blueprint is delete transaction for entire blueprint (version_id = None)
        return None, "delete"


class VersionNeverExistedCursor(NoneCursor):

    @classmethod
    def fetchone(cls):
        # Blueprint exist and has not been deleted
        if "select version_id,job" in cls.command:
            return 'v4.0', 'update'
        # version not found
        return None


class VersionDeletedCursor(NoneCursor):

    @classmethod
    def fetchone(cls):
        # Blueprint exist and has not been deleted
        if "select version_id,job" in cls.command:
            return 'v4.0', 'update'

        # job in last db entry for this blueprint version is delete
        return ["delete"]


class VersionExistsCursor(NoneCursor):

    @classmethod
    def fetchone(cls):
        # Blueprint exist and has not been deleted
        if "select version_id,job" in cls.command:
            return 'a', 'update'

        # job in last db entry for this blueprint version is not delete
        return ["update"]


class GetBlueprintMeta(NoneCursor):
    @classmethod
    def fetchone(cls):
        if "select blueprint_id, blueprint_name" in cls.command:
            return 'a', 'name'

        if "select blueprint_id, project_domain" in cls.command:
            return 'a', 'project_domain'

        if "select blueprint_id, version_id, blueprint_name, aadm_id" in cls.command:
            blueprint_meta = TestPostgreSQLBlueprintMeta.blueprint_meta
            return [blueprint_meta.blueprint_id, blueprint_meta.version_id, blueprint_meta.blueprint_name,
                    blueprint_meta.aadm_id, blueprint_meta.username, blueprint_meta.project_domain,
                    blueprint_meta.url, blueprint_meta.timestamp, blueprint_meta.commit_sha]

    @classmethod
    def fetchall(cls):
        # used to get deployments
        return []


class GetBlueprintCursor(NoneCursor):
    @classmethod
    def fetchall(cls):
        blueprints = [{key: (timestamp_util.str_to_datetime(value) if key == 'timestamp' else value)
                       for key, value in blueprint.items()} for blueprint in TestGetBlueprint.blueprints]

        return [list(x.values()) for x in blueprints]


class TestPostgreSQLVersionExists:

    def test_blueprint_has_never_existed(self, mocker, caplog):
        # Test preparation
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})

        # Testing
        blueprint_id = uuid.uuid4()
        version_id = 'v4.0'
        exists = db.version_exists(blueprint_id, version_id)
        assert_that(exists).is_false()
        assert_that(caplog.text).contains(f"Blueprint {blueprint_id} has never existed")

    def test_blueprint_deleted(self, mocker, monkeypatch, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', BlueprintDeletedCursor)

        # Testing
        blueprint_id = uuid.uuid4()
        version_id = 'v4.0'
        exists = db.version_exists(blueprint_id, version_id)
        assert_that(exists).is_false()
        assert_that(caplog.text).contains(f"Entire blueprint {blueprint_id} has been deleted, does not exist any more")

    def test_version_has_never_existed(self, mocker, monkeypatch, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', VersionNeverExistedCursor)

        # testing
        blueprint_id = uuid.uuid4()
        version_id = 'v4.0'
        exists = db.version_exists(blueprint_id, version_id)
        assert_that(exists).is_false()
        assert_that(caplog.text).contains(f"Blueprint-version {blueprint_id}/{version_id} has never existed")

    def test_version_deleted(self, mocker, monkeypatch, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', VersionDeletedCursor)

        # testing
        blueprint_id = uuid.uuid4()
        version_id = 'v4.0'
        exists = db.version_exists(blueprint_id, version_id)
        assert_that(exists).is_false()
        assert_that(caplog.text).contains(f"Blueprint-version {blueprint_id}/{version_id} has been deleted, does not "
                                          f"exist any more")

    def test_version_exists(self, mocker, monkeypatch, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', VersionExistsCursor)

        # testing
        blueprint_id = uuid.uuid4()
        version_id = 'v4.0'
        exists = db.version_exists(blueprint_id, version_id)
        assert_that(exists).is_true()
        assert_that(caplog.text).is_empty()


class TestPostgreSQLBlueprintMeta:

    def test_save_blueprint_meta(self, mocker, monkeypatch, caplog, generic_blueprint_meta):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', NoneCursor)

        # testing
        blueprint_meta: BlueprintVersion = generic_blueprint_meta
        db.save_blueprint_meta(blueprint_meta)
        replacements = db.connection.cursor().get_replacements()
        assert_that(replacements).contains_only(*[
            str(blueprint_meta.blueprint_id),
            blueprint_meta.version_id,
            blueprint_meta.blueprint_name,
            blueprint_meta.aadm_id,
            blueprint_meta.username,
            blueprint_meta.project_domain,
            blueprint_meta.url,
            blueprint_meta.commit_sha
        ])
        assert_that(caplog.text).contains("Updated blueprint meta", str(blueprint_meta.blueprint_id))

    def test_save_blueprint_meta_exception(self, mocker, monkeypatch, caplog, generic_blueprint_meta):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', PsycopgErrorCursor)

        blueprint_meta: BlueprintVersion = generic_blueprint_meta
        db.save_blueprint_meta(blueprint_meta)

        assert_that(caplog.text).contains("Fail to update blueprint meta", str(blueprint_meta.blueprint_id))

    blueprint_meta = BlueprintVersion(
        blueprint_id=str(uuid.uuid4()),
        version_id='v1.0',
        blueprint_name='a',
        aadm_id=str(uuid.uuid4()),
        username='username',
        project_domain='some_domain',
        url='www.google.com',
        timestamp=datetime.datetime.now(),
        commit_sha='d955c23e2771639202f52db9d40c633f6f732e55'
    )

    def test_get_blueprint_meta(self, mocker, monkeypatch, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', GetBlueprintMeta)

        # test
        blueprint_meta: BlueprintVersion = self.blueprint_meta
        assert_that(BlueprintVersion.from_dict(db.get_blueprint_meta(blueprint_meta.blueprint_id))).is_equal_to(
            blueprint_meta)

    def test_get_project_blueprint_meta_missing(self, mocker, caplog, generic_blueprint_meta):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})

        # test
        blueprint_meta: BlueprintVersion = generic_blueprint_meta
        assert db.get_blueprint_meta(blueprint_meta.blueprint_id) is None

    def test_get_project_domain(self, mocker, monkeypatch, caplog, generic_blueprint_meta):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', GetBlueprintMeta)

        # test
        blueprint_meta: BlueprintVersion = generic_blueprint_meta
        assert db.get_project_domain(blueprint_meta.blueprint_id) == blueprint_meta.project_domain

    def test_get_project_domain_missing(self, mocker, caplog, generic_blueprint_meta):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})

        # test
        blueprint_meta: BlueprintVersion = generic_blueprint_meta
        assert db.get_project_domain(blueprint_meta.blueprint_id) is None

    def test_get_blueprint_name(self, mocker, monkeypatch, caplog, generic_blueprint_meta):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', GetBlueprintMeta)

        # test
        blueprint_meta: BlueprintVersion = generic_blueprint_meta
        assert db.get_blueprint_name(blueprint_meta.blueprint_id) == blueprint_meta.blueprint_name

    def test_save_blueprint_name(self, mocker, monkeypatch, caplog, generic_blueprint_meta):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', NoneCursor)

        # test
        blueprint_meta: BlueprintVersion = generic_blueprint_meta
        new_name = 'new_name'
        db.update_blueprint_name(blueprint_meta.blueprint_id, new_name)
        command = db.connection.cursor().get_command()
        assert_that(command).contains(blueprint_meta.blueprint_name, new_name)
        assert_that(caplog.text).contains("Updated blueprint name", new_name, str(blueprint_meta.blueprint_id))

    def test_save_blueprint_name_exception(self, mocker, monkeypatch, caplog, generic_blueprint_meta):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', PsycopgErrorCursor)

        blueprint_meta: BlueprintVersion = generic_blueprint_meta
        new_name = 'new_name'
        db.update_blueprint_name(blueprint_meta.blueprint_id, new_name)

        assert_that(caplog.text).contains("Fail to update blueprint name", new_name, str(blueprint_meta.blueprint_id))

    def test_get_blueprint_name_missing(self, mocker, caplog, generic_blueprint_meta):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})

        # test
        blueprint_meta: BlueprintVersion = generic_blueprint_meta
        assert db.get_blueprint_name(blueprint_meta.blueprint_id) is None

    def test_delete_blueprint_meta(self, mocker, monkeypatch, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', NoneCursor)

        # testing
        blueprint_id = uuid.uuid4()
        assert db.delete_blueprint_meta(blueprint_id)
        command = db.connection.cursor().get_command()
        assert_that(command).contains("delete")
        assert_that(caplog.text).contains("Deleted blueprint meta", str(blueprint_id))

    def test_delete_blueprint_version_meta(self, mocker, monkeypatch, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', NoneCursor)

        # testing
        blueprint_id = uuid.uuid4()
        version_id = 'v1.0'
        assert db.delete_blueprint_meta(blueprint_id, version_id)
        command = db.connection.cursor().get_command()
        assert_that(command).contains("delete")
        assert_that(caplog.text).contains("Deleted blueprint meta", str(blueprint_id), str(version_id))

    def test_delete_blueprint_meta_fail(self, mocker, monkeypatch, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', PsycopgErrorCursor)

        # testing
        blueprint_id = uuid.uuid4()
        assert not db.delete_blueprint_meta(blueprint_id)
        assert_that(caplog.text).contains("Failed to delete blueprint metadata", str(blueprint_id))


class TestGetBlueprint:
    blueprints = [{
            "blueprint_id": '91df79b1-d78b-4cac-ae24-4edaf49c5030',
            "blueprint_name": 'TestBlueprint',
            "aadm_id": 'aadm_id',
            "username": 'mihaTrajbaric',
            "project_domain": 'SODALITE',
            "timestamp": timestamp_util.datetime_now_to_string()
        }]

    def test_success(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', GetBlueprintCursor)

        # testing
        assert db.get_blueprints_by_user_or_project('username', 'project_domain') == self.blueprints

