from assertpy import assert_that
from opera.api.openapi.models.invocation import Invocation, InvocationState, OperationType
from opera.api.controllers.background_invocation import InvocationService
from opera.api.util import timestamp_util
import uuid
from pathlib import Path
from opera.api.settings import Settings


class TestStatus:

    def test_missing(self, client):
        token = 'foo'
        resp = client.get(f"/info/status?token={token}")
        assert resp.status_code == 404
        assert_that(resp.json).contains_only('message')
        assert_that(resp.json['message']).contains(f'Could not find session with session_token {token}')

    def test_pending(self, client, generic_invocation: Invocation):
        inv = generic_invocation
        inv.state = InvocationState.PENDING
        InvocationService.write_invocation(inv)

        resp = client.get(f"/info/status?token={inv.session_token}")
        assert_that(resp.json['session_token'] == inv.state)
        assert resp.status_code == 202

    def test_in_progress(self, client, generic_invocation: Invocation):
        inv = generic_invocation
        inv.state = InvocationState.IN_PROGRESS
        InvocationService.write_invocation(inv)
        (Path(Settings.STDFILE_DIR) / str(inv.session_token)).mkdir(parents=True, exist_ok=True)
        (Path(Settings.STDFILE_DIR) / str(inv.session_token) / 'stdout.txt').write_text('stdout')
        (Path(Settings.STDFILE_DIR) / str(inv.session_token) / 'stderr.txt').write_text('stderr')

        resp = client.get(f"/info/status?token={inv.session_token}")
        assert_that(resp.json['session_token'] == inv.state)
        assert resp.status_code == 202

    def test_success(self, client, generic_invocation: Invocation):
        inv = generic_invocation
        inv.state = InvocationState.SUCCESS
        InvocationService.write_invocation(inv)

        resp = client.get(f"/info/status?token={inv.session_token}")
        assert_that(resp.json['session_token'] == inv.state)
        assert resp.status_code == 201

    def test_failed(self, client, generic_invocation: Invocation):
        inv = generic_invocation
        inv.state = InvocationState.FAILED
        InvocationService.write_invocation(inv)

        resp = client.get(f"/info/status?token={inv.session_token}")
        assert_that(resp.json['session_token'] == inv.state)
        assert resp.status_code == 500
