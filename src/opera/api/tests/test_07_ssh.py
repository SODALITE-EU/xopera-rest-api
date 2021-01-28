from pathlib import Path

from assertpy import assert_that
from pytest_mock import mocker as Mock

from opera.api.settings import Settings
from opera.api.util import xopera_util


class TestSsh:

    def test_configure_ssh_keys(self, client, mock_ssh_keys_loc: Path, mocker: Mock):
        # mock os.chown func
        mocker.patch('os.chown')
        # create dummy ssh keys
        ssh_pub_key = mock_ssh_keys_loc / "test-xOpera.pubk"
        ssh_private_key = mock_ssh_keys_loc / "test-xOpera"
        ssh_pub_key.write_text('public_key')
        ssh_private_key.write_text('private_key')

        xopera_util.configure_ssh_keys()

        resp = client.get("/ssh/keys/public")
        assert_that(resp.json).contains_only('key_pair_name', 'public_key')
        assert resp.json['key_pair_name'] == 'test-xOpera'
        assert resp.json['public_key'] == 'public_key'

    def test_key_pair_not_set(self, client, mock_ssh_keys_loc: Path):
        # set key_pair to empty string
        Settings.key_pair = ''
        resp = client.get("/ssh/keys/public")
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json).contains_only('message')

    def test_key_pair_missing(self, client, mock_ssh_keys_loc: Path):
        # set key_pair to non-existent key
        Settings.key_pair = 'foo'
        resp = client.get("/ssh/keys/public")
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json).contains_only('message')
