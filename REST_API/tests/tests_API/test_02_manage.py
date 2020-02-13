import datetime
import time
import uuid

import requests
from assertpy import assert_that, fail

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


class TestPostNew:

    def test_empty(self, url):
        payload = {}
        resp = requests.post(url=url + "/manage", data=payload)
        assert_that(resp.status_code).is_equal_to(406)
        assert_that(resp.json()).is_not_none().contains_only("message")

    def test_no_id(self, url):

        payload_no_id = {i: payload_generic[i] for i in payload_generic if i != 'blueprint_id'}

        resp = requests.post(url=url + "/manage", json=payload_no_id)
        assert_that(resp.status_code).is_equal_to(406)
        assert_that(resp.json()).is_not_none().contains_only("message")

    def test_no_tosca(self, url):

        payload_no_tosca = {i: payload_generic[i] for i in payload_generic if i != 'tosca_definition'}

        resp = requests.post(url=url + "/manage", json=payload_no_tosca)
        assert_that(resp.status_code).is_equal_to(406)
        assert_that(resp.json()).is_not_none().contains_only("message")

    def test_no_ansible(self, url):

        payload_no_ansible = {i: payload_generic[i] for i in payload_generic if i != 'ansible_definition'}

        resp = requests.post(url=url + "/manage", json=payload_no_ansible)
        assert_that(resp.status_code).is_equal_to(406)
        assert_that(resp.json()).is_not_none().contains_only("message")

    def test_success(self, url):
        resp = requests.post(url=url + "/manage", json=payload_generic)
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json()).is_not_none().contains_only("message", 'id', 'blueprint_token', 'version_id',
                                                             'timestamp')
        try:
            uuid.UUID(resp.json()['blueprint_token'])
        except ValueError:
            fail('"blueprint_token" from response is not uuid')

        assert_that(resp.json()['version_id']).is_equal_to(1)

        try:
            datetime.datetime.strptime(resp.json()['timestamp'], '%Y-%m-%dT%H:%M:%S.%f')
        except ValueError:
            fail('Incorrect timestamp format, should be "%Y-%m-%dT%H:%M:%S.%f"')

    def test_invalid_blueprint_id(self, url):
        payload = {**payload_generic, 'blueprint_id': "aaa.111"}
        resp = requests.post(url=url + "/manage", json=payload)
        assert_that(resp.status_code).is_equal_to(406)


class TestPostMultipleVersions:

    def test_wrong_token(self, url):
        token = "ahaha"
        resp = requests.post(url=url + "/manage/{}".format(token), json=payload_generic)
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json()).is_not_none().contains_only("message")

    def test_emtpy_request(self, url):
        # prepare blueprint
        resp = requests.post(url=url + "/manage", json=payload_generic)
        token = resp.json()['blueprint_token']
        # test empty request
        resp = requests.post(url=url + "/manage/{}".format(token), json={})
        assert_that(resp.status_code).is_equal_to(406)
        assert_that(resp.json()).is_not_none().contains_only("message")

    def test_success(self, url):
        # prepare first blueprint
        resp = requests.post(url=url + "/manage", json=payload_generic)
        token = resp.json()['blueprint_token']
        # test new version
        resp = requests.post(url=url + "/manage/{}".format(token), json=payload_generic)
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json()).is_not_none().contains_only("message", 'id', 'blueprint_token', 'version_id',
                                                             'timestamp')
        assert_that(resp.json()['version_id']).is_equal_to(2)

    def test_invalid_blueprint_id(self, url):
        resp = requests.post(url=url + "/manage", json=payload_generic)
        token = resp.json()['blueprint_token']

        payload = {**payload_generic, 'blueprint_id': "aaa.111"}
        resp = requests.post(url=url + "/manage/{}".format(token), json=payload)
        assert_that(resp.status_code).is_equal_to(406)


