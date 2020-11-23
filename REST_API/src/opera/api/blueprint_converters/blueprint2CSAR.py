import argparse
import glob
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import yaml


class TOSCAException(Exception):
    pass


class MultipleDefinitionsFoundException(TOSCAException):
    pass


class NoMetadataExcepion(TOSCAException):
    pass


class BrokenMetadataException(TOSCAException):
    pass


class NoEntryDefinitionsFoundException(TOSCAException):
    pass


class NoOtherDefinitionsFoundException(TOSCAException):
    pass


def to_CSAR_simple(src: Path, dst: Path, raise_exceptions=False):
    """
    Makes a Zip archive from src and saves it to dst. Src must contain either a TOSCA-Metadata directory, which in turn
    contains the TOSCA.meta metadata file or a yaml (.yml or .yaml) file at the root of the archive. The yaml file
    being a valid tosca definition template that MUST define a metadata section where
    template_name and template_version are required.
    https://docs.oasis-open.org/tosca/TOSCA-Simple-Profile-YAML/v1.3/os/TOSCA-Simple-Profile-YAML-v1.3-os.html#_Toc26969474
    Args:
        src: Path to dir to be converted to CSAR (Path)
        dst: Path to converted CSAR archive (Path)
        raise_exceptions: raise exception instead of returning False on mistakes (bool)

    Returns: conversion_success (bool)
    """
    if not validate_csar(src, raise_exceptions=raise_exceptions):
        return False
    os.makedirs(str(dst.parent), exist_ok=True)
    shutil.make_archive(str(dst), 'zip', str(src))
    return True


