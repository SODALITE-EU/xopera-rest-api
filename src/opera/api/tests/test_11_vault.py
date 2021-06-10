from unittest.mock import MagicMock

import pytest

from opera.api.util.vault_client import get_secret


class TestVault:

    def test_get_secret_no_token(self):
        with pytest.raises(ValueError):
            get_secret("", "", None)

    def test_get_secret(self, mocker):
        def get_json():
            return {
                "data":
                    {
                        "ssh_key": "test"
                    }
            }

        get_response = MagicMock()
        get_response.json = get_json
        mocker.patch("opera.api.util.vault_client.session.get",
                     return_value=get_response)
        mocker.patch("opera.api.util.vault_client.session.post")
        result = get_secret("pds/test", "pds", "ACCESS_TOKEN")
        assert len(result) == 1
        assert result["ssh_key"] == "test"
