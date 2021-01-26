import pathlib
import json
import shutil


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
        file_path = (new_path / subpath)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(text)


if __name__ == '__main__':
    my_path = pathlib.Path(
        '/home/mihaeltrajbaric/projects/SODALITE/Collection/TOSCA/mihas-private-tosca-blueprint-collection/diff_and_update/.opera')

    new_path = pathlib.Path(__file__).parent / '.opera'

    tree_json = dir_to_json(my_path)
    print(json.dumps(tree_json, indent=2))
    json_to_dir(tree_json, new_path)
