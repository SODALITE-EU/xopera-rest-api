from opera.api.blueprint_converters import blueprint2CSAR
import pytest
from pathlib import Path
import shutil
import yaml


class TestValidate:

    def test_not_meta_multiple_yaml(self, CSAR_unpacked):

        csar_path = CSAR_unpacked / 'CSAR-no-meta-multiple-yaml'
        assert not blueprint2CSAR.validate_csar(csar_path)

        with pytest.raises(blueprint2CSAR.MultipleDefinitionsFoundException):
            blueprint2CSAR.validate_csar(csar_path, raise_exceptions=True)

    def test_no_meta_no_entry_definitions(self, CSAR_unpacked):
        csar_path = CSAR_unpacked / 'CSAR-no-meta-no-entry-def'
        assert not blueprint2CSAR.validate_csar(csar_path)

        with pytest.raises(blueprint2CSAR.NoEntryDefinitionsFoundException):
            blueprint2CSAR.validate_csar(csar_path, raise_exceptions=True)

    def test_no_meta_no_meta_section(self, CSAR_unpacked):
        csar_path = CSAR_unpacked / 'CSAR-no-meta-no-meta-section'
        assert not blueprint2CSAR.validate_csar(csar_path)

        with pytest.raises(blueprint2CSAR.NoMetadataExcepion):
            blueprint2CSAR.validate_csar(csar_path, raise_exceptions=True)

    def test_no_meta_success(self, CSAR_unpacked):
        csar_path = CSAR_unpacked / 'CSAR-no-meta-ok'
        assert blueprint2CSAR.validate_csar(csar_path)

        # it should not fail
        blueprint2CSAR.validate_csar(csar_path, raise_exceptions=True)

    def test_meta_section_missing_key(self, CSAR_unpacked):
        csar_path = CSAR_unpacked / 'CSAR-no-meta-missing-key'
        assert not blueprint2CSAR.validate_csar(csar_path)

        with pytest.raises(blueprint2CSAR.BrokenMetadataException):
            blueprint2CSAR.validate_csar(csar_path, raise_exceptions=True)

    def test_broken_metadata_file(self, CSAR_unpacked):
        csar_path = CSAR_unpacked / 'CSAR-broken-meta'
        assert not blueprint2CSAR.validate_csar(csar_path)

        with pytest.raises(blueprint2CSAR.BrokenMetadataException):
            blueprint2CSAR.validate_csar(csar_path, raise_exceptions=True)

    def test_no_entry_definitions(self, CSAR_unpacked):
        csar_path = CSAR_unpacked / 'CSAR-no-entry-def'
        assert not blueprint2CSAR.validate_csar(csar_path)

        with pytest.raises(blueprint2CSAR.NoEntryDefinitionsFoundException):
            blueprint2CSAR.validate_csar(csar_path, raise_exceptions=True)

    def test_no_other_definitions(self, CSAR_unpacked):
        csar_path = CSAR_unpacked / 'CSAR-no-other-def'
        assert not blueprint2CSAR.validate_csar(csar_path)

        with pytest.raises(blueprint2CSAR.NoOtherDefinitionsFoundException):
            blueprint2CSAR.validate_csar(csar_path, raise_exceptions=True)

    def test_success(self, CSAR_unpacked):
        csar_path = CSAR_unpacked / 'CSAR-ok'
        assert blueprint2CSAR.validate_csar(csar_path)

        # it should not fail
        blueprint2CSAR.validate_csar(csar_path, raise_exceptions=True)


class TestEntryDefinitions:

    def test_no_meta_no_yaml(self, CSAR_unpacked):
        csar_path = CSAR_unpacked / 'CSAR-no-meta-no-entry-def'
        assert blueprint2CSAR.entry_definitions(csar_path) is None

    def test_no_meta_success(self, CSAR_unpacked):
        csar_path = CSAR_unpacked / 'CSAR-no-meta-ok'
        assert blueprint2CSAR.entry_definitions(csar_path) == 'service.yaml'

    def test_meta_no_entry_definitions(self, CSAR_unpacked):
        csar_path = CSAR_unpacked / 'CSAR-broken-meta'
        assert blueprint2CSAR.entry_definitions(csar_path) is None

    def test_meta_success(self, CSAR_unpacked):
        csar_path = CSAR_unpacked / 'CSAR-ok'
        assert blueprint2CSAR.entry_definitions(csar_path) == 'service.yaml'


