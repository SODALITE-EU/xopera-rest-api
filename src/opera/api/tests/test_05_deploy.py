import copy
import time

from assertpy import assert_that, fail

from opera.api.util import timestamp_util
from opera.api.openapi.models import InvocationState


class TestDeploy:

    @staticmethod
    def monitor(client, session_token, timeout=10):
        time_start = time.time()
        while time.time() - time_start < timeout:
            resp = client.get(f"/info/status?token={session_token}")
            if resp.json['state'] not in [InvocationState.PENDING, InvocationState.IN_PROGRESS]:
                return True, resp

            time.sleep(1)
        resp = client.get(f"/info/log/deployment?session_token={session_token}")        
        return False, resp

    def test_deploy_json_keys_error(self, client):
        resp = client.post(f"/deploy/{'42'}")
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json).is_not_none().contains_only("message")

    def test_undeploy_json_keys_error(self, client):
        resp = client.post(f"/undeploy/{'42'}")
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json).is_not_none().contains_only("message")

    def test_deploy_json_keys_success(self, client, csar_corrupt):

        resp = client.post("/manage", data=csar_corrupt)
        blueprint_token = resp.json['blueprint_token']

        # deploy and check deploy message
        resp = client.post(f"/deploy/{blueprint_token}")
        assert_that(resp.json).contains_only('session_token', 'blueprint_token',
                                             'timestamp', 'state', 'operation')
        assert_that(resp.json['blueprint_token']).is_equal_to(blueprint_token)
        assert_that(resp.status_code).is_equal_to(202)

    def test_deploy_wrong_version_tag(self, client, csar_corrupt):

        resp = client.post("/manage", data=csar_corrupt)
        blueprint_token = resp.json['blueprint_token']

        # deploy and check deploy message
        resp = client.post(f"/deploy/{blueprint_token}?version_tag=42")
        assert_that(resp.status_code).is_equal_to(404)

    def test_deploy_last_version(self, client, csar_1, csar_corrupt):

        # upload 2 different blueprints under same token
        resp_1 = client.post("/manage", data=csar_1)
        blueprint_token = resp_1.json['blueprint_token']

        # upload corrupted blueprint so it will fail and take less time
        resp_2 = client.post(f"/manage/{blueprint_token}", data=csar_corrupt)

        resp_deploy = client.post(f"/deploy/{blueprint_token}")
        assert_that(resp_deploy.status_code).is_equal_to(202)
        assert_that(resp_deploy.json).does_not_contain('version_tag')

    def test_deploy_by_version_tag(self, client, csar_1, csar_corrupt):

        # upload 2 different blueprints under same token
        resp_1 = client.post("/manage", data=csar_corrupt)
        blueprint_token = resp_1.json['blueprint_token']

        # upload corrupted blueprint so it will fail and take less time
        resp_2 = client.post(f"/manage/{blueprint_token}", data=csar_1)

        resp_deploy = client.post(f"/deploy/{blueprint_token}?version_tag={resp_1.json['version_tag']}")
        assert_that(resp_deploy.status_code).is_equal_to(202)
        assert_that(resp_deploy.json['version_tag']).is_equal_to(resp_1.json['version_tag'])
        assert_that(resp_deploy.json['blueprint_token']).is_equal_to(resp_1.json['blueprint_token'])

    def test_deploy_success(self, client, csar_1):

        # upload local template
        resp = client.post("/manage", data=csar_1)
        blueprint_token = resp.json['blueprint_token']

        # deploy and check deploy message
        resp_deploy = client.post(f"/deploy/{blueprint_token}")
        assert_that(resp_deploy.status_code).is_equal_to(202)

        session_token = resp_deploy.json['session_token']

        done, resp_status = TestDeploy.monitor(client, session_token, timeout=100)
        assert_that(done, resp_status.json).is_true()
        assert_that(resp_status.json['state']).is_equal_to(InvocationState.SUCCESS)
        assert_that(resp_status.status_code).is_equal_to(201)

        assert_that(resp_status.json).contains_only('session_token', 'blueprint_token',
                                                    'timestamp', 'state', 'operation',
                                                    'instance_state', 'stderr', 'stdout',
                                                    'exception', 'inputs', 'version_tag')
        
        # print status
        print(resp_status.json)


        # check logs

        resp_log = client.get(f"/info/log/deployment?session_token={session_token}")
        assert_that(len(resp_log.json)).is_equal_to(1)

        log = resp_log.json[0]
        print(log)
        assert_that(log).contains_only('session_token', 'blueprint_token', 'job', 'state',
                                       'timestamp_start', 'timestamp_end', 'log')
        try:
            timestamp_util.str_to_datetime(log['timestamp_start'])
            timestamp_util.str_to_datetime(log['timestamp_end'])
        except ValueError:
            fail('Incorrect timestamp format, should be "%Y-%m-%dT%H:%M:%S.%f%z"')
        assert_that(log['session_token']).is_equal_to(session_token)
        assert_that(log['blueprint_token']).is_equal_to(blueprint_token)
        assert_that(log['job']).is_equal_to('deploy')
        assert_that(log['state']).is_equal_to(InvocationState.SUCCESS)

    def test_deploy_fail(self, client, csar_corrupt):

        # upload corrupted blueprint template
        resp = client.post("/manage", data=csar_corrupt)
        blueprint_token = resp.json['blueprint_token']

        # deploy and check deploy message
        resp_deploy = client.post(f"/deploy/{blueprint_token}")
        assert_that(resp_deploy.status_code).is_equal_to(202)
        session_token = resp_deploy.json['session_token']

        done, resp_status = TestDeploy.monitor(client, session_token, timeout=100)

        assert_that(done).is_true()
        assert_that(resp_status.json['state']).is_equal_to('failed')
        assert_that(resp_status.status_code).is_equal_to(500)

    def test_deploy_no_inputs(self, client, csar_inputs):

        # upload corrupted blueprint template
        resp = client.post("/manage", data=csar_inputs)
        blueprint_token = resp.json['blueprint_token']

        # deploy and check deploy message
        resp_deploy = client.post(f"/deploy/{blueprint_token}")
        assert_that(resp_deploy.status_code).is_equal_to(202)
        session_token = resp_deploy.json['session_token']

        done, resp_status = TestDeploy.monitor(client, session_token, timeout=100)

        assert_that(done).is_true()
        assert_that(resp_status.json['state']).is_equal_to('failed')
        assert_that(resp_status.status_code).is_equal_to(500)

    def test_deploy_with_inputs(self, client, csar_inputs, inputs_1):

        resp = client.post("/manage", data=csar_inputs)
        blueprint_token = resp.json['blueprint_token']

        # deploy with inputs and check deploy message
        resp = client.post(f"/deploy/{blueprint_token}", data=inputs_1)

        session_token = resp.json['session_token']

        done, resp = TestDeploy.monitor(client, session_token, timeout=100)
        assert_that(done).is_true()
        assert_that(resp.json['state']).is_equal_to(InvocationState.SUCCESS)

    def test_undeploy_no_inputs(self, client, csar_inputs, inputs_1):

        resp = client.post("/manage", data=csar_inputs)
        blueprint_token = resp.json['blueprint_token']

        # deploy with inputs and check deploy message
        resp = client.post(f"/deploy/{blueprint_token}", data=inputs_1)

        session_token = resp.json['session_token']

        done, resp = TestDeploy.monitor(client, session_token, timeout=100)
        assert_that(done).is_true()
        assert_that(resp.json['state']).is_equal_to(InvocationState.SUCCESS)

        # undeploy
        resp = client.post(f"/undeploy/{blueprint_token}")
        session_token = resp.json['session_token']
        assert_that(session_token).is_not_none()

        done, resp = TestDeploy.monitor(client, session_token, timeout=100)
        assert_that(done).is_true()
        assert_that(resp.json['state']).is_equal_to('failed')

    def test_undeploy_with_inputs(self, client, csar_inputs, inputs_1, inputs_2):

        resp = client.post("/manage", data=csar_inputs)
        blueprint_token = resp.json['blueprint_token']

        # deploy with inputs and check deploy message
        resp = client.post(f"/deploy/{blueprint_token}", data=inputs_1)

        session_token = resp.json['session_token']

        done, resp = TestDeploy.monitor(client, session_token, timeout=100)
        assert_that(done).is_true()
        assert_that(resp.json['state']).is_equal_to(InvocationState.SUCCESS)

        # undeploy
        resp = client.post(f"/undeploy/{blueprint_token}", data=inputs_2)
        session_token = resp.json['session_token']
        assert_that(session_token).is_not_none()

        done, resp = TestDeploy.monitor(client, session_token, timeout=100)
        assert_that(done).is_true()
        assert_that(resp.json['state']).is_equal_to(InvocationState.SUCCESS)

    def test_undeploy(self, client, csar_1):
        # upload corrupted blueprint template
        resp = client.post("/manage", data=csar_1)
        blueprint_token = resp.json['blueprint_token']

        # deploy and check deploy message
        resp_deploy = client.post(f"/deploy/{blueprint_token}")
        assert_that(resp_deploy.status_code).is_equal_to(202)
        session_token = resp_deploy.json['session_token']

        done, resp_status = TestDeploy.monitor(client, session_token, timeout=100)

        assert_that(done).is_true()
        assert_that(resp_status.json['state']).is_equal_to(InvocationState.SUCCESS)
        assert_that(resp_status.status_code).is_equal_to(201)

        # undeploy
        resp = client.post(f"/undeploy/{blueprint_token}")
        session_token = resp.json['session_token']

        done, resp_status = TestDeploy.monitor(client, session_token, timeout=100)
        assert_that(done).is_true()
        assert_that(resp_status.json['state']).is_equal_to(InvocationState.SUCCESS)

    def test_undeploy_before_deploy(self, client, csar_1):

        resp = client.post("/manage", data=csar_1)
        blueprint_token = resp.json['blueprint_token']

        # try_to_undeploy
        resp = client.post(f"/undeploy/{blueprint_token}")
        assert_that(resp.status_code).is_equal_to(403)

    # def test_deploy_clean(self, client, csar_clean_state):
    #     # TODO this test does not make any sense, remove it
    #     resp = client.post("/manage", data=csar_clean_state)
    #     blueprint_token = resp.json['blueprint_token']
    #
    #     # deploy and check deploy message
    #     resp_deploy = client.post(f"/deploy/{blueprint_token}")
    #     assert_that(resp_deploy.status_code).is_equal_to(202)
    #     session_token = resp_deploy.json['session_token']
    #
    #     done, resp_status = self.monitor(client, session_token, timeout=100)
    #     assert_that(done).is_true()
    #     print(resp_status.json)
    #     assert_that(resp_status.json['state']).is_equal_to(InvocationState.SUCCESS)
    #     assert_that(resp_status.status_code).is_equal_to(201)
    #     resp_log = client.get(f"/info/log/deployment?session_token={session_token}")
    #     print(resp_log.json)
    #     log_message = resp_log.json[0]['log']
    #     assert_that(log_message).contains('deployment of my-workstation_0 complete')
