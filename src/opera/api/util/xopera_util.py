import grp
import os
import pwd
import re
import shutil
import subprocess
import atexit
import tempfile
from contextlib import contextmanager
from pathlib import Path
from cryptography.hazmat.primitives import serialization

import connexion
import yaml

from opera.api.log import get_logger
from opera.api.settings import Settings
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


def setup_agent():
    process = subprocess.run(["/usr/bin/ssh-agent", "-s"],
                             stdout=subprocess.PIPE,
                             universal_newlines=True)
    OUTPUT_PATTERN = re.compile("SSH_AUTH_SOCK=(?P<socket>[^;]+).*SSH_AGENT_PID=(?P<pid>\d+)", re.MULTILINE | re.DOTALL )
    match = OUTPUT_PATTERN.search(process.stdout)
    if match is None:
        raise ValueError("Could not parse ssh-agent output. It was: {}".format(process.stdout))
    agent_data = match.groupdict()
    logger.debug("ssh agent data: {}".format(agent_data))
    logger.debug("exporting ssh agent environment variables")
    os.environ["SSH_AUTH_SOCK"] = agent_data["socket"]
    os.environ["SSH_AGENT_PID"] = agent_data["pid"]
    atexit.register(kill_agent)


def kill_agent():
    logger.debug("killing previously started ssh-agent")
    subprocess.run(["/usr/bin/ssh-agent", "-k"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    del os.environ["SSH_AUTH_SOCK"]
    del os.environ["SSH_AGENT_PID"]


def add_key(key: str):
    process = subprocess.run(['/usr/bin/ssh-add', '-'], input=key, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if process.returncode != 0:
        logger.error( "Failed to add SSH key.")


def setup_user(locations: list, username: str, access_token: str):
    if not validate_username(username):
        raise ValueError("Username {} contains illegal characters".format(username))

    try:
        user = pwd.getpwnam(username)
    except KeyError:
        user = create_user(username)

    tmp = (locations[0] / "tmp")
    os.mkdir(tmp)
    for location in locations:
        setup_user_dir(location, user.pw_uid, user.pw_gid)

    tempfile.tempdir = str(tmp)

    os.environ["ANSIBLE_LOCAL_TEMP"] = str(tmp)
    os.environ["HOME"] = user.pw_dir
    os.environ["USERNAME"] = username
    os.environ["USER"] = username
    os.environ["LOGNAME"] = username

    os.setgid(user.pw_gid)
    os.setuid(user.pw_uid)

    if access_token:
        try:
            setup_user_keys(username, access_token)

        except Exception as e:
            logger.warn( "An error occurred adding SSH key: " + str(e))


def create_user(username: str):
    subprocess.run(["/usr/sbin/adduser", "--system", username], stdout=subprocess.DEVNULL)
    user = pwd.getpwnam(username)
    user_ssh_path = Path(user.pw_dir + "/.ssh")
    shutil.copytree(Settings.ssh_keys_location, user_ssh_path, dirs_exist_ok=True)
    if Settings.key_pair:
        config = "ConnectTimeout 5\n" \
                f"IdentityFile {Path(user_ssh_path / Settings.key_pair)}\n" \
                "UserKnownHostsFile=/dev/null\n" \
                "StrictHostKeyChecking=no"
        Path(user_ssh_path / Path('config')).write_text(config)
    setup_user_dir(user_ssh_path, user.pw_uid, user.pw_gid)
    return user


def cleanup_user():
    kill_agent()


def setup_user_keys(username: str, access_token: str):
    ssh_key = get_secret(Settings.ssh_key_path_template.format(username=username), username, access_token)
    if ssh_key:
        setup_agent()
        for key in ssh_key.values():
            if vaildate_key(key):
                add_key(key)
            else:
                logger.warn("Provided key value is not a valid SSH key.")


def setup_user_dir(location: Path, user_id: int, group_id: int):
    os.chown(location, user_id, group_id)
    os.chmod(location, 0o700)
    for root, dirs, files in os.walk(location):
        for ndir in dirs:
            os.chown(os.path.join(root, ndir), user_id, group_id)
            os.chmod(os.path.join(root, ndir), 0o700)
        for nfile in files:
            os.chown(os.path.join(root, nfile), user_id, group_id)
            os.chmod(os.path.join(root, nfile), 0o700)


def vaildate_key(key: str):
    try:
        serialization.load_ssh_private_key(str.encode(key), password=None)
        return True
    except ValueError:
        pass

    try:
        serialization.load_pem_private_key(str.encode(key), password=None)
        return True
    except ValueError:
        pass

    return False


def validate_username(username: str):
    if re.match(r"^[a-zA-Z0-9_-]*$", username):
        return True
    return False
