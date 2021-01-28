import uuid

import validators
from assertpy import assert_that, fail

from opera.api.util import git_util


class TestPostNew:

    def test_empty(self, client, csar_empty):

        resp = client.post("/manage", data=csar_empty, content_type='multipart/form-data')
        assert_that(resp.status_code).is_equal_to(406)
        assert_that(resp.json).is_not_none().contains_only("message")

    def test_no_metadata(self, client, csar_no_meta):
        resp = client.post("/manage", data=csar_no_meta, content_type='multipart/form-data')
        assert_that(resp.status_code).is_equal_to(406)
        assert_that(resp.json).is_not_none().contains_only("message")

    def test_success(self, client, csar_1):
        resp = client.post("/manage", data=csar_1)
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json).is_not_none().contains_only("message", 'blueprint_token', 'url',
                                                           'version_tag', 'users', 'commit_sha', 'timestamp')
        uuid.UUID(resp.get_json()['blueprint_token'])

        assert_that(resp.get_json()['version_tag']).is_equal_to('v1.0')

        validators.url(resp.get_json()['url'])


class TestPostMultipleVersions:

    def test_wrong_token(self, client, csar_1):
        token = "42"
        resp = client.post("/manage/{}".format(token), data=csar_1)
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json).is_not_none().contains_only("message")

    def test_emtpy_request(self, client, csar_empty, csar_1):
        # prepare blueprint
        resp = client.post("/manage", data=csar_1)
        assert_that(resp.status_code).is_equal_to(200)
        token = resp.json['blueprint_token']

        resp = client.post("/manage/{}".format(token), data=csar_empty, content_type='multipart/form-data')
        assert_that(resp.status_code).is_equal_to(406)
        assert_that(resp.json).is_not_none().contains_only("message")

    def test_success(self, client, csar_1, csar_2):
        # prepare first blueprint
        resp1 = client.post("/manage", data=csar_1)
        token = resp1.json['blueprint_token']
        # test new version
        resp2 = client.post(f"/manage/{token}", data=csar_2)
        assert_that(resp2.status_code).is_equal_to(200)
        assert_that(resp2.json).is_not_none().contains_only("message", 'blueprint_token', 'url',
                                                            'version_tag', 'users', 'commit_sha', 'timestamp')
        assert_that(resp2.json['version_tag']).is_equal_to('v2.0')