class TestGet:

    def test_json_keys_error(self, url):
        resp = requests.post(url=url + "/manage/{}".format('a'))
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json()).is_not_none().contains_only("message")

    def test_json_keys_success(self, url):
        resp = requests.post(url=url + "/manage", json=payload_generic)
        token = resp.json()['blueprint_token']

        resp = requests.get(url=url + "/manage/{}".format(token))
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json()).is_not_none().contains_only('blueprint_id', 'tosca_definition', 'ansible_definition',
                                                             'rc_file', 'blueprint_token', 'version_id', 'timestamp')

    def test_get_by_wrong_timestamp(self, url):
        resp = requests.post(url=url + "/manage", json=payload_generic)
        token = resp.json()['blueprint_token']

        resp = requests.get(url=url + "/manage/{}".format(token), params={'timestamp': 1})
        assert_that(resp.status_code).is_equal_to(404)

    def test_get_by_wrong_version_id(self, url):
        resp = requests.post(url=url + "/manage", json=payload_generic)
        token = resp.json()['blueprint_token']

        resp = requests.get(url=url + "/manage/{}".format(token), params={'version_id': 42})
        assert_that(resp.status_code).is_equal_to(404)

    def test_get_by_wrong_timestamp_and_version_id(self, url):
        resp = requests.post(url=url + "/manage", json=payload_generic)
        token = resp.json()['blueprint_token']

        resp = requests.get(url=url + "/manage/{}".format(token), params={'timestamp': 1, 'version_id': 42})
        assert_that(resp.status_code).is_equal_to(404)

    def test_get_last_version(self, url):
        # create 4 different payloads and upload them under same token
        payloads = [{**payload_generic, 'blueprint_id': "id_{}_id".format(i + 1)} for i in range(4)]
        resp = requests.post(url=url + "/manage", json=payloads[0])
        token = resp.json()['blueprint_token']
        responses = [resp] + [requests.post(url=url + "/manage/{}".format(token), json=payloads[i + 1]) for i in
                              range(3)]

        last_json = responses[-1].json()
        last_payload = payloads[-1]
        resp = requests.get(url=url + "/manage/{}".format(token))
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(int(resp.json()['version_id'])).is_equal_to(int(last_json['version_id']))
        assert_that(resp.json()['timestamp']).is_equal_to(last_json['timestamp'])
        assert_that(resp.json()['blueprint_id']).is_equal_to(last_payload['blueprint_id'])

    def test_get_by_version_id(self, url):
        # create 4 different payloads and upload them under same token
        payloads = [{**payload_generic, 'blueprint_id': "id_{}_id".format(i + 1)} for i in range(4)]
        resp = requests.post(url=url + "/manage", json=payloads[0])
        token = resp.json()['blueprint_token']
        responses = [resp] + [requests.post(url=url + "/manage/{}".format(token), json=payloads[i + 1]) for i in
                              range(3)]

        json_3 = responses[2].json()
        payload_3 = payloads[2]
        resp = requests.get(url=url + "/manage/{}".format(token), params={'version_id': int(json_3['version_id'])})
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(int(resp.json()['version_id'])).is_equal_to(int(json_3['version_id']))
        assert_that(resp.json()['timestamp']).is_equal_to(json_3['timestamp'])
        assert_that(resp.json()['blueprint_id']).is_equal_to(payload_3['blueprint_id'])

    def test_get_by_timestamp(self, url):
        # create 4 different payloads and upload them under same token
        payloads = [{**payload_generic, 'blueprint_id': "id_{}_id".format(i + 1)} for i in range(4)]
        resp = requests.post(url=url + "/manage", json=payloads[0])
        token = resp.json()['blueprint_token']
        responses = [resp] + [requests.post(url=url + "/manage/{}".format(token), json=payloads[i + 1]) for i in
                              range(3)]

        json_2 = responses[1].json()
        payload_2 = payloads[1]
        resp = requests.get(url=url + "/manage/{}".format(token), params={'timestamp': json_2['timestamp']})
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(int(resp.json()['version_id'])).is_equal_to(int(json_2['version_id']))
        assert_that(resp.json()['timestamp']).is_equal_to(json_2['timestamp'])
        assert_that(resp.json()['blueprint_id']).is_equal_to(payload_2['blueprint_id'])


