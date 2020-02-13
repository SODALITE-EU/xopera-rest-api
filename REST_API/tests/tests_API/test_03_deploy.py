import copy
import datetime
import io
import time

import requests
from assertpy import assert_that, fail
from werkzeug.datastructures import FileStorage

local_blueprint = {
    "blueprint_id": "local_test",
    "tosca_definition": {
        "name": "service.yaml",
        "type": "file",
        "content": "tosca_definitions_version: tosca_simple_yaml_1_0\n\ntopology_template:\n  node_templates:\n    my-workstation:\n      type: tosca.nodes.Compute\n      attributes:\n        private_address: localhost\n        public_address: localhost\n\n    hello:\n      type: tosca.nodes.SoftwareComponent\n      requirements:\n        - host: my-workstation\n      interfaces:\n        Standard:\n          create: playbooks/hello/create.yml"
    },
    "ansible_definition": {
        "name": "playbooks",
        "type": "dir",
        "content": [
            {
                "name": "hello",
                "type": "dir",
                "content": [
                    {
                        "name": "create.yml",
                        "type": "file",
                        "content": "---\n- hosts: all\n  become: no\n  gather_facts: no\n  tasks:\n    - name: Make the location\n      file:\n        path: /tmp/playing-opera/hello\n        recurse: true\n        state: directory\n\n    - name: Ansible was here\n      file:\n        path: /tmp/playing-opera/hello/hello.txt\n        state: touch"
                    },
                    {
                        "name": "delete.yml",
                        "type": "file",
                        "content": "---\n- hosts: all\n  become: no\n  gather_facts: no\n  tasks:\n    - name: delete folder\n      file:\n        path: /tmp/playing-opera\n        state: absent"
                    }
                ]
            }
        ]
    },
    "config_script": {
        "name": "no_config",
        "type": "file",
        "content": ""
    },
    "timestamp": "2019-12-19T15:36:37.362777"
}
local_inputs = "file_name: my_file"

local_blueprint_inputs = {
    "blueprint_id": "hello-world-inputs",
    "tosca_definition": {
        "name": "service.yaml",
        "type": "file",
        "content": "tosca_definitions_version: tosca_simple_yaml_1_0\n\nnode_types:\n  my.nodes.hello:\n    derived_from: tosca.nodes.SoftwareComponent\n    requirements:\n      - host:\n          capability: tosca.capabilities.Compute\n    properties:\n      file_name:\n        type: string\n        description: file name\n    interfaces:\n      Standard:\n        create:\n          inputs:\n            file_name:    { default: { get_property: [ SELF, file_name    ] } }\n          implementation: playbooks/hello/create.yml\n        delete:\n          inputs:\n            file_name:    { default: { get_property: [ SELF, file_name    ] } }\n          implementation: playbooks/hello/delete.yml\n\n\n\ntopology_template:\n  node_templates:\n    my-workstation:\n      type: tosca.nodes.Compute\n      attributes:\n        private_address: localhost\n        public_address: localhost\n\n    hello:\n      type: my.nodes.hello\n      requirements:\n        - host: my-workstation\n      properties:\n        file_name: { get_input: file_name }"
    },
    "ansible_definition": {
        "name": "playbooks",
        "type": "dir",
        "content": [
            {
                "name": "hello",
                "type": "dir",
                "content": [
                    {
                        "name": "create.yml",
                        "type": "file",
                        "content": "---\n- hosts: all\n  become: no\n  gather_facts: no\n  tasks:\n    - name: Make the location\n      file:\n        path: /tmp/playing-opera/hello\n        recurse: true\n        state: directory\n\n    - name: Ansible was here\n      file:\n        path: \"/tmp/playing-opera/hello/{{ file_name }}\"\n        state: touch"
                    },
                    {
                        "name": "delete.yml",
                        "type": "file",
                        "content": "---\n- hosts: all\n  become: no\n  gather_facts: no\n  tasks:\n    - name: delete file\n      file:\n        path: \"/tmp/playing-opera/hello/{{ file_name }}\"\n        state: absent"
                    }
                ]
            }
        ]
    },
    "config_script": {
        "name": "no_config",
        "type": "file",
        "content": ""
    },
    "timestamp": "2020-01-24T14:03:54.129495"
}

payload_generic = {
    "blueprint_id": "id",
    "tosca_definition": {
        "name": "service.yaml",
        "type": "file",
        "content": ""
    },
    "ansible_definition": {
        "name": "playbooks",
        "type": "dir",
        "content": [
            {
                "name": "dumy.yml",
                "type": "file",
                "content": "no content"
            }
        ]
    },
    "config_script": {
        "name": "no_config",
        "type": "file",
        "content": ""
    }
}