def to_CSAR(blueprint_name: str, blueprint_dir: Path, no_meta: bool = False, entry_definitions: Path = None,
            other_definitions: list = None, author: str = 'SODALITE blueprint2CSAR tool', output: Path = None,
            workdir: Path = Path('/tmp/blueprint2csar')):
    """
    Packs TOSCA Simple Profile definitions along with all accompanying artifacts
    (e.g. scripts, binaries, configuration files) in TOSCA Cloud Service Archive (CSAR) format.
    In compliance with TOSCA Simple Profile in YAML Version 1.3
    https://docs.oasis-open.org/tosca/TOSCA-Simple-Profile-YAML/v1.3/os/TOSCA-Simple-Profile-YAML-v1.3-os.html#_Toc26969474
    Args:
        blueprint_name: name of blueprint / CSAR
        blueprint_dir: Path to dir with TOSCA definitions and all accompanying artifacts
        no_meta: Do not create TOSCA.meta file. Metadata section will instead be created in TOSCA definitions file.
                 This implies blueprint_dir contains a single YAML file at the root of the archive.
        entry_definitions: Path to main TOSCA .yaml (or .yml) file relative to blueprint_dir
        other_definitions: List of Paths to files containing substitution templates relative to blueprint_dir
        author: The person or vendor, respectively, who created the CSAR.
        output: Path to output file. If omitted, script will output CSAR to workdir as CSAR-{name}.zip
        workdir: Workdir to be used during converting to CSAR format.


    """
    tmp_blueprint_path = workdir / Path(str(uuid.uuid4()))
    shutil.copytree(blueprint_dir, tmp_blueprint_path)

    out_path = output or Path(Path(os.getcwd()) / Path(f'CSAR-{blueprint_name}'))
    meta_version = 1.1

    if no_meta:

        yaml_files = glob.glob(str(tmp_blueprint_path) + "/*.yaml") + glob.glob(str(tmp_blueprint_path) + "/*.yml")
        if len(yaml_files) != 1:
            raise MultipleDefinitionsFoundException(
                'CSAR should contain a single .yaml / .yml file in root dir, multiple found')

        entry_definitions_path = Path(yaml_files[0])
        entry_definitions = yaml.safe_load(entry_definitions_path.open('r'))

        metadata = {
            'template_name': blueprint_name,
            'template_author': author,
            'template_version': meta_version
        }

        if 'metadata' not in entry_definitions:
            version_str = entry_definitions['tosca_definitions_version']
            del entry_definitions['tosca_definitions_version']
            entry_definitions = {'tosca_definitions_version': version_str, 'metadata': metadata, **entry_definitions}
        else:
            entry_definitions['metadata'] = {**metadata, **entry_definitions['metadata']}

        with entry_definitions_path.open('w')as file:
            file.write(yaml.dump(entry_definitions, default_flow_style=False, sort_keys=False))

    else:

        entry_definitions = tmp_blueprint_path / Path(entry_definitions)

        if not entry_definitions.exists():
            raise FileNotFoundError(f'File {entry_definitions} does not exist!')

        version_str = yaml.safe_load(entry_definitions.open('r'))['tosca_definitions_version']

        if 'tosca_simple_yaml' not in version_str:
            raise TypeError('Support only different versions of "tosca_simple_yaml"')

        version = ".".join([s for s in version_str.split('_') if s.isdigit()])

        tosca_meta_dir_path = Path(tmp_blueprint_path / 'TOSCA-Metadata')
        tosca_meta_path = Path(tosca_meta_dir_path / 'TOSCA.meta')

        if not tosca_meta_path.exists():
            tosca_meta = {'TOSCA-Meta-File-Version': meta_version,
                          'CSAR-Version': float(version),
                          'Created-By': author,
                          'Entry-Definitions': str(entry_definitions.name),
                          'CSAR-name': blueprint_name,
                          'CSAR-timestamp': datetime.now().timestamp()
                          }
            if other_definitions:

                for definition in other_definitions:

                    if not (tmp_blueprint_path / Path(definition)).exists():
                        raise FileNotFoundError(f"File {definition} from other_definitions not found")
                    if not isinstance(yaml.safe_load((tmp_blueprint_path / Path(definition)).open('r')), dict):
                        raise TypeError(f"File {definition} from other_definitions is not a valid yaml file.")

                tosca_meta['Other-Definitions'] = " ".join(other_definitions)

            if not tosca_meta_dir_path.exists():
                tosca_meta_dir_path.mkdir()

            with open(tosca_meta_path, 'w') as file:
                file.write(yaml.dump(tosca_meta, default_flow_style=False, sort_keys=False))

    shutil.make_archive(out_path, 'zip', tmp_blueprint_path)
    shutil.rmtree(tmp_blueprint_path)


def from_CSAR(csar: Path, dst: Path):
    """
    Unpacks CSAR arhive.
    Args:
        csar: Path to .zip file with CSAR archive
        dst: Path to where archive should be unpacked

    """
    shutil.unpack_archive(str(csar.absolute()), extract_dir=str(dst.absolute()))


