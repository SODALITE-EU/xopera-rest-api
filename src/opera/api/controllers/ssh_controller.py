from pathlib import Path

from opera.api.openapi.models.just_message import JustMessage
from opera.api.openapi.models.openstack_key_pair import OpenstackKeyPair
from opera.api.settings import Settings


def get_public_key():
    """
    Obtain ssh public key

    :rtype: JustMessage
    """
    key_name = Settings.key_pair
    try:
        with (Settings.ssh_keys_location / Path(f"{key_name}.pubk")).open('r') as file:
            file_string = "".join(file.readlines())
            return OpenstackKeyPair(key_name, file_string), 200
    except FileNotFoundError:
        if Settings.key_pair == "":
            return JustMessage("Openstack ssh key pair missing"), 404
        return JustMessage(f"Public key {key_name} not found"), 404