class TestDelete:

    def test_json_keys_error(self, client):
        resp = client.delete(f"/manage/{42}")
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json).is_not_none().contains_only("message", 'blueprint_token', 'version_tag',
                                                           'deleted_database_entries', 'force')

    def test_json_keys_success(self, client, csar_1):
        resp = client.post("/manage", data=csar_1)
        token = resp.json['blueprint_token']

        resp = client.delete(f"/manage/{token}")
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json).is_not_none().contains_only("message", 'blueprint_token', 'version_tag',
                                                           'deleted_database_entries', 'force')

    def test_delete_by_wrong_version_tag(self, client, csar_1):
        resp = client.post("/manage", data=csar_1)
        token = resp.json['blueprint_token']

        resp = client.delete(f"/manage/{token}?version_tag={42}")
        assert_that(resp.status_code).is_equal_to(404)

    def test_delete_all_versions(self, client, csar_1, csar_2, csar_3):
        # upload 3 times under same token
        resp = client.post("/manage", data=csar_1)
        token = resp.json['blueprint_token']
        client.post(f"/manage/{token}", data=csar_2)
        client.post(f"/manage/{token}", data=csar_3)

        resp = client.delete(f"/manage/{token}")
        assert_that(resp.status_code).is_equal_to(200)
        assert_that(resp.json['deleted_database_entries']).is_equal_to(3)
        assert_that(resp.json['blueprint_token']).is_equal_to(token)

    def test_delete_by_version_tag(self, client, csar_1, csar_2, csar_3):
        # upload 3 times under same token
        resp_1 = client.post("/manage", data=csar_1)
        token = resp_1.json['blueprint_token']

        resp_2 = client.post(f"/manage/{token}", data=csar_2)
        client.post(f"/manage/{token}", data=csar_3)

        resp_delete = client.delete(f"/manage/{token}?version_tag={resp_2.json['version_tag']}")
        assert_that(resp_delete.status_code).is_equal_to(200)
        assert_that(resp_delete.json['blueprint_token']).is_equal_to(token)
        assert_that(resp_delete.json['version_tag']).is_equal_to(resp_2.json['version_tag'])
        assert_that(int(resp_delete.json['deleted_database_entries'])).is_equal_to(1)

    def test_delete_before_undeploy(self, client, csar_1, csar_2):
        # upload local blueprint
        resp = client.post(f"/manage", data=csar_1)
        blueprint_token = resp.json['blueprint_token']

        # upload again, mock revision_msg after deploy
        client.post(f"/manage/{blueprint_token}?revision_msg="
                    f"{git_util.after_job_commit_msg(token=blueprint_token, mode='deploy')}", data=csar_2)

        # try to delete
        resp = client.delete(f"/manage/{blueprint_token}")
        assert_that(resp.status_code).is_equal_to(403)

    def test_delete_before_undeploy_version_tag(self, client, csar_1, csar_2, csar_3):
        # upload local blueprint
        resp = client.post(f"/manage", data=csar_1)
        blueprint_token = resp.json['blueprint_token']

        # upload again, mock revision_msg after deploy
        resp = client.post(f"/manage/{blueprint_token}?revision_msg="
                           f"{git_util.after_job_commit_msg(token=blueprint_token, mode='deploy')}", data=csar_2)
        version_tag = resp.json['version_tag']
        # upload again, mock revision_msg after undeploy
        client.post(f"/manage/{blueprint_token}?revision_msg="
                    f"{git_util.after_job_commit_msg(token=blueprint_token, mode='undeploy')}", data=csar_3)

        # try to delete 2nd revision (deploy)
        resp = client.delete(f"/manage/{blueprint_token}?version_tag={version_tag}")
        assert_that(resp.status_code).is_equal_to(403)

    def test_delete_after_undeploy(self, client, csar_1, csar_2):
        # upload local blueprint
        resp = client.post(f"/manage", data=csar_1)
        blueprint_token = resp.json['blueprint_token']

        # upload again, mock revision_msg after undeploy
        client.post(f"/manage/{blueprint_token}?revision_msg="
                    f"{git_util.after_job_commit_msg(token=blueprint_token, mode='undeploy')}", data=csar_2)

        # try to delete
        resp = client.delete(f"/manage/{blueprint_token}")
        assert_that(resp.status_code).is_equal_to(200)

    def test_force_delete(self, client, csar_1, csar_2):
        # upload local blueprint
        resp = client.post(f"/manage", data=csar_1)
        blueprint_token = resp.json['blueprint_token']

        # upload again, mock revision_msg after deploy
        client.post(f"/manage/{blueprint_token}?revision_msg="
                    f"{git_util.after_job_commit_msg(token=blueprint_token, mode='deploy')}", data=csar_2)

        # try to delete with force
        resp = client.delete(f"/manage/{blueprint_token}?force={True}")
        assert_that(resp.status_code).is_equal_to(200)


class TestUser:

    def test_get_users_non_existing_blueprint(self, client):
        blueprint_token = '42'
        resp = client.get(f"/manage/{blueprint_token}/user")
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json).contains_only('message')
        assert_that(resp.json['message']).is_equal_to('Blueprint with token 42 does not exist')

    def test_add_users_to_non_existing_blueprint(self, client):
        blueprint_token = '42'
        resp = client.post(f"/manage/{blueprint_token}/user?username=foo")
        assert_that(resp.status_code).is_equal_to(404)
        assert_that(resp.json['message']).is_equal_to('Blueprint with token 42 does not exist')

    def test_add_user(self, client, csar_1):
        # upload local blueprint
        resp = client.post(f"/manage", data=csar_1)
        blueprint_token = resp.json['blueprint_token']
        resp = client.get(f"/manage/{blueprint_token}/user")

        assert_that(resp.json['collaborators']).is_empty()
        assert_that(resp.json['blueprint_token']).is_equal_to(blueprint_token)

        username = 'foo'
        resp = client.post(f"/manage/{blueprint_token}/user?username={username}")
        # since this is MockConnector, message should be 'user foo added'
        assert_that(resp.json['message']).is_equal_to('user foo added')
        assert_that(resp.status_code).is_equal_to(201)

        resp = client.get(f"/manage/{blueprint_token}/user")
        assert_that(resp.json['collaborators']).is_not_empty().is_equal_to(['foo'])
