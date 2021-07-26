import datetime
import json
import logging
import uuid

import psycopg2
from assertpy import assert_that

from opera.api.openapi.models import BlueprintVersion, InvocationState, OperationType, Deployment, GitLog, Invocation
from opera.api.openapi.models.base_model_ import Model as BaseModel
from opera.api.service.sqldb_service import PostgreSQL
from opera.api.util import timestamp_util


# PostgreSQL tests

def obj_to_json(obj: BaseModel):
    _dict = obj.to_dict()
    return {key: (timestamp_util.datetime_to_str(value) if isinstance(value, datetime.datetime) else value)
            for key, value in _dict.items()}


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
        if isinstance(command, psycopg2.sql.Composed):
            cls.command = command._wrapped.__repr__()
        else:
            cls.command = command
        cls.replacements = replacements

    @classmethod
    def fetchone(cls):
        return None

    @classmethod
    def fetchall(cls):
        return []

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
        if "select version_id,job" in str(cls.command):
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


class GetInputsCursor(NoneCursor):
    @classmethod
    def fetchone(cls):
        return [json.dumps(TestBlueprintMeta.inputs)]


class GetStringCursor(NoneCursor):
    @classmethod
    def fetchone(cls):
        return [""]


class GetBlueprintMetaCursor(NoneCursor):
    @classmethod
    def fetchone(cls):
        if "select blueprint_id, blueprint_name" in cls.command:
            return 'a', 'name'

        if "select blueprint_id, project_domain" in cls.command:
            return 'a', 'project_domain'

        if "select blueprint_id, version_id, blueprint_name, aadm_id" in cls.command:
            blueprint_meta = TestBlueprintMeta.blueprint_meta
            return [blueprint_meta.blueprint_id, blueprint_meta.version_id, blueprint_meta.blueprint_name,
                    blueprint_meta.aadm_id, blueprint_meta.username, blueprint_meta.project_domain,
                    blueprint_meta.url, blueprint_meta.timestamp, blueprint_meta.commit_sha]

    @classmethod
    def fetchall(cls):
        # used to get deployments
        deployment = Deployment.from_dict(TestBlueprintMeta.deployment)
        return [
            [
                deployment.deployment_id, deployment.state, deployment.operation,
                deployment.timestamp, deployment.deployment_label
            ]
        ]


class GetDeploymentsCursor(NoneCursor):

    @classmethod
    def fetchall(cls):
        # used to get deployments
        deployments = [Deployment.from_dict(x) for x in TestBlueprintMeta.deployments]
        return [
            [
                deployment.deployment_id, deployment.state, deployment.operation,
                deployment.timestamp, deployment.deployment_label
            ] for deployment in deployments
        ]


class GetBlueprintCursor(NoneCursor):
    @classmethod
    def fetchall(cls):
        blueprints = [{key: (timestamp_util.str_to_datetime(value) if key == 'timestamp' else value)
                       for key, value in blueprint.items()} for blueprint in TestGetBlueprint.blueprints]

        return [list(x.values()) for x in blueprints]


class GitTransactionDataCursor(NoneCursor):
    @classmethod
    def fetchall(cls):
        git_log = TestGitTransactionData.git_log

        return [
            [
                git_log.blueprint_id, git_log.version_id, git_log.revision_msg, git_log.job,
                git_log.git_backend, git_log.repo_url, git_log.commit_sha, git_log.timestamp
            ]
        ]


class InvocationCursor(NoneCursor):
    @classmethod
    def fetchone(cls):
        if "select timestamp, invocation_id" in cls.command:
            return ['a', TestInvocation.invocation_id]
        if "select timestamp, _log" in cls.command:
            inv = TestInvocation.inv
            return [
                inv.timestamp_submission, json.dumps(inv.to_dict())
            ]

    @classmethod
    def fetchall(cls):
        if "select timestamp, _log" in cls.command:
            inv = TestInvocation.inv
            return [
                [
                    inv.timestamp_submission, json.dumps(inv.to_dict())
                ]
            ]

        if "select deployment_id" in cls.command:
            inv = TestInvocation.inv
            return [
                [
                    inv.deployment_id
                ]
            ]

        if "select version_id" in cls.command:
            inv = TestInvocation.inv
            return [
                [
                    inv.version_id
                ]
            ]


