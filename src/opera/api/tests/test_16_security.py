import pytest

from opera.api.controllers import security_controller


class TestSecurity:
    def test_validate_scope(self):
        assert security_controller.validate_scope(None, None) is True
        assert security_controller.validate_scope([], []) is True
        assert security_controller.validate_scope(["test"], None) is True

    def test_token_info(self, mocker):
        mock = mocker.MagicMock()
        mock.ok = False
        mocker.patch("opera.api.controllers.security_controller.session.post", return_value=mock)
        result = security_controller.token_info("ACCESS_TOKEN")
        assert result == None
        mock.ok = True
        mock.json.return_value = {'active': False}
        result = security_controller.token_info("ACCESS_TOKEN")
        assert result == None
        mock.json.return_value={'scope': ['email']}
        result = security_controller.token_info("ACCESS_TOKEN")
        assert result["scope"][0] == 'email'

    def test_get_token(self, mocker):
        mock = mocker.MagicMock()
        mock.headers = {"Authorization": "Bearer TEST_TOKEN"}
        token = security_controller.get_access_token(mock)
        assert token == "TEST_TOKEN"

        mock.headers = {}
        token = security_controller.get_access_token(mock)
        assert token == None

        mock.headers = {"Authorization": "BearerTEST_TOKEN"}
        token = security_controller.get_access_token(mock)
        assert token == None

        mock.headers = {"Authorization": "None TEST_TOKEN"}
        token = security_controller.get_access_token(mock)
        assert token == None
