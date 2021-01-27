from pathlib import Path
from opera.api.util import file_util, xopera_util
from opera.api.settings import Settings
from assertpy import assert_that


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

    def test_init_data(self, change_api_workdir):
        xopera_util.init_data()
        assert_that(Settings.STDFILE_DIR).is_directory()
        assert_that(Settings.INVOCATION_DIR).is_directory()
        assert_that(Settings.DEPLOYMENT_DIR).is_directory()
