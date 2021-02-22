import json
import uuid
from pathlib import Path

from assertpy import assert_that

from opera.api.openapi.models import Invocation
from opera.api.service.sqldb_service import OfflineStorage
from opera.api.util import file_util, timestamp_util


class TestDeploymentLog:
    def test_log(self, sql_db: OfflineStorage, generic_invocation: Invocation):
        inv = generic_invocation
        inv.deployment_id = str(uuid.uuid4())

        for i in range(5):
            inv_id = uuid.uuid4()
            inv.version_id = f"v1.{i}"
            inv.timestamp = timestamp_util.datetime_now_to_string()
            sql_db.update_deployment_log(inv_id, inv)
        history = sql_db.get_deployment_history(inv.deployment_id)
        assert len(history) == 5
        for i, inv_temp in enumerate(history):
            assert inv_temp.version_id == f"v1.{i}"
        status = sql_db.get_deployment_status(inv.deployment_id)
        assert status.version_id == 'v1.4'

    def test_last_inv_id(self, sql_db: OfflineStorage, generic_invocation: Invocation):
        # set up
        inv_ids = [uuid.uuid4() for _ in range(5)]
        inv = generic_invocation
        inv.deployment_id = str(uuid.uuid4())
        for inv_id in inv_ids:
            inv.timestamp = timestamp_util.datetime_now_to_string()
            sql_db.update_deployment_log(inv_id, inv)

        # test
        last_id = sql_db.get_last_invocation_id(inv.deployment_id)
        assert uuid.UUID(last_id) == inv_ids[-1]


class TestBlueprintInDeployment:
    def test_get_deployment_ids(self, sql_db: OfflineStorage, generic_invocation):
        # save a couple invocations with same blueprint_id
        blueprint_id = uuid.uuid4()
        deployment_ids = [uuid.uuid4() for i in range(5)]
        for i, deployment_id in enumerate(deployment_ids):
            inv = generic_invocation
            inv.deployment_id = deployment_id
            inv.version_id = f"v{i}.0"
            inv.blueprint_id = blueprint_id
            sql_db.update_deployment_log(uuid.uuid4(), inv)

        # test
        deployment_ids_new = sql_db.get_deployment_ids(blueprint_id)
        assert set(deployment_ids) == set(deployment_ids_new)

    def test_blueprint_in_deployment(self, sql_db: OfflineStorage, generic_invocation):
        # save invocation
        inv = generic_invocation
        inv.deployment_id = uuid.uuid4()
        inv.version_id = "v1.0"
        inv.blueprint_id = uuid.uuid4()
        sql_db.update_deployment_log(uuid.uuid4(), inv)

        # blueprint is part of deployment
        assert_that(sql_db.blueprint_used_in_deployment(inv.blueprint_id)).is_true()

        # random blueprint is not part of deployment
        assert_that(sql_db.blueprint_used_in_deployment(uuid.uuid4())).is_false()

    def test_blueprint_version_in_deployment(self, sql_db: OfflineStorage, generic_invocation):
        # save a couple invocations with same blueprint_id and deployment_id
        blueprint_id = uuid.uuid4()
        deployment_id = uuid.uuid4()
        version_ids = [f"v{i}.0" for i in range(3)]
        for version_id in version_ids:
            inv = generic_invocation
            inv.deployment_id = deployment_id
            inv.version_id = version_id
            inv.blueprint_id = blueprint_id
            inv.timestamp = timestamp_util.datetime_now_to_string()
            sql_db.update_deployment_log(uuid.uuid4(), inv)

        # Last version is part of deployment, other two are not
        assert_that(sql_db.blueprint_used_in_deployment(blueprint_id, version_ids[-1])).is_true()
        assert_that(sql_db.blueprint_used_in_deployment(blueprint_id, version_ids[0])).is_false()
        assert_that(sql_db.blueprint_used_in_deployment(blueprint_id, version_ids[1])).is_false()


class TestSessionData:

    def test_save_session_data(self, sql_db: OfflineStorage, generic_dir: Path):
        deployment_id = uuid.uuid4()
        sql_db.save_opera_session_data(deployment_id, file_util.dir_to_json(generic_dir))
        assert sql_db.opera_session_data_path.exists()
        data_path = sql_db.opera_session_data_path / str(deployment_id)
        assert data_path.is_file()
        data = json.loads(data_path.read_text())
        assert_that(data).contains_only('tree', 'deployment_id', 'timestamp')
        assert uuid.UUID(data['deployment_id']) == deployment_id

    def test_get_session_data_missing(self, sql_db: OfflineStorage):
        data = sql_db.get_opera_session_data('foo')
        assert_that(data).is_none()

    def test_get_session_data(self, sql_db: OfflineStorage, generic_dir: Path):
        deployment_id = uuid.uuid4()
        sql_db.save_opera_session_data(deployment_id, file_util.dir_to_json(generic_dir))
        data = sql_db.get_opera_session_data(deployment_id)
        assert_that(data).contains_only('tree', 'deployment_id', 'timestamp')
        assert deployment_id == uuid.UUID(data['deployment_id'])
        assert_that(data['tree']).contains_only("0-new.txt", "1-new.txt", "2-new.txt", "3-new.txt")

    def test_delete_session_data(self, sql_db: OfflineStorage, generic_dir: Path):
        # set up test
        deployment_id = uuid.uuid4()
        sql_db.save_opera_session_data(deployment_id, file_util.dir_to_json(generic_dir))
        assert (sql_db.opera_session_data_path / str(deployment_id)).exists()

        # test function
        sql_db.delete_opera_session_data(deployment_id)
        assert not (sql_db.opera_session_data_path / str(deployment_id)).exists()