class OperaSessionDataCursor(NoneCursor):
    @classmethod
    def fetchone(cls):
        session_data = TestSessionData.session_data
        return [
            session_data['deployment_id'],
            timestamp_util.str_to_datetime(session_data['timestamp']),
            json.dumps(session_data['tree'])
        ]


class TestVersionExists:

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


class TestBlueprintMeta:

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
        monkeypatch.setattr(db.connection, 'cursor', GetBlueprintMetaCursor)

        # test
        blueprint_meta: BlueprintVersion = self.blueprint_meta
        assert_that(BlueprintVersion.from_dict(db.get_blueprint_meta(blueprint_meta.blueprint_id))).is_equal_to(
            blueprint_meta)

    def test_get_blueprint_meta_version(self, mocker, monkeypatch, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', GetBlueprintMetaCursor)

        # test
        blueprint_meta: BlueprintVersion = self.blueprint_meta
        assert_that(BlueprintVersion.from_dict(db.get_blueprint_meta(
            blueprint_id=blueprint_meta.blueprint_id, version_id=blueprint_meta.version_id
        ))).is_equal_to(
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
        monkeypatch.setattr(db.connection, 'cursor', GetBlueprintMetaCursor)

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
        monkeypatch.setattr(db.connection, 'cursor', GetBlueprintMetaCursor)

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

    inputs = {
        'foo': 'bar',
        'foo2': 'bar2'
    }

    def test_get_inputs(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', GetInputsCursor)

        deployment_id = uuid.uuid4()
        assert_that(db.get_inputs(deployment_id=deployment_id)).is_equal_to(self.inputs)

    def test_get_inputs_missing(self, mocker):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})

        deployment_id = uuid.uuid4()
        assert_that(db.get_inputs(deployment_id=deployment_id)).is_none()

    def test_get_inputs_exception(self, mocker, monkeypatch):
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', GetStringCursor)

        deployment_id = uuid.uuid4()
        assert_that(db.get_inputs(deployment_id=deployment_id)).is_none()

    deployment = {
        'deployment_id': str(uuid.uuid4()),
        'state': InvocationState.SUCCESS,
        'operation': OperationType.DEPLOY_CONTINUE,
        'timestamp': timestamp_util.datetime_now_to_string(),
        'last_inputs': None,
        'deployment_label': 'label'
    }

    def test_get_deployments(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', GetBlueprintMetaCursor)

        blueprint_id = uuid.uuid4()
        assert_that(db.get_deployments_for_blueprint(blueprint_id, active=False)).is_equal_to([self.deployment])

    deployments = [
        {
            "deployment_id": "71ceef1c-f169-4204-b180-e95948329108",
            "operation": OperationType.DEPLOY_FRESH,
            "state":  InvocationState.SUCCESS,
            "timestamp": timestamp_util.datetime_now_to_string(),
            'last_inputs': None,
            'deployment_label': 'label'
        },
        {
            "deployment_id": "30e143c9-e614-41bc-9b22-47c588f394e3",
            "operation": OperationType.UNDEPLOY,
            "state":  InvocationState.SUCCESS,
            "timestamp": timestamp_util.datetime_to_str(datetime.datetime.fromtimestamp(1)),
            'last_inputs': None,
            'deployment_label': 'label'
        }
    ]

    def test_get_active_deployments(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', GetDeploymentsCursor)

        blueprint_id = uuid.uuid4()
        assert_that(db.get_deployments_for_blueprint(blueprint_id, active=False)).is_equal_to(self.deployments)
        assert_that(db.get_deployments_for_blueprint(blueprint_id, active=True)).is_equal_to([self.deployments[0]])


class TestGetBlueprint:
    blueprints = [{
        "blueprint_id": '91df79b1-d78b-4cac-ae24-4edaf49c5030',
        "blueprint_name": 'TestBlueprint',
        "aadm_id": 'aadm_id',
        "username": 'mihaTrajbaric',
        "project_domain": 'SODALITE',
        "timestamp": timestamp_util.datetime_now_to_string()
    }]

    def test_user(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', GetBlueprintCursor)

        # testing
        assert db.get_blueprints_by_user_or_project(username='username') == self.blueprints

    def test_project_domain(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', GetBlueprintCursor)

        # testing
        assert db.get_blueprints_by_user_or_project(project_domain='project_domain') == self.blueprints

    def test_user_and_project_domain(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', GetBlueprintCursor)

        # testing
        assert db.get_blueprints_by_user_or_project(username='username',
                                                    project_domain='project_domain') == self.blueprints


class TestGitTransactionData:
    git_log = GitLog.from_dict(
        {
            'blueprint_id': uuid.uuid4(),
            'version_id': 'v1.0',
            'revision_msg': 'revision_msg',
            'job': 'update',
            'git_backend': 'gitlab',
            'repo_url': 'https://gitlab.com/sodalite.xopera/gitDB_546c27fb-faa0-4b51-a241-22d9d1e6faf2',
            'commit_sha': '4eb6309f062eb9d62a916c85d12824a73057cd7d',
            'timestamp': timestamp_util.datetime_now_to_string()
        }
    )

    def test_get(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', GitTransactionDataCursor)

        # testing
        assert_that(db.get_git_transaction_data(
            blueprint_id=self.git_log.blueprint_id)
        ).is_equal_to([obj_to_json(self.git_log)])

    def test_save_success(self, mocker, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})

        # testing
        assert_that(db.save_git_transaction_data(
            blueprint_id=self.git_log.blueprint_id,
            version_id=self.git_log.version_id,
            revision_msg=self.git_log.revision_msg,
            job=self.git_log.job,
            git_backend=self.git_log.git_backend,
            repo_url=self.git_log.repo_url,
            commit_sha=self.git_log.commit_sha
        )).is_true()

        assert_that(caplog.text).contains("Updated git log", str(self.git_log.blueprint_id),
                                          str(self.git_log.version_id))

    def test_save_fail(self, mocker, monkeypatch, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', PsycopgErrorCursor)

        # testing
        assert_that(db.save_git_transaction_data(
            blueprint_id=self.git_log.blueprint_id,
            version_id=self.git_log.version_id,
            revision_msg=self.git_log.revision_msg,
            job=self.git_log.job,
            git_backend=self.git_log.git_backend,
            repo_url=self.git_log.repo_url,
            commit_sha=self.git_log.commit_sha
        )).is_false()

        assert_that(caplog.text).contains(
            "Failed to update git log",
            str(self.git_log.blueprint_id),
            str(self.git_log.version_id)
        )


class TestInvocation:
    inv = Invocation(
        deployment_id=str(uuid.uuid4()),
        deployment_label='label',
        timestamp_submission=timestamp_util.datetime_now_to_string(),
        blueprint_id=str(uuid.uuid4()),
        version_id='v1.0',
        state=InvocationState.SUCCESS,
        operation=OperationType.DEPLOY_CONTINUE
    )
    invocation_id = str(uuid.uuid4())
    _log = 'deployment log'

    def test_get_last_invocation_id_fail(self, mocker):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})

        assert_that(db.get_last_invocation_id(uuid.uuid4())).is_none()

    def test_get_last_invocation_id_success(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', InvocationCursor)

        assert_that(db.get_last_invocation_id(uuid.uuid4())).is_equal_to(self.invocation_id)

    def test_get_deployment_history(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', InvocationCursor)

        assert_that([obj_to_json(x) for x in db.get_deployment_history(uuid.uuid4())]).is_equal_to([self.inv.to_dict()])

    def test_get_last_completed_invocation(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', InvocationCursor)

        assert_that(obj_to_json(db.get_last_completed_invocation(uuid.uuid4()))).is_equal_to(self.inv.to_dict())

    def test_get_last_completed_invocation_fail(self, mocker):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})

        assert_that(db.get_last_completed_invocation(uuid.uuid4())).is_none()

    def test_get_deployment_status(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', InvocationCursor)

        assert_that(obj_to_json(db.get_deployment_status(uuid.uuid4()))).is_equal_to(self.inv.to_dict())

    def test_get_deployment_status_fail(self, mocker):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})

        assert_that(db.get_deployment_status(uuid.uuid4())).is_none()

    def test_update_deployment_log_success(self, mocker, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})

        assert_that(db.update_deployment_log(self.invocation_id, self.inv)).is_true()

        assert_that(caplog.text).contains("Updated deployment log",
                                          str(self.inv.deployment_id),
                                          str(self.invocation_id))

    def test_update_deployment_log_fail(self, mocker, monkeypatch, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', PsycopgErrorCursor)

        assert_that(db.update_deployment_log(self.invocation_id, self.inv)).is_false()

        assert_that(caplog.text).contains("Failed to update deployment log",
                                          str(self.inv.deployment_id),
                                          str(self.invocation_id))

    def test_get_deployment_ids(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', InvocationCursor)

        assert_that(db.get_deployment_ids(uuid.uuid4())).is_equal_to([self.inv.deployment_id])

    def test_get_deployment_ids_version(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', InvocationCursor)

        assert_that(db.get_deployment_ids(uuid.uuid4(), 'v1.0')).is_equal_to([self.inv.deployment_id])

    def test_blueprint_used_in_deployment_no_deployment_ids(self, mocker):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        mocker.patch('opera.api.service.sqldb_service.Database.get_deployment_ids', return_value=None)
        db = PostgreSQL({})

        assert_that(db.blueprint_used_in_deployment(uuid.uuid4(), 'v1.0')).is_false()

    def test_blueprint_used_in_deployment(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', InvocationCursor)

        assert_that(db.blueprint_used_in_deployment(uuid.uuid4())).is_true()

    def test_blueprint_used_in_deployment_version(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', InvocationCursor)

        assert_that(db.blueprint_used_in_deployment(uuid.uuid4(), self.inv.version_id)).is_true()

    def test_blueprint_used_in_deployment_version_no_ids(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', InvocationCursor)

        assert_that(db.blueprint_used_in_deployment(uuid.uuid4(), 'blah')).is_false()

    def test_delete_deployment(self, mocker, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})

        deployment_id = uuid.uuid4()
        assert_that(db.delete_deployment(deployment_id)).is_true()
        assert_that(caplog.text).contains("Deleted deployment", str(deployment_id))

    def test_delete_deployment_fail(self, mocker, monkeypatch, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', PsycopgErrorCursor)

        deployment_id = uuid.uuid4()
        assert_that(db.delete_deployment(deployment_id)).is_false()
        assert_that(caplog.text).contains("Failed to delete deployment", str(deployment_id))


class TestSessionData:
    session_data = {
        'deployment_id': uuid.uuid4(),
        'timestamp': timestamp_util.datetime_now_to_string(),
        'tree': {}
    }

    def test_save_success(self, mocker, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        deployment_id = uuid.uuid4()
        assert_that(db.save_opera_session_data(deployment_id, {})).is_true()
        assert_that(caplog.text).contains("Updated dot_opera_data", str(deployment_id))

    def test_save_fail(self, mocker, monkeypatch, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', PsycopgErrorCursor)
        deployment_id = uuid.uuid4()
        assert_that(db.save_opera_session_data(deployment_id, {})).is_false()
        assert_that(caplog.text).contains("Failed to update dot_opera_data", str(deployment_id))

    def test_get_opera_session_data(self, mocker, monkeypatch):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', OperaSessionDataCursor)

        assert_that(db.get_opera_session_data(self.session_data['deployment_id'])).is_equal_to(self.session_data)

    def test_get_opera_session_data_fail(self, mocker):
        # test set up
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})

        assert_that(db.get_opera_session_data(self.session_data['deployment_id'])).is_none()

    def test_delete_opera_session_data(self, mocker, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})

        deployment_id = uuid.uuid4()
        assert_that(db.delete_opera_session_data(deployment_id)).is_true()
        assert_that(caplog.text).contains("Deleted opera_session_data", str(deployment_id))

    def test_delete_opera_session_data_fail(self, mocker, monkeypatch, caplog):
        # test set up
        caplog.set_level(logging.DEBUG, logger="opera.api.service.sqldb_service")
        mocker.patch('psycopg2.connect', new=FakePostgres)
        db = PostgreSQL({})
        monkeypatch.setattr(db.connection, 'cursor', PsycopgErrorCursor)

        deployment_id = uuid.uuid4()
        assert_that(db.delete_opera_session_data(deployment_id)).is_false()
        assert_that(caplog.text).contains("Failed to delete opera_session_data", str(deployment_id))
