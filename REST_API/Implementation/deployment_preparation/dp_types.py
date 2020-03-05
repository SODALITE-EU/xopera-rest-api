import datetime
import logging as log
import os
import uuid
from pathlib import Path

from deployment_preparation.settings import Settings
from werkzeug.datastructures import FileStorage
import shutil
import yaml
import json
import glob


class Node:
    def __init__(self, name: str = "path_node"):
        self.name = name

    def __str__(self):
        return self.name

    def write(self, path):
        pass

    @staticmethod
    def read(path: Path):
        pass

    def to_dict(self):
        pass

    @staticmethod
    def from_dict(dictionary: dict):
        pass


class File(Node):
    def __init__(self, name: str = "file", content: str = ""):
        super().__init__(name)
        self.content = content

    def write(self, path):
        path = path + self.name
        open_file = open(path, "w")
        open_file.write(self.content)
        open_file.close()
        return path

    def write_raw(self, path):
        open_file = open(path, "w")
        open_file.write(self.content)
        open_file.close()
        return path

    @staticmethod
    def read(path: Path):
        open_file = open(str(path.absolute()), "r")
        text = open_file.read()
        open_file.close()
        return File(path.name, text)

    def to_dict(self):
        return {"name": self.name, "type": "file", "content": self.content}

    @staticmethod
    def from_dict(dictionary: dict):
        return File(dictionary["name"], dictionary["content"])

    @staticmethod
    def tosca_from_dict(tosca: dict):
        return File(name="service.yaml", content=tosca["content"])


class Directory(Node):
    def __init__(self, name: str = "folder"):
        super().__init__(name)
        self.contents = list()

    def add(self, other):
        self.contents.append(other)

    def remove(self, other):
        self.contents.remove(other)

    def __str__(self):
        string = "\n" + self.name + ": "
        for nod in self.contents:
            string += "{}".format(nod)
            if nod != "" and nod != self.contents[len(self.contents) - 1]:
                string += ", "
        return string

    def write(self, path):
        path = path + self.name + "/"
        if not os.path.exists(path):
            os.mkdir(path)
        for nod in self.contents:
            nod.write(path)
        return path

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

    @staticmethod
    def from_dict(dictionary: dict):
        dir = Directory(dictionary["name"])
        for nod in dictionary["content"]:
            if nod["type"] == "dir":
                dir.add(Directory.from_dict(nod))
            else:
                dir.add(File.from_dict(nod))
        return dir


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
    def __init__(self, id: str = None, blueprint_token: uuid = None, version_id: datetime = None, tosca: File = None,
                 ansible_tree: Directory = None, timestamp: str = None, rc_file: File = None, raw_template: str = None):

        if raw_template is not None:
            self.template = raw_template

        elif None in [tosca, ansible_tree, blueprint_token, id]:
            # one of (tosca, ansible, blueprint_token and id) was None
            return

        self.id = id
        self.blueprint_token = blueprint_token
        if version_id is not None:
            self.version_id = version_id

        if tosca is None:
            self.tosca = File.read(Path(self.template + "service.yaml"))
        else:
            self.tosca = tosca
        """
        if self.tosca is not None and type(self.tosca) is File:
            tpl = Environment(loader=BaseLoader).from_string(self.tosca.content)
            self.tosca.content = tpl.render(id=self.id, key_pair=Settings.key_pair)
        """

        if ansible_tree is None:
            self.ansible_tree = Directory.read(Path(self.template + "playbooks/"))
        else:
            self.ansible_tree = ansible_tree

        if rc_file is None:
            try:
                self.rc_file = File.read(Path(self.template + "openrc.sh"))
            except (FileNotFoundError, AttributeError):
                self.rc_file = Dummy()
        else:
            self.rc_file = rc_file

        if timestamp is None:
            self.timestamp = Settings.datetime_now_to_string()
        else:
            self.timestamp = timestamp

    def print_metadata(self):
        return_string = ""
        for key, value in self.metadata().items():
            return_string += "{}: {}\n".format(key, value)
        log.info(return_string)

    def metadata(self):
        return {
            "blueprint_id": self.id,
            "blueprint_token": self.blueprint_token,
            "version_id": self.version_id,
            "timestamp": self.timestamp
        }

    def to_dict(self):
        return {
            "blueprint_id": str(self.id),
            "blueprint_token": str(self.blueprint_token),
            "version_id": self.version_id,
            "tosca_definition": self.tosca.to_dict(),
            "ansible_definition": self.ansible_tree.to_dict(),
            "rc_file": self.rc_file.to_dict(),
            "timestamp": self.timestamp
        }

    @staticmethod
    def pretty(d: dict, indent=0):
        for key, value in d.items():
            print('\t' * indent + str(key))
            if isinstance(value, dict):
                Deployment.pretty(value, indent + 1)
            else:
                print('\t' * (indent + 1) + str(value))

    @staticmethod
    def from_dict(blueprint_token: uuid, dictionary: dict):
        try:
            return Deployment(id=dictionary["blueprint_id"],
                              tosca=File.tosca_from_dict(dictionary["tosca_definition"]),
                              ansible_tree=Directory.from_dict(dictionary["ansible_definition"]),
                              rc_file=File.from_dict(dictionary["config_script"]),
                              blueprint_token=blueprint_token)
        except (KeyError, TypeError, FileNotFoundError):
            return None

    @staticmethod
    def from_csar(blueprint_token: uuid, CSAR: FileStorage):

        tmp_dir = Path(f'/tmp/xopera/{str(blueprint_token)}')
        CSAR_path = tmp_dir / Path(CSAR.filename)
        blueprint_path = tmp_dir / Path('blueprint')
        os.makedirs(tmp_dir)
        CSAR.save(CSAR_path.open('wb'))
        shutil.unpack_archive(str(CSAR_path), extract_dir=str(blueprint_path))
        tosca_meta_path = Path(blueprint_path / 'TOSCA.meta')
        if tosca_meta_path.exists():
            meta = yaml.safe_load(tosca_meta_path.open('r'))
            # author = meta['Created-By']
            entry_definitions = blueprint_path / Path(meta['Entry-Definitions'])
            name = meta['CSAR-name']
            # timestamp = meta['CSAR-timestamp']
        else:
            yaml_files = glob.glob(str(blueprint_path) + "/*.yaml") + glob.glob(str(blueprint_path) + "/*.yml")
            if len(yaml_files) != 1:
                return None

            entry_definitions = Path(yaml_files[0])
            entry_definitions_json = yaml.safe_load(entry_definitions.open('r'))
            meta = entry_definitions_json['metadata']
            # author = meta['template_author']
            name = meta['template_name']
            # timestamp = datetime.datetime.now().timestamp()

        deployment = Deployment(id=name,
                                tosca=File.read(entry_definitions),
                                ansible_tree=Directory.read(blueprint_path / Path("playbooks")),
                                blueprint_token=blueprint_token)
        deployment.tosca.name = 'service.yaml'
        shutil.rmtree(tmp_dir)
        return deployment
