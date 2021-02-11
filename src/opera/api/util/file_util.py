import json
import pathlib
import shutil
from uuid import UUID


def dir_to_json(dir_path: pathlib.Path) -> dict:
    """
    Convert file tree to json
    """
    tree = {str(file.relative_to(dir_path)): file.read_text() for file in list(dir_path.rglob('*')) if file.is_file()}
    return tree


def json_to_dir(tree: dict, dir_path: pathlib.Path) -> None:
    """
    Convert json to file tree
    """
    shutil.rmtree(dir_path, ignore_errors=True)

    for subpath, text in tree.items():
        file_path = (dir_path / subpath)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(text)


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            # if the obj is uuid, we simply return the value of uuid
            return obj.hex
        return json.JSONEncoder.default(self, obj)