class TestDelete:

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

    def test_json_keys_error(self, url):
        resp = requests.delete(url=url + "/manage/{}".format('a'))
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json()).is_not_none().contains_only("message", 'blueprint_token', 'version_id', 'timestamp',
                                                             'deleted_database_entries', 'force')

    def test_json_keys_success(self, url):
        resp = requests.post(url=url + "/manage", json=payload_generic)
        token = resp.json()['blueprint_token']

        resp = requests.delete(url=url + "/manage/{}".format(token))
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json()).is_not_none().contains_only("message", 'blueprint_token', 'version_id', 'timestamp',
                                                             'deleted_database_entries', 'force')

    def test_wrong_timestamp(self, url):
        resp = requests.post(url=url + "/manage", json=payload_generic)
        token = resp.json()['blueprint_token']

        resp = requests.delete(url=url + "/manage/{}".format(token), params={'timestamp': 1})
        assert_that(resp.status_code).is_equal_to(404)

    def test_wrong_version_id(self, url):
        resp = requests.post(url=url + "/manage", json=payload_generic)
        token = resp.json()['blueprint_token']

        resp = requests.delete(url=url + "/manage/{}".format(token), params={'version_id': 42})
        assert_that(resp.status_code).is_equal_to(404)

    def test_wrong_timestamp_and_version_id(self, url):
        resp = requests.post(url=url + "/manage", json=payload_generic)
        token = resp.json()['blueprint_token']

        resp = requests.delete(url=url + "/manage/{}".format(token), params={'timestamp': 1, 'version_id': 42})
        assert_that(resp.status_code).is_equal_to(404)

    def test_all_versions(self, url):
        # upload 4 times under same token
        resp = requests.post(url=url + "/manage", json=payload_generic)
        token = resp.json()['blueprint_token']
        responses = [resp] + [requests.post(url=url + "/manage/{}".format(token), json=payload_generic) for i in
                              range(3)]

        resp = requests.delete(url=url + "/manage/{}".format(token))
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(int(resp.json()['deleted_database_entries'])).is_equal_to(4)
        assert_that(resp.json()['blueprint_token']).is_equal_to(token)

    def test_version_id(self, url):
        # upload 3 times under same token
        resp = requests.post(url=url + "/manage", json=payload_generic)
        token = resp.json()['blueprint_token']
        responses = [resp] + [requests.post(url=url + "/manage/{}".format(token), json=payload_generic) for i in
                              range(2)]

        json_2 = responses[1].json()
        resp = requests.delete(url=url + "/manage/{}".format(token), params={'version_id': int(json_2['version_id'])})
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json()['blueprint_token']).is_equal_to(token)
        assert_that(int(resp.json()['version_id'])).is_equal_to(int(json_2['version_id']))
        assert_that(resp.json()['timestamp']).is_equal_to('any')
        assert_that(int(resp.json()['deleted_database_entries'])).is_equal_to(1)

    def test_timestamp(self, url):
        # upload 3 times under same token
        resp = requests.post(url=url + "/manage", json=payload_generic)
        token = resp.json()['blueprint_token']
        responses = [resp] + [requests.post(url=url + "/manage/{}".format(token), json=payload_generic) for i in
                              range(2)]

        json_2 = responses[1].json()
        resp = requests.delete(url=url + "/manage/{}".format(token), params={'timestamp': json_2['timestamp']})
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json()['blueprint_token']).is_equal_to(token)
        assert_that(resp.json()['version_id']).is_equal_to('any')
        assert_that(resp.json()['timestamp']).is_equal_to(json_2['timestamp'])
        assert_that(int(resp.json()['deleted_database_entries'])).is_equal_to(1)

    def test_delete_before_undeploy(self, url):
        # upload local template
        resp = requests.post(url=url + "/manage", json=local_blueprint)
        blueprint_token = resp.json()['blueprint_token']

        # deploy and check deploy message
        resp = requests.post(url=url + "/deploy/{}".format(blueprint_token))
        session_token = resp.json()['session_token']

        # check it is done
        done, resp = TestDelete.monitor(session_token, job='deploy', url=url, timeout=30)
        assert_that(done).is_true()
        assert_that(resp.json()['deploy']).is_equal_to('done')

        # try to delete
        resp = requests.delete(url=url + "/manage/{}".format(blueprint_token))
        assert_that(resp.status_code).is_equal_to(403)

    def test_delete_after_undeploy(self, url):
        # upload local template
        resp = requests.post(url=url + "/manage", json=local_blueprint)
        blueprint_token = resp.json()['blueprint_token']

        # deploy and check deploy message
        resp = requests.post(url=url + "/deploy/{}".format(blueprint_token))
        session_token = resp.json()['session_token']

        # check it is done
        done, resp = TestDelete.monitor(session_token, job='deploy', url=url, timeout=30)
        assert_that(done).is_true()
        assert_that(resp.json()['deploy']).is_equal_to('done')

        # undeploy
        resp = requests.delete(url=url + "/deploy/{}".format(blueprint_token))
        session_token = resp.json()['session_token']

        # check it is done
        done, resp = TestDelete.monitor(session_token, job='undeploy', url=url, timeout=30)
        assert_that(done).is_true()
        assert_that(resp.json()['undeploy']).is_equal_to('done')

        # try to delete
        resp = requests.delete(url=url + "/manage/{}".format(blueprint_token))
        assert_that(resp.status_code).is_equal_to(200)

    def test_force_delete(self, url):
        # upload local template
        resp = requests.post(url=url + "/manage", json=local_blueprint)
        blueprint_token = resp.json()['blueprint_token']

        # deploy and check deploy message
        resp = requests.post(url=url + "/deploy/{}".format(blueprint_token))
        session_token = resp.json()['session_token']

        # check it is done
        done, resp = TestDelete.monitor(session_token, job='deploy', url=url, timeout=30)
        assert_that(done).is_true()
        assert_that(resp.json()['deploy']).is_equal_to('done')

        # try to delete with force
        resp = requests.delete(url=url + "/manage/{}".format(blueprint_token), params={'force': True})
        assert_that(resp.status_code).is_equal_to(200)


if __name__ == '__main__':
    test = TestPostNew()
    test.test_empty(url="http://localhost:5000")
