from pathlib import Path

from assertpy import assert_that
from pytest_mock import mocker as Mock

from opera.api.settings import Settings
from opera.api.util import file_util, xopera_util


class TestFileUtil:

    def test_dir_to_json(self, generic_dir: Path):
        _json = file_util.dir_to_json(generic_dir)
        assert_that(_json).is_instance_of(dict)
        assert_that(_json).contains_only(*[f'{i}-new.txt' for i in range(4)])

    def test_json_to_dir(self, get_workdir_path):
        tree = {f'{i}-new.txt': '' for i in range(4)}
        path = get_workdir_path

        file_util.json_to_dir(tree, path)
        for key in tree.keys():
            assert_that(f'{path}/{key}').exists()


class TestXoperaUtil:

    def test_cwd(self, generic_dir: Path):
        tree = {f'{i}-new.txt': '' for i in range(4)}
        with xopera_util.cwd(generic_dir):
            for key in tree.keys():
                assert_that(str(key)).exists()

    def test_init_data(self, mock_api_workdir: Path):
        Path(Settings.STDFILE_DIR).mkdir(parents=True)
        (Path(Settings.STDFILE_DIR) / 'some_file').write_text('foo')
        xopera_util.init_data()
        assert_that(Settings.STDFILE_DIR).is_directory()
        assert_that(Settings.INVOCATION_DIR).is_directory()
        assert_that(Settings.DEPLOYMENT_DIR).is_directory()

    def test_configure_ssh_keys(self, mock_ssh_keys_loc: Path, mocker: Mock):
        # mock os.chown func
        mocker.patch('os.chown')

        # create dummy ssh keys
        ssh_pub_key = mock_ssh_keys_loc / "test-xOpera.pubk"
        ssh_private_key = mock_ssh_keys_loc / "test-xOpera"
        ssh_pub_key.write_text('public_key')
        ssh_private_key.write_text('private_key')

        xopera_util.configure_ssh_keys()
        config_string = (mock_ssh_keys_loc / 'config').read_text()
        assert config_string == "ConnectTimeout 5\n" \
                                f"IdentityFile {ssh_private_key}\n" \
                                "UserKnownHostsFile=/dev/null\n" \
                                "StrictHostKeyChecking=no"

    def test_configure_ssh_keys_too_many(self, mock_ssh_keys_loc: Path, mocker: Mock, caplog):
        # mock os.chown func
        mocker.patch('os.chown')

        # create dummy ssh key
        ssh_private_key = mock_ssh_keys_loc / "test-xOpera"
        ssh_private_key.write_text('private_key')

        xopera_util.configure_ssh_keys()
        assert 'Expected exactly 2 keys (public and private)' in caplog.text

    def test_configure_ssh_keys_wrong_ext(self, mock_ssh_keys_loc: Path, mocker: Mock, caplog):
        # mock os.chown func
        mocker.patch('os.chown')

        # create dummy ssh keys
        ssh_pub_key = mock_ssh_keys_loc / "test-xOpera.foo"
        ssh_private_key = mock_ssh_keys_loc / "test-xOpera.bar"
        ssh_pub_key.write_text('public_key')
        ssh_private_key.write_text('private_key')

        xopera_util.configure_ssh_keys()
        assert 'Wrong file extension' in caplog.text

    def test_configure_ssh_keys_key_mismatch(self, mock_ssh_keys_loc: Path, mocker: Mock, caplog):
        # mock os.chown func
        mocker.patch('os.chown')

        # create dummy ssh keys
        ssh_pub_key = mock_ssh_keys_loc / "foo-xOpera.pubk"
        ssh_private_key = mock_ssh_keys_loc / "bar-xOpera"
        ssh_pub_key.write_text('public_key')
        ssh_private_key.write_text('private_key')

        xopera_util.configure_ssh_keys()
        assert 'No matching private and public key pair' in caplog.text

    def test_configure_ssh_keys_ip_replace(self, mock_ssh_keys_loc: Path, mocker: Mock):
        # mock os.chown func
        mocker.patch('os.chown')

        # create dummy ssh keys
        ssh_pub_key = mock_ssh_keys_loc / "192.168.0.1-xOpera.pubk"
        ssh_private_key = mock_ssh_keys_loc / "192.168.0.1-xOpera"
        ssh_pub_key.write_text('public_key')
        ssh_private_key.write_text('private_key')

        xopera_util.configure_ssh_keys()
        assert (mock_ssh_keys_loc / '192-168-0-1-xOpera').is_file()
        assert (mock_ssh_keys_loc / '192-168-0-1-xOpera.pubk').is_file()

    def test_preprocess_inputs(self, inputs_with_secret, mocker):
        mocker.patch("opera.api.util.xopera_util.get_secret",
                        return_value={"ssh_key": "test"})
        result = xopera_util.preprocess_inputs(inputs_with_secret, "ACCESS_TOKEN")
        assert len(result) == 3
        assert result["frontend-address"] == "14.15.11.12"
        assert result["user"] == "test_user"
        assert result["ssh_key"] == "test"

    def test_preprocess_inputs_no_secret(self, inputs_no_secret):
        result = xopera_util.preprocess_inputs(inputs_no_secret, "ACCESS_TOKEN")
        assert len(result) == 2
        assert result["frontend-address"] == "14.15.11.12"
        assert result["user"] == "test_user"
