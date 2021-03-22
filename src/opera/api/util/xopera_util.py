import grp
import os
import pwd
import re
import shutil
from contextlib import contextmanager
from pathlib import Path

import connexion
import yaml

from opera.api.settings import Settings
from opera.api.log import get_logger
from opera.api.util.vault_client import get_secret


logger = get_logger(__name__)


@contextmanager
def cwd(path):
    old_pwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_pwd)


def configure_ssh_keys():
    keys = list(Settings.ssh_keys_location.glob("*xOpera*"))
    if len(keys) != 2:
        logger.error(
            "Expected exactly 2 keys (public and private) with xOpera substring in name, found {}".format(len(keys)))
        return
    try:
        private_key = [str(key) for key in keys if ".pubk" not in str(key)][0]
        public_key = [str(key) for key in keys if ".pubk" in str(key)][0]
    except IndexError:
        logger.error(
            'Wrong file extension. Public key should have ".pubk" and private key should have ".pk" or no extension '
            'at all')
        return
    public_key_check = private_key.replace(".pk", "") + ".pubk"
    if public_key != public_key_check:
        logger.error(
            'No matching private and public key pair. Public key should have ".pubk" and private key should have '
            '".pk" or no extension at all')
        return

    private_key_new, public_key_new = private_key, public_key
    ip = re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", private_key)
    if ip is not None:
        ip = ip.group()
        ip_hyphens = ip.replace(".", "-")
        private_key_new, public_key_new = private_key.replace(ip, ip_hyphens), public_key.replace(ip, ip_hyphens)

    private_key_new = private_key_new.replace(".pk", "")
    os.rename(private_key, private_key_new)
    os.rename(public_key, public_key_new)
    uid = pwd.getpwnam('root').pw_uid
    gid = grp.getgrnam('root').gr_gid
    os.chown(private_key_new, uid, gid)
    os.chmod(private_key_new, 0o400)

    config = "ConnectTimeout 5\n" \
             f"IdentityFile {private_key_new}\n" \
             "UserKnownHostsFile=/dev/null\n" \
             "StrictHostKeyChecking=no"
    Path(Path(Settings.ssh_keys_location) / Path('config')).write_text(config)

    key_pair = private_key_new.split("/")[-1]
    Settings.key_pair = key_pair
    logger.info("key '{}' added".format(Settings.key_pair))


def init_dir(dir_path: str, clean=False):
    path = Path(dir_path)
    if clean and path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def init_data():
    init_dir(Settings.STDFILE_DIR, clean=True)
    init_dir(Settings.INVOCATION_DIR)
    init_dir(Settings.DEPLOYMENT_DIR, clean=True)


def get_preprocessed_inputs():
    raw_inputs = inputs_file()
    if raw_inputs:
       return preprocess_inputs(raw_inputs, get_access_token())
    return None    


def inputs_file():
    try:
        file = connexion.request.files['inputs_file']
        return yaml.safe_load(file.read().decode('utf-8'))
    except KeyError:
        return None


def preprocess_inputs(inputs, access_token):
    refined_inputs = inputs.copy()

    for key in inputs:
        if key.startswith(Settings.vault_secret_prefix):
            logger.info("Resolving input {0}".format(key))
            path, role = inputs[key].split(':')
            if not isinstance(path, str) and not isinstance(role, str):
                raise ValueError(
                    "Incorrect input format for secret: {0}".format(
                        inputs[key]
                        )
                    )
            secret = get_secret(path, role, access_token)
            if isinstance(secret, dict):
                refined_inputs.pop(key)
                refined_inputs.update(secret)
            else:
                raise ValueError(
                    "Incorrect secret: {0} for role {1}".format(
                        path,
                        role
                        )
                    )

    return refined_inputs


def get_access_token():
    authorization = connexion.request.headers.get("Authorization")
    if not authorization:
        return None
    try:
        auth_type, token = authorization.split(None, 1)
    except ValueError:
        return None
    if auth_type.lower() != "bearer":
        return None
    return token


def mask_workdir(location: Path, stacktrace: str, placeholder="$BLUEPRINT_DIR"):
    """
    replaces real workdir with placeholder
    """
    return stacktrace.replace(str(location), placeholder)


def mask_workdirs(locations: [Path], stacktrace: str, placeholder="$BLUEPRINT_DIR"):
    """
    replaces real workdir with placeholder, for multiple locations
    """

    for location in locations:
        stacktrace = stacktrace.replace(str(location), placeholder)
    return stacktrace
