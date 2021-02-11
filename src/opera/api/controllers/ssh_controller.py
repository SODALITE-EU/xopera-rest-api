from pathlib import Path

from opera.api.openapi.models.key_pair import KeyPair
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
            return KeyPair(key_name, file_string), 200
    except FileNotFoundError:
        if Settings.key_pair == "":
            return "Ssh key pair missing", 404
        return f"Public key {key_name} not found", 404
