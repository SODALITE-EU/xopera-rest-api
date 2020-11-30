import grp
import logging as log
import os
import pwd
import re
import shutil
import uuid
from pathlib import Path

from opera.api.settings import Settings


def deployment_location(session_token: uuid, blueprint_token: uuid):
    return Path(Settings.deployment_data) / Path(str(blueprint_token) / Path(str(session_token)))


def parse_path(path: Path):
    session_token = path.name
    blueprint_token = path.parent.name

    # test everything is ok
    try:
        uuid.UUID(session_token)
        uuid.UUID(blueprint_token)
    except ValueError:
        return None, None
    if not path.parent.parent == Path(Settings.deployment_data):
        return None, None
    return blueprint_token, session_token


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


def clean_deployment_data():
    if Path(Settings.deployment_data).exists():
        shutil.rmtree(Settings.deployment_data)
    os.mkdir(Settings.deployment_data)
    Path(Path(Settings.deployment_data) / Path(".gitignore")).write_text("*")


def parse_log(deploy_location: Path):
    with (deploy_location / Settings.logfile_name).open('r') as file:
        logfile = file.readlines()
        log_str = "".join(logfile[:-1]).casefold()
    try:
        status_code = int(logfile[-1])
        state = "done" if status_code == 0 else "failed"
    except ValueError:
        log.warning('Could not read xopera exit code, obtaining status from stacktrace...')
        failed_keywords = ["fail", "traceback", "error"]
        state = "failed" if len([i for i in failed_keywords if i in log_str]) != 0 else "done"

    return state, log_str


def save_version_tag(deploy_location: Path, version_tag: str):
    with (deploy_location / "version_tag").open('w') as file:
        file.write(str(version_tag))


def read_version_tag(deploy_location: Path):
    version_tag = (deploy_location / "version_tag").open('r').read()
    (deploy_location / "version_tag").unlink()
    return version_tag
