import datetime
import os
import stat
from pathlib import Path

from assertpy import assert_that
from pytest_mock import mocker as Mock

from opera.api.settings import Settings
from opera.api.util import file_util, xopera_util, timestamp_util


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

    def test_mask_workdir(self):
        workdir = '~/projects/SODALITE/SODALITE-EU-github/xopera-rest-api'
        stacktrace = f"Exception: {workdir} does not exist"
        assert_that(xopera_util.mask_workdir(Path(workdir), stacktrace)).does_not_contain(workdir)

    def test_mask_workdirs(self):
        workdirs = [
            '~/projects/SODALITE/SODALITE-EU-github/xopera-rest-api',
            '~/projects/SODALITE/SODALITE-EU-github/xopera-rest-api-1',
            '~/projects/SODALITE/SODALITE-EU-github/xopera-rest-api-2',
        ]
        stacktrace = f"Exception: {workdirs[0]} does not exist, also {workdirs[1]} is missing. {workdirs[2]} is ok."
        assert_that(xopera_util.mask_workdirs([Path(workdir) for workdir in workdirs], stacktrace)).does_not_contain(
            *workdirs)

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

    def test_validate_key_valid(self, valid_ssh_key):
        assert xopera_util.vaildate_key(valid_ssh_key) is True

    def test_validate_key_invalid(self, invalid_ssh_key):
        assert xopera_util.vaildate_key(invalid_ssh_key) is False

    def test_validate_username_valid(self):
        assert xopera_util.validate_username("test") is True

    def test_validate_username_invalid(self):
        assert xopera_util.validate_username("test=") is False

    def test_setup_user(self, mocker, tmp_path_factory):
        location = tmp_path_factory.mktemp("temp")
        file = location / "hello.txt"
        file.write_text("hello")
        os.chmod(location, 0o755)
        os.chmod(file, 0o755)
        mock = mocker.MagicMock()
        mock.pw_uid = os.getuid()
        mock.pw_gid = os.getgid()
        mock.pw_dir = str(location)
        user_mock = mocker.patch("pwd.getpwnam", return_value=mock)

        mocker.patch("os.setgid")
        mocker.patch("os.setuid")
        xopera_util.setup_user([Path(location)], "test", None)

        permissions = oct(os.stat(file).st_mode & stat.S_IRWXU)

        assert permissions == '0o700'
        user_mock.assert_called_with("test")

    def test_setup_user_keys(self, mocker, valid_ssh_key, invalid_ssh_key):
        keys = {Settings.ssh_key_secret_name: valid_ssh_key, "other": invalid_ssh_key}
        list_secret_mock = mocker.patch("opera.api.util.xopera_util.list_secrets", return_value=["secret"])
        secret_mock = mocker.patch("opera.api.util.xopera_util.get_secret", return_value=keys)
        add_mock = mocker.patch("opera.api.util.xopera_util.add_key", return_value=None)
        xopera_util.setup_user_keys("test", "ACCESS_TOKEN")

        list_secret_mock.assert_called_once_with(Settings.ssh_key_path_template.format(username='test'), 'test', 'ACCESS_TOKEN')
        secret_mock.assert_called_once_with(Settings.ssh_key_path_template.format(username='test') + '/secret', 'test', 'ACCESS_TOKEN')
        add_mock.assert_called_once_with(valid_ssh_key)

    def test_setup_user_keys_invalid(self, mocker, valid_ssh_key, invalid_ssh_key):
        keys = {Settings.ssh_key_secret_name: invalid_ssh_key}
        list_secret_mock = mocker.patch("opera.api.util.xopera_util.list_secrets", return_value=["secret"])
        secret_mock = mocker.patch("opera.api.util.xopera_util.get_secret", return_value=keys)
        add_mock = mocker.patch("opera.api.util.xopera_util.add_key", return_value=None)
        xopera_util.setup_user_keys("test", "ACCESS_TOKEN")

        list_secret_mock.assert_called_once_with(Settings.ssh_key_path_template.format(username='test'), 'test', 'ACCESS_TOKEN')
        secret_mock.assert_called_once_with(Settings.ssh_key_path_template.format(username='test') + '/secret', 'test', 'ACCESS_TOKEN')
        add_mock.assert_not_called()

    def test_try_get_failed_tasks(self, error_stdout):
        failed_tasks = xopera_util.try_get_failed_tasks(error_stdout)
        assert len(failed_tasks) == 1
        assert failed_tasks['Fail'] == {'msg': 'Failed.', 'stderr': None}

class TestTimestampUtil:

    def test_datetime_now_to_string(self):
        tmstp_now_str = timestamp_util.datetime_now_to_string()
        assert_that(tmstp_now_str).is_type_of(str)
        datetime.datetime.strptime(tmstp_now_str, '%Y-%m-%dT%H:%M:%S.%f%z')

    def test_datetime_to_str_and_back(self):
        some_time = datetime.datetime.now(tz=datetime.timezone.utc)
        assert_that(timestamp_util.str_to_datetime(timestamp_util.datetime_to_str(some_time))).is_equal_to(some_time)