def validate_csar(csar: Path, raise_exceptions=False):
    """
    validates if tree is a valid csar archive.
    Args:
        csar: Path to csar archive
        raise_exceptions: raise exception instead of returning False on mistakes

    Returns: csar_is_valid: bool

    """
    tmp_blueprint_path = csar
    tosca_meta_path = Path(tmp_blueprint_path / 'TOSCA-Metadata' / 'TOSCA.meta')

    if not tosca_meta_path.exists():

        yaml_files = glob.glob(str(tmp_blueprint_path) + "/*.yaml") + glob.glob(str(tmp_blueprint_path) + "/*.yml")
        if len(yaml_files) > 1:
            if raise_exceptions:
                raise MultipleDefinitionsFoundException(
                    'without metadata file, CSAR should contain a single .yaml / .yml file in root dir, multiple found')
            return False
        elif len(yaml_files) == 0:
            if raise_exceptions:
                raise NoEntryDefinitionsFoundException(
                    'without metadata file, CSAR should contain a single .yaml / .yml file in root dir, None found')
            return False

        entry_definitions_path = Path(yaml_files[0])
        entry_definitions = yaml.safe_load(entry_definitions_path.open('r'))

        if 'metadata' not in entry_definitions:
            if raise_exceptions:
                raise NoMetadataExcepion("without metadata file, entry_definitions should have 'metadata' section")
            return False
        else:
            metadata = entry_definitions['metadata']
            for key in ['template_name', 'template_author', 'template_version']:
                if key not in metadata:
                    if raise_exceptions:
                        raise BrokenMetadataException(f'Missing {key} key in {tosca_meta_path}')
                    return False
    else:  # metadata file exist
        metadata_yaml = yaml.safe_load(open(tosca_meta_path, 'r').read())
        for key in ['TOSCA-Meta-File-Version', 'CSAR-Version', 'Created-By', 'Entry-Definitions']:
            if key not in metadata_yaml:
                if raise_exceptions:
                    raise BrokenMetadataException(f'Missing {key} key in {tosca_meta_path}')
                return False
        entry_definitions_path = Path(tmp_blueprint_path / metadata_yaml['Entry-Definitions'])

        if not entry_definitions_path.exists():
            if raise_exceptions:
                raise NoEntryDefinitionsFoundException(f'{entry_definitions_path} not found')
            return False

        if 'Other-Definitions' in metadata_yaml:
            other_definitions_filenames = metadata_yaml['Other-Definitions'].split(" ")
            for definitions in other_definitions_filenames:
                other_definitions_path = Path(tmp_blueprint_path / definitions)
                if not other_definitions_path.exists():
                    if raise_exceptions:
                        raise NoOtherDefinitionsFoundException(f'{other_definitions_path} not found')
                    return False

    return True


def entry_definitions(csar: Path):
    """
    returns path: str to entry definitions, relative to csar path

    """

    tosca_meta_path = Path(csar / 'TOSCA-Metadata' / 'TOSCA.meta')

    if not tosca_meta_path.exists():
        yaml_files = glob.glob(str(csar) + "/*.yaml") + glob.glob(str(csar) + "/*.yml")

        if len(yaml_files) != 1:
            return None

        return Path(yaml_files[0]).name

    else:
        metadata_yaml = yaml.safe_load(open(tosca_meta_path, 'r').read())

        if 'Entry-Definitions' not in metadata_yaml:
            return None

        return metadata_yaml['Entry-Definitions']


def main(args):
    to_CSAR(blueprint_name=args.name, blueprint_dir=args.blueprint_dir, no_meta=args.no_meta,
            entry_definitions=args.entry_definitions, other_definitions=args.other_definitions,
            author=args.author, output=args.output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Packs TOSCA Simple Profile definitions along with all accompanying artifacts (e.g. scripts, '
                    'binaries, configuration files) in TOSCA Cloud Service Archive (CSAR) format.\n')
    parser.add_argument('name', help='template name', type=str)
    parser.add_argument('blueprint_dir', help='Path to dir with TOSCA definitions and all accompanying artifacts',
                        type=str)
    parser.add_argument('--no-meta', action='store_true',
                        help='Do not create TOSCA.meta file. Metadata section will instead be created in TOSCA '
                             'definitions file. This implies blueprint_dir contains a single YAML '
                             'file at the root of the archive.')
    parser.add_argument('--entry-definitions', help='Path to main TOSCA .yaml (or .yml) file relative to blueprint_dir',
                        type=str)
    parser.add_argument('--other-definitions', nargs='+',
                        help='List of paths to files containing substitution templates relative to blueprint_dir',
                        type=str)

    parser.add_argument('--author', help="The person or vendor, respectively, who created the CSAR.", type=str,
                        default='SODALITE blueprint2CSAR tool')
    parser.add_argument('--output',
                        help="Path to output file. If omitted, script will output CSAR to workdir as CSAR-{name}.zip",
                        type=str)

    parsed_args = parser.parse_args()

    main(parsed_args)
