import argparse
import os
import shutil
from datetime import datetime
from pathlib import Path
import glob

import yaml
import uuid


class TOSCAException(Exception):
    pass


class MultipleDefinitionsFound(TOSCAException):
    pass


def main(args):
    tmp_path = Path(f'/tmp/blueprint2csar/{uuid.uuid4()}')
    shutil.copytree(Path(args.blueprint_dir), tmp_path)

    blueprint_name = args.name
    blueprint_dir = tmp_path

    out_path = args.output or Path(Path(os.getcwd()) / Path(f'CSAR-{blueprint_name}'))
    meta_version = 1.1

    if args.no_meta:

        yaml_files = glob.glob(str(blueprint_dir) + "/*.yaml") + glob.glob(str(blueprint_dir) + "/*.yml")
        if len(yaml_files) != 1:
            raise MultipleDefinitionsFound('CSAR should contain a single .yaml / .yml file in root dir, multiple found')

        entry_definitions_path = Path(yaml_files[0])
        entry_definitions = yaml.safe_load(entry_definitions_path.open('r'))

        metadata = {
            'template_name': blueprint_name,
            'template_author': args.author,
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

        entry_definitions = blueprint_dir / Path(args.entry_definitions)

        if not entry_definitions.exists():
            raise FileNotFoundError(f'File {entry_definitions} does not exist!')

        version_str = yaml.safe_load(entry_definitions.open('r'))['tosca_definitions_version']

        if 'tosca_simple_yaml' not in version_str:
            raise TypeError('Support only different versions of "tosca_simple_yaml"')

        version = ".".join([s for s in version_str.split('_') if s.isdigit()])

        tosca_meta_path = Path(blueprint_dir / 'TOSCA.meta')

        if not tosca_meta_path.exists():
            tosca_meta = {'TOSCA-Meta-File-Version': meta_version,
                          'CSAR-Version': float(version),
                          'Created-By': args.author,
                          'Entry-Definitions': str(entry_definitions.name),
                          'CSAR-name': blueprint_name,
                          'CSAR-timestamp': datetime.now().timestamp()
                          }
            if args.other_definitions:

                for definition in args.other_definitions:

                    if not (blueprint_dir / Path(definition)).exists():
                        raise FileNotFoundError(f"File {definition} from other_definitions not found")
                    if not isinstance(yaml.safe_load((blueprint_dir / Path(definition)).open('r')), dict):
                        raise TypeError(f"File {definition} from other_definitions is not a valid yaml file.")

                tosca_meta['Other-Definitions'] = " ".join(args.other_definitions)

            with open(tosca_meta_path, 'w') as file:
                file.write(yaml.dump(tosca_meta, default_flow_style=False, sort_keys=False))

    shutil.make_archive(out_path, 'zip', blueprint_dir)
    shutil.rmtree(blueprint_dir)


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