class TestToCsarSimple:

    def test_CSAR_not_valid(self, CSAR_unpacked):
        csar_path = CSAR_unpacked / 'CSAR-broken-meta'
        dst_path = CSAR_unpacked / 'CSAR-dummy'
        assert not blueprint2CSAR.to_CSAR_simple(csar_path, dst_path, raise_exceptions=False)

        with pytest.raises(Exception):
            blueprint2CSAR.to_CSAR_simple(csar_path, dst_path, raise_exceptions=True)

    def test_success(self, CSAR_unpacked: Path):
        csar_path = CSAR_unpacked / 'CSAR-ok'
        dst_path = CSAR_unpacked / 'CSAR-dummy'
        dst_path_with_zip = Path(str(dst_path) + '.zip')

        assert blueprint2CSAR.to_CSAR_simple(csar_path, dst_path, raise_exceptions=False)
        assert dst_path_with_zip.exists()
        dst_path_with_zip.unlink()

        # should not fail
        blueprint2CSAR.to_CSAR_simple(csar_path, dst_path, raise_exceptions=True)
        assert dst_path_with_zip.exists()
        dst_path_with_zip.unlink()


class TestToCsar:

    def test_no_meta_multiple_yaml(self, get_workdir_path, CSAR_unpacked):
        blueprint_path = CSAR_unpacked / 'CSAR-no-meta-multiple-yaml'
        with pytest.raises(blueprint2CSAR.MultipleDefinitionsFoundException):
            blueprint2CSAR.to_CSAR(blueprint_name='some_blueprint',
                                   blueprint_dir=blueprint_path,
                                   no_meta=True,
                                   workdir=get_workdir_path)

    def test_no_meta_success(self, get_workdir_path, CSAR_unpacked):
        blueprint_path = CSAR_unpacked / 'CSAR-no-meta-ok'
        workdir = get_workdir_path
        name = 'some_blueprint'
        output = workdir / f'CSAR-{name}'

        blueprint2CSAR.to_CSAR(blueprint_name=name,
                               blueprint_dir=blueprint_path,
                               no_meta=True,
                               workdir=workdir,
                               output=output)

    def test_meta_no_entry_definitions(self, get_workdir_path, CSAR_unpacked):
        blueprint_path = CSAR_unpacked / 'CSAR-no-entry-def'
        with pytest.raises(FileNotFoundError):
            blueprint2CSAR.to_CSAR(blueprint_name='some_blueprint',
                                   blueprint_dir=blueprint_path,
                                   entry_definitions=Path('service.yaml'),
                                   workdir=get_workdir_path)

    def test_wrong_tosca_version(self, get_workdir_path, CSAR_unpacked):
        blueprint_path = CSAR_unpacked / 'CSAR-wrong-tosca-version'
        with pytest.raises(TypeError):
            blueprint2CSAR.to_CSAR(blueprint_name='some_blueprint',
                                   blueprint_dir=blueprint_path,
                                   entry_definitions=Path('service.yaml'),
                                   workdir=get_workdir_path)

    def test_no_other_definition(self, get_workdir_path, CSAR_unpacked):
        blueprint_path = CSAR_unpacked / 'CSAR-wrong-other-def'
        with pytest.raises(TypeError):
            blueprint2CSAR.to_CSAR(blueprint_name='some_blueprint',
                                   blueprint_dir=blueprint_path,
                                   entry_definitions=Path('service.yaml'),
                                   other_definitions=[Path('other_def.yaml')],
                                   workdir=get_workdir_path)

    def test_success(self, get_workdir_path: Path, CSAR_unpacked):
        workdir = get_workdir_path
        name = 'some_blueprint'
        output = workdir / f'CSAR-{name}'
        output_with_zip = Path(f'{output}.zip')
        unpacked = workdir / 'my_csar_unpacked'
        blueprint_path = CSAR_unpacked / 'CSAR-ok'
        blueprint2CSAR.to_CSAR(blueprint_name=name,
                               blueprint_dir=blueprint_path,
                               entry_definitions=Path('service.yaml'),
                               workdir=workdir,
                               output=output)
        assert output_with_zip.exists()

        shutil.unpack_archive(str(output_with_zip.absolute()), extract_dir=str(unpacked.absolute()))

        assert (unpacked / 'TOSCA-Metadata').is_dir()
        metadata_path = unpacked / 'TOSCA-Metadata' / 'TOSCA.meta'
        assert metadata_path.exists()
        metadata = yaml.load(metadata_path.open('r'))
        assert isinstance(metadata, dict)
        assert all(key in metadata.keys() for key in ['TOSCA-Meta-File-Version', 'CSAR-Version',
                                                      'Created-By', 'Entry-Definitions',
                                                      'CSAR-name', 'CSAR-timestamp'])





