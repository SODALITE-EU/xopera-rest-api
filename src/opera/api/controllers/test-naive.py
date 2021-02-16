from opera.utils import format_outputs, save_outputs, get_template, get_workdir
from opera.storage import Storage
from opera.api.util import xopera_util

from pathlib import Path
import yaml
import json
# opera_diff()
blueprint_dir = Path('/home/mihaeltrajbaric/projects/SODALITE/Collection/TOSCA/mihas-private-tosca-blueprint-collection/blueprint_hash_test')
service_template = 'service1.yaml'
inputs_new = yaml.safe_load((blueprint_dir / 'inputs.yaml').open('r'))
print(inputs_new)

storage = Storage.create((blueprint_dir / '.opera'))
storage.write_json(inputs_new, "inputs")
storage.write(service_template, "root_file")
with xopera_util.cwd(blueprint_dir):
    template = get_template(storage)
    topology = template.instantiate(storage)
    # print(type(topology))
    # print(topology)
    # for _id, node in topology.nodes.items():
    #     print(f"{_id}:{node.dump()}")
    topology_dict = {tosca_id: node.dump() for tosca_id, node in topology.nodes.items()}
    print(json.dumps(topology_dict, indent=2, sort_keys=True))


