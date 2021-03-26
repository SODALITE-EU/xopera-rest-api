from enum import Enum
import json
import tempfile
import shutil
from pathlib import Path
from opera.storage import Storage
from opera.utils import get_template

from opera.api.util import file_util, xopera_util
from opera.api.openapi.models import OperationType


# THIS class is in xOpera > 0.6.4, when update, replace it with importing opera.constants.NodeState
class NodeState(Enum):
    INITIAL = "initial"
    CREATING = "creating"
    CREATED = "created"
    CONFIGURING = "configuring"
    CONFIGURED = "configured"
    STARTING = "starting"
    STARTED = "started"
    STOPPING = "stopping"
    DELETING = "deleting"
    ERROR = "error"


class OperaSessionData:
    def __init__(self, storage: Storage):
        self.storage = storage
        self.tree = file_util.dir_to_json(self.storage.path)
        self.instances = {key: json.loads(value) for key, value in self.tree.items() if "instances" in key}
        # TODO change component_version filter to something better
        self.nodes = {value['tosca_name']['data']: value['state']['data']
                      for _, value in self.instances.items() if 'component_version' in value.keys()}

    def __str__(self):
        return json.dumps(self.nodes, indent=2)

    def initial_nodes(self):
        return [name for name, state in self.nodes.items() if state == "initial"]

    def deployed_nodes(self):
        return [name for name, state in self.nodes.items() if state == "started"]

    def all_nodes(self):
        with xopera_util.cwd(self.storage.path.parent):
            template = get_template(self.storage)
            return list(template.nodes.keys())


def get_all_nodes(service_yaml_path: Path):
    base, name = service_yaml_path.parent, service_yaml_path.name
    storage = Storage(base / ".opera_tmp")
    storage.write(str(name), "root_file")
    nodes = OperaSessionData(storage).all_nodes()
    shutil.rmtree(base / ".opera_tmp", ignore_errors=True)
    return nodes


def get_current_nodes(storage: Storage, operation: OperationType):
    if operation in (OperationType.DEPLOY_FRESH, OperationType.DEPLOY_CONTINUE):
        return OperaSessionData(storage).deployed_nodes()
    if operation == OperationType.UNDEPLOY:
        return OperaSessionData(storage).initial_nodes()
    if operation == OperationType.UPDATE:
        return "Let's cry"

