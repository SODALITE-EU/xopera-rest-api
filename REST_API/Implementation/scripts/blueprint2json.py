import argparse
import datetime
import json
import os
import urllib.parse
from pathlib import Path


def datetime_now_to_string():
    return datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')


class Node:
    def __init__(self, name: str = "path_node"):
        self.name = name

    @staticmethod
    def read(path: Path):
        pass


class File(Node):
    def __init__(self, name: str = "file", content: str = ""):
        super().__init__(name)
        self.content = content

    @staticmethod
    def read(path: Path):
        open_file = open(str(path.absolute()), "r")
        text = open_file.read()
        open_file.close()
        return File(path.name, text)

    def to_dict(self):
        return {"name": self.name, "type": "file", "content": self.content}


class Directory(Node):
    def __init__(self, name: str = "folder"):
        super().__init__(name)
        self.contents = list()

    def add(self, other):
        self.contents.append(other)

    @staticmethod
    def read(path: Path):
        dir = Directory(path.name)
        for item in path.iterdir():
            if item.is_file():
                dir.add(File.read(item))
            else:
                dir.add(Directory.read(item))
        return dir

    def to_dict(self):
        dictionary = {"name": self.name, "type": "dir", "content": []}
        for nod in self.contents:
            dictionary["content"].append(nod.to_dict())
        return dictionary


class Dummy:
    def __init__(self):
        pass

    @staticmethod
    def to_dict():
        return {
            "name": "no_config",
            "type": "file",
            "content": ""
        }


class Deployment:
    def __init__(self, id: str, template: Path, tosca: Path, openrc: str):

        self.template = template
        # if self.template[-1] != '/':
        #     self.template = self.template + '/'
        self.id = id
        self.tosca = File.read(tosca)
        self.tosca.name = 'service.yaml'
        self.ansible_tree = Directory.read(self.template.joinpath("playbooks"))
        if openrc is None:
            openrc_path = self.template.joinpath('openrc.sh')
        else:
            openrc_path = Path(openrc)
        try:
            self.rc_file = File.read(openrc_path)
            self.rc_file.name = 'openrc.sh'
        except FileNotFoundError:
            self.rc_file = Dummy()
        self.timestamp = datetime_now_to_string()

    def to_dict(self):
        return {
            "blueprint_id": "{}".format(self.id),
            "tosca_definition": self.tosca.to_dict(),
            "ansible_definition": self.ansible_tree.to_dict(),
            "config_script": self.rc_file.to_dict(),
            "timestamp": self.timestamp
        }


def escape(string: str):
    escaped = string.replace('\"', '\\"')
    escaped = escaped.replace('\n', '\\n')
    # escaped = escaped.replace('!', '\\!')
    return '"{}"'.format(escaped)


def urlencode(string: str):
    return urllib.parse.quote(string)


def main(args):
    deploy_id = args.id
    path_to_TOSCA_yaml = Path(args.tosca)
    path_to_template = path_to_TOSCA_yaml.parent

    deployment = Deployment(id=deploy_id, template=path_to_template, tosca=path_to_TOSCA_yaml,
                            openrc=args.config_script)

    json_obj = deployment.to_dict()
    output = json.dumps(json_obj, indent=2, sort_keys=False)
    if args.file is not None:
        directory = os.path.dirname(args.file)
        if directory is not "":
            os.makedirs(directory, exist_ok=True)

        with open(args.file, 'w') as file:
            if args.url_encode:
                output = urlencode(output)
                file.write(output)
            else:
                json.dump(json_obj, file, indent=4)
        print('JSON saved to file "{}"'.format(args.file))
        return
    if args.url_encode:
        output = urlencode(output)
    print("\n\n\n\n")
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Converts xOpera blueprint to JSON.\nBlueprint dir usually consists of TOSCA .yaml file, '
                    'related ansible playbooks, stored in dir "playbooks" and "openstack.sh" for setting environment '
                    'to work with OpenStack.')
    parser.add_argument('id', help='ID of deployment', type=str)
    parser.add_argument('tosca', help='Path to .yaml file with tosca configuration', type=str)
    parser.add_argument('--config-script', help="Path to configuration script to set env_vars for connecting to cloud "
                                                "infrastructure. In case of deploying to openstack, script is called "
                                                "openrc.sh", type=str)

    parser.add_argument('--file', help="Path to output file. If omitted, script will output JSON as string to STDOUT",
                        type=str)
    parser.add_argument('--url-encode', help="url encode output, so it can be sent to REST api",
                        action="store_true", default=False)

    args = parser.parse_args()

    main(args)
