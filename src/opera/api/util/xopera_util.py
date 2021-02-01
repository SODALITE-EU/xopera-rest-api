import grp
import logging as log
import os
import pwd
import re
import shutil
from contextlib import contextmanager
from pathlib import Path

import connexion
import yaml

from opera.api.settings import Settings


@contextmanager
def cwd(path):
    oldpwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(oldpwd)


def configure_ssh_keys():
    keys = list(Settings.ssh_keys_location.glob("*xOpera*"))
    if len(keys) != 2:
        log.error(
            "Expected exactly 2 keys (public and private) with xOpera substring in name, found {}".format(len(keys)))
        return
    try:
        private_key = [str(key) for key in keys if ".pubk" not in str(key)][0]
        public_key = [str(key) for key in keys if ".pubk" in str(key)][0]
    except IndexError:
        log.error(
            'Wrong file extention. Public key should have ".pubk" and private key should have ".pk" or no extension '
            'at all')
        return
    public_key_check = private_key.replace(".pk", "") + ".pubk"
    if public_key != public_key_check:
        log.error(
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
    log.info("key '{}' added".format(Settings.key_pair))


def init_dir(dir_path: str, clean=False):
    path = Path(dir_path)
    if clean and path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def init_data():
    init_dir(Settings.STDFILE_DIR, clean=True)
    init_dir(Settings.INVOCATION_DIR)
    init_dir(Settings.DEPLOYMENT_DIR, clean=True)


def inputs_file():
    try:
        file = connexion.request.files['inputs_file']
        return yaml.safe_load(file.read().decode('utf-8'))
    except KeyError:
        return None


def mask_workdir(location: Path, stacktrace: str, placeholder="$BLUEPRINT_DIR"):
    """
    replaces real workdir with placehodler
    """
    return stacktrace.replace(str(location), placeholder)
