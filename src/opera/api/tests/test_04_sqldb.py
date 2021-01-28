import json
import uuid
from pathlib import Path

from assertpy import assert_that

from opera.api.service.sqldb_service import OfflineStorage
from opera.api.util import file_util


class TestSessionData:

    def test_save_session_data(self, sql_db: OfflineStorage, generic_dir: Path):
        blueprint_token = str(uuid.uuid4())
        session_token = str(uuid.uuid4())
        version_tag = 'v1'
        sql_db.save_session_data(session_token, blueprint_token, version_tag, file_util.dir_to_json(generic_dir))
        assert sql_db.dot_opera_data_path.exists()
        assert (sql_db.dot_opera_data_path / str(session_token)).is_file()
        data = json.loads((sql_db.dot_opera_data_path / str(session_token)).read_text())
        assert_that(data).contains_only('tree', 'blueprint_token', 'version_tag', 'session_token', 'timestamp')
        assert data['version_tag'] == version_tag
        assert data['blueprint_token'] == blueprint_token
        assert data['session_token'] == session_token

    def test_get_session_data(self, sql_db: OfflineStorage, generic_dir: Path):
        blueprint_token = str(uuid.uuid4())
        session_token = str(uuid.uuid4())
        version_tag = 'v1'
        sql_db.save_session_data(session_token, blueprint_token, version_tag, file_util.dir_to_json(generic_dir))
        data = sql_db.get_session_data(session_token)
        assert_that(data).contains_only('tree', 'blueprint_token', 'version_tag', 'session_token', 'timestamp')
        assert blueprint_token == data['blueprint_token']
        assert version_tag == data['version_tag']
        assert session_token == data['session_token']
        assert_that(data['tree']).contains_only("0-new.txt", "1-new.txt", "2-new.txt", "3-new.txt")

    def test_get_last_session_data(self, sql_db: OfflineStorage, generic_dir: Path):
        tokens = {str(uuid.uuid4()): [str(uuid.uuid4()) for _ in range(5)] for _ in range(3)}
        for blueprint_token, session_tokens in tokens.items():
            for session_token in session_tokens:
                sql_db.save_session_data(session_token, blueprint_token, 'tag', file_util.dir_to_json(generic_dir))
        for blueprint_token in tokens.keys():
            # blueprint_token_new, _, _ = sql_db.get_last_session_data(blueprint_token)
            assert sql_db.get_last_session_data(blueprint_token)['blueprint_token'] == blueprint_token