class TestDeploy:

    @staticmethod
    def corrupt_blueprint(blueprint: dict):
        blueprint_corrupted = copy.deepcopy(blueprint)
        tosca = blueprint_corrupted['tosca_definition']['content']
        tosca_corrupted = tosca.replace('topology_template', 'top010gy_template')
        blueprint_corrupted['tosca_definition']['content'] = tosca_corrupted
        return blueprint_corrupted

    @staticmethod
    def monitor(session_token, job, url, timeout):
        done = False
        resp = None
        time_start = time.time()
        while not done:
            resp = requests.get(url=url + "/info/status", params={'token': session_token})
            try:
                status = resp.json()[job]
                done = True
            except KeyError:
                if time.time() - time_start > timeout:
                    break
                time.sleep(1)
                pass
        return done, resp

    def test_deploy_json_keys_error1(self, url):
        resp = requests.post(url=url + "/deploy/{}".format('a'))
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json()).is_not_none().contains_only("message")

    def test_deploy_json_keys_error2(self, url):
        resp = requests.delete(url=url + "/deploy/{}".format('a'))
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json()).is_not_none().contains_only("message")

    def test_deploy_json_keys_success(self, url):
        # corrupt blueprint so it will fail
        local_blueprint_failed = TestDeploy.corrupt_blueprint(local_blueprint)

        resp = requests.post(url=url + "/manage", json=local_blueprint_failed)
        blueprint_token = resp.json()['blueprint_token']

        # deploy and check deploy message
        resp = requests.post(url=url + "/deploy/{}".format(blueprint_token))
        assert_that(resp.json()).contains_only('message', 'session_token', 'blueprint_id', 'blueprint_token',
                                               'version_id', 'timestamp')
        assert_that(resp.json()['blueprint_token']).is_equal_to(blueprint_token)
        assert_that(resp.json()['blueprint_id']).is_equal_to(local_blueprint['blueprint_id'])
        assert_that(resp.status_code).is_equal_to(202)

    def test_deploy_wrong_timestamp(self, url):
        # corrupt blueprint so it will fail
        local_blueprint_failed = TestDeploy.corrupt_blueprint(local_blueprint)

        resp = requests.post(url=url + "/manage", json=local_blueprint_failed)
        blueprint_token = resp.json()['blueprint_token']

        # deploy and check deploy message
        resp = requests.post(url=url + "/deploy/{}".format(blueprint_token), params={'timestamp': 1})
        assert_that(resp.status_code).is_equal_to(404)

    def test_deploy_wrong_version_id(self, url):
        # corrupt blueprint so it will fail
        local_blueprint_failed = TestDeploy.corrupt_blueprint(local_blueprint)

        resp = requests.post(url=url + "/manage", json=local_blueprint_failed)
        blueprint_token = resp.json()['blueprint_token']

        # deploy and check deploy message
        resp = requests.post(url=url + "/deploy/{}".format(blueprint_token), params={'version_id': 42})
        assert_that(resp.status_code).is_equal_to(404)

    def test_deploy_wrong_timestamp_and_version_id(self, url):
        # corrupt blueprint so it will fail
        local_blueprint_failed = TestDeploy.corrupt_blueprint(local_blueprint)

        resp = requests.post(url=url + "/manage", json=local_blueprint_failed)
        blueprint_token = resp.json()['blueprint_token']

        # deploy and check deploy message
        resp = requests.post(url=url + "/deploy/{}".format(blueprint_token), params={'timestamp': 1, 'version_id': 42})
        assert_that(resp.status_code).is_equal_to(404)

    def test_deploy_last_version(self, url):
        # corrupt blueprint so it will fail and take less time
        local_blueprint_failed = TestDeploy.corrupt_blueprint(local_blueprint)

        # create 4 different payloads and upload them under same token
        payloads = [{**local_blueprint_failed, 'blueprint_id': "id_{}_id".format(i + 1)} for i in range(4)]
        resp = requests.post(url=url + "/manage", json=payloads[0])
        token = resp.json()['blueprint_token']
        responses = [resp] + [requests.post(url=url + "/manage/{}".format(token), json=payloads[i + 1]) for i in
                              range(3)]

        last_json = responses[-1].json()
        last_payload = payloads[-1]
        resp = requests.post(url=url + "/deploy/{}".format(token))
        assert_that(resp.status_code).is_equal_to(202)
        assert_that(int(resp.json()['version_id'])).is_equal_to(int(last_json['version_id']))
        assert_that(resp.json()['timestamp']).is_equal_to(last_json['timestamp'])
        assert_that(resp.json()['blueprint_id']).is_equal_to(last_payload['blueprint_id'])

    def test_deploy_by_version_id(self, url):
        # corrupt blueprint so it will fail and take less time
        local_blueprint_failed = TestDeploy.corrupt_blueprint(local_blueprint)

        # create 4 different payloads and upload them under same token
        payloads = [{**local_blueprint_failed, 'blueprint_id': "id_{}_id".format(i + 1)} for i in range(4)]
        resp = requests.post(url=url + "/manage", json=payloads[0])
        token = resp.json()['blueprint_token']
        responses = [resp] + [requests.post(url=url + "/manage/{}".format(token), json=payloads[i + 1]) for i in
                              range(3)]

        json_3 = responses[2].json()
        payload_3 = payloads[2]
        resp = requests.post(url=url + "/deploy/{}".format(token), params={'version_id': int(json_3['version_id'])})
        assert_that(resp.status_code).is_equal_to(202)
        assert_that(int(resp.json()['version_id'])).is_equal_to(int(json_3['version_id']))
        assert_that(resp.json()['timestamp']).is_equal_to(json_3['timestamp'])
        assert_that(resp.json()['blueprint_id']).is_equal_to(payload_3['blueprint_id'])

    def test_deploy_by_timestamp(self, url):
        # corrupt blueprint so it will fail and take less time
        local_blueprint_failed = TestDeploy.corrupt_blueprint(local_blueprint)

        # create 4 different payloads and upload them under same token
        payloads = [{**local_blueprint_failed, 'blueprint_id': "id_{}_id".format(i + 1)} for i in range(4)]
        resp = requests.post(url=url + "/manage", json=payloads[0])
        token = resp.json()['blueprint_token']
        responses = [resp] + [requests.post(url=url + "/manage/{}".format(token), json=payloads[i + 1]) for i in
                              range(3)]

        json_2 = responses[1].json()
        payload_2 = payloads[1]
        resp = requests.post(url=url + "/deploy/{}".format(token), params={'timestamp': json_2['timestamp']})
        assert_that(resp.status_code).is_equal_to(202)
        assert_that(int(resp.json()['version_id'])).is_equal_to(int(json_2['version_id']))
        assert_that(resp.json()['timestamp']).is_equal_to(json_2['timestamp'])
        assert_that(resp.json()['blueprint_id']).is_equal_to(payload_2['blueprint_id'])

    def test_deploy_success(self, url):

        # upload local template
        resp = requests.post(url=url + "/manage", json=local_blueprint)
        blueprint_token = resp.json()['blueprint_token']

        # deploy and check deploy message
        resp = requests.post(url=url + "/deploy/{}".format(blueprint_token))
        assert_that(resp.json()).contains_only('message', 'session_token', 'blueprint_id', 'blueprint_token',
                                               'version_id', 'timestamp')
        assert_that(resp.json()['blueprint_token']).is_equal_to(blueprint_token)
        assert_that(resp.json()['blueprint_id']).is_equal_to(local_blueprint['blueprint_id'])
        assert_that(resp.status_code).is_equal_to(202)

        session_token = resp.json()['session_token']

        done, resp = TestDeploy.monitor(session_token, job='deploy', url=url, timeout=30)

        assert_that(done).is_true()
        assert_that(resp.json()['deploy']).is_equal_to('done')
        assert_that(resp.status_code).is_equal_to(201)

        # check logs

        resp = requests.get(url=url + "/info/log", params={'session_token': session_token})
        logs_json = {k: v for d in resp.json() for k, v in d.items()}
        log_timestamps = list(logs_json.keys())
        # check just one log entry exists
        assert_that(len(log_timestamps)).is_equal_to(1)
        try:
            datetime.datetime.strptime(log_timestamps[0], '%Y-%m-%dT%H:%M:%S.%f')
        except ValueError:
            fail('Incorrect timestamp format, should be "%Y-%m-%dT%H:%M:%S.%f"')
        key = log_timestamps[0]
        log = logs_json[key]
        assert_that(log).contains_only('session_token', 'blueprint_token', 'blueprint_id', 'job', 'state',
                                       'timestamp_start', 'timestamp_end', 'log')
        assert_that(log['session_token']).is_equal_to(session_token)
        assert_that(log['blueprint_token']).is_equal_to(blueprint_token)
        assert_that(log['blueprint_id']).is_equal_to(local_blueprint['blueprint_id'])
        assert_that(log['job']).is_equal_to('deploy')

    def test_deploy_fail(self, url):
        # corrupt blueprint so it will fail
        local_blueprint_failed = TestDeploy.corrupt_blueprint(local_blueprint)

        resp = requests.post(url=url + "/manage", json=local_blueprint_failed)
        blueprint_token = resp.json()['blueprint_token']

        # deploy and check deploy message
        resp = requests.post(url=url + "/deploy/{}".format(blueprint_token))
        assert_that(resp.json()).contains_only('message', 'session_token', 'blueprint_id', 'blueprint_token',
                                               'version_id', 'timestamp')
        assert_that(resp.json()['blueprint_token']).is_equal_to(blueprint_token)
        assert_that(resp.json()['blueprint_id']).is_equal_to(local_blueprint['blueprint_id'])
        assert_that(resp.status_code).is_equal_to(202)

        session_token = resp.json()['session_token']

        done, resp = TestDeploy.monitor(session_token, job='deploy', url=url, timeout=30)

        assert_that(done).is_true()
        assert_that(resp.json()['deploy']).is_equal_to('failed')
        assert_that(resp.status_code).is_equal_to(500)

    def test_deploy_no_inputs(self, url):

        resp = requests.post(url=url + "/manage", json=local_blueprint_inputs)
        blueprint_token = resp.json()['blueprint_token']

        # deploy and check deploy message
        resp = requests.post(url=url + "/deploy/{}".format(blueprint_token))

        session_token = resp.json()['session_token']

        done, resp = TestDeploy.monitor(session_token, job='deploy', url=url, timeout=30)
        assert_that(done).is_true()
        assert_that(resp.json()['deploy']).is_equal_to('failed')

    def test_deploy_with_inputs(self, url):

        resp = requests.post(url=url + "/manage", json=local_blueprint_inputs)
        blueprint_token = resp.json()['blueprint_token']

        fp = io.StringIO(local_inputs)
        file = FileStorage(fp)

        # deploy and check deploy message
        resp = requests.post(url=url + "/deploy/{}".format(blueprint_token), files={'inputs_file': file})

        session_token = resp.json()['session_token']

        done, resp = TestDeploy.monitor(session_token, job='deploy', url=url, timeout=30)
        assert_that(done).is_true()
        assert_that(resp.json()['deploy']).is_equal_to('done')

    def test_undeploy_no_inputs(self, url):

        # upload local template
        resp = requests.post(url=url + "/manage", json=local_blueprint_inputs)
        blueprint_token = resp.json()['blueprint_token']

        # fp = open(inputs_file_path, 'rb')
        fp = io.StringIO(local_inputs)
        file = FileStorage(fp)

        # deploy and check deploy message
        resp = requests.post(url=f"{url}/deploy/{blueprint_token}", files={'inputs_file': file})
        session_token = resp.json()['session_token']

        done, resp = TestDeploy.monitor(session_token, job='deploy', url=url, timeout=30)
        assert_that(done).is_true()
        assert_that(resp.json()['deploy']).is_equal_to('done')

        # undeploy
        resp = requests.delete(url=f"{url}/deploy/{blueprint_token}")
        session_token = resp.json()['session_token']
        assert_that(session_token).is_not_none()

        done, resp = TestDeploy.monitor(session_token, job='undeploy', url=url, timeout=30)
        assert_that(done).is_true()
        assert_that(resp.json()['undeploy']).is_equal_to('failed')

    def test_undeploy_with_inputs(self, url):

        # upload local template
        resp = requests.post(url=url + "/manage", json=local_blueprint_inputs)
        blueprint_token = resp.json()['blueprint_token']

        # fp = open(inputs_file_path, 'rb')
        fp = io.StringIO(local_inputs)
        file = FileStorage(fp)

        # deploy and check deploy message
        resp = requests.post(url=f"{url}/deploy/{blueprint_token}", files={'inputs_file': file})
        session_token = resp.json()['session_token']

        done, resp = TestDeploy.monitor(session_token, job='deploy', url=url, timeout=30)
        assert_that(done).is_true()
        assert_that(resp.json()['deploy']).is_equal_to('done')

        # undeploy
        fp = io.StringIO(local_inputs)
        file = FileStorage(fp)
        resp = requests.delete(url=f"{url}/deploy/{blueprint_token}", files={'inputs_file': file})
        session_token = resp.json()['session_token']
        assert_that(session_token).is_not_none()

        done, resp = TestDeploy.monitor(session_token, job='undeploy', url=url, timeout=30)
        assert_that(done).is_true()
        assert_that(resp.json()['undeploy']).is_equal_to('done')

    def test_undeploy(self, url):
        # upload local template
        resp = requests.post(url=url + "/manage", json=local_blueprint)
        blueprint_token = resp.json()['blueprint_token']

        # deploy and check deploy message
        resp = requests.post(url=url + "/deploy/{}".format(blueprint_token))
        session_token = resp.json()['session_token']

        done, resp = TestDeploy.monitor(session_token, job='deploy', url=url, timeout=30)
        assert_that(done).is_true()
        assert_that(resp.json()['deploy']).is_equal_to('done')

        # undeploy
        resp = requests.delete(url=url + "/deploy/{}".format(blueprint_token))
        session_token = resp.json()['session_token']

        done, resp = TestDeploy.monitor(session_token, job='undeploy', url=url, timeout=30)
        assert_that(done).is_true()
        assert_that(resp.json()['undeploy']).is_equal_to('done')


if __name__ == '__main__':
    test = TestDeploy()
    test.test_undeploy_no_inputs(url="http://localhost:5000")
