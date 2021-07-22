import functools
import logging
import re
from base64 import b64encode

import connexion
import requests

from opera.api.cli import CSAR_db, SQL_database
from opera.api.settings import Settings

# use connection pool for OAuth tokeninfo
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
session = requests.Session()
for protocol in Settings.connection_protocols:
    session.mount(protocol, adapter)

role_regex = r"(?P<domain>\w+)_(?P<type>\w+)_(?P<permissions>\w)"
AADM_SUFFIX = "aadm"
RM_SUFFIX = "rm"


def check_api_key(apikey, required_scopes=None):
    if not Settings.apiKey or apikey != Settings.apiKey:
        return None

    return {'scope': ['apiKey']}


def token_info(access_token) -> dict:
    request = {'token': access_token}
    headers = {'Content-type': 'application/x-www-form-urlencoded'}
    token_info_url = Settings.oidc_introspection_endpoint_uri
    if not token_info_url:
        logging.warning("OAuth 2.0 Introspection endpoint not configured.")
        return None
    # TODO add multiple client support
    basic_auth_string = '{0}:{1}'.format(
        Settings.oidc_client_id,
        Settings.oidc_client_secret
    )
    basic_auth_bytes = bytearray(basic_auth_string, 'utf-8')
    headers['Authorization'] = 'Basic {0}'.format(
        b64encode(basic_auth_bytes).decode('utf-8')
    )
    try:
        token_request = session.post(token_info_url, data=request, headers=headers)
        if not token_request.ok:
            return None
        json = token_request.json()
        if "active" in json and json["active"] is False:
            return None
        return json
    except Exception as e:
        logging.error(str(e))
        return None


def validate_scope(required_scopes, token_scopes) -> bool:
    return True


def check_roles(project_domain):
    info = connexion.context.get("token_info")
    if info is None:
        return False

    # if auth with apiKey all domains are allowed
    if "scope" in info and "apiKey" in info["scope"]:
        return True

    if "azp" not in info or "resource_access" not in info:
        return False

    client_id = info["azp"]
    client = info["resource_access"].get(client_id)

    if client is None:
        return False

    for role in client["roles"]:
        match = re.match(role_regex, role)
        if match:
            role_parse = match.group(1, 2, 3)
            if (role_parse[0] == project_domain and
                    role_parse[1] == AADM_SUFFIX and
                    role_parse[2] == "w"):
                return True

    return False


def get_username():
    info = connexion.context.get("token_info")
    if info is None:
        return None

    # TODO decide what to do in case of apiKey
    # use default username or None?
    if "scope" in info and "apiKey" in info["scope"]:
        return None

    if "azp" not in info or "resource_access" not in info:
        return False

    return info["preferred_username"]


def check_role_auth_blueprint(func):
    @functools.wraps(func)
    def wrapper_check_role_auth(*args, **kwargs):
        blueprint_id = kwargs.get("blueprint_id")
        if not blueprint_id:
            return f"Authorization configuration error", 401

        version_id = kwargs.get("version_id")
        if not SQL_database.version_exists(blueprint_id, version_id) and not CSAR_db.version_exists(blueprint_id,
                                                                                                    version_id):
            return f"Did not find blueprint with id: {blueprint_id} and version_id: {version_id or 'any'}", 404

        project_domain = SQL_database.get_project_domain(blueprint_id)
        if project_domain and not check_roles(project_domain):
            return f"Unauthorized request for project: {project_domain}", 401

        return func(*args, **kwargs)

    return wrapper_check_role_auth


def check_role_auth_project_domain(func):
    @functools.wraps(func)
    def wrapper_check_role_auth(*args, **kwargs):
        blueprint_id = kwargs.get("blueprint_id")
        if not blueprint_id:
            return f"Authorization configuration error", 401

        project_domain = SQL_database.get_project_domain(blueprint_id)
        if project_domain and not check_roles(project_domain):
            return f"Unauthorized request for project: {project_domain}", 401

        return func(*args, **kwargs)

    return wrapper_check_role_auth


def check_role_auth_deployment(func):
    @functools.wraps(func)
    def wrapper_check_role_auth(*args, **kwargs):
        deployment_id = kwargs.get("deployment_id")
        if not deployment_id:
            return f"Authorization configuration error", 401

        inv = SQL_database.get_deployment_status(deployment_id)
        if not inv:
            return f"Deployment with id: {deployment_id} does not exist", 404

        if not SQL_database.version_exists(inv.blueprint_id, inv.version_id) and not CSAR_db.version_exists(
                inv.blueprint_id, inv.version_id):
            return f"Did not find blueprint with id: {inv.blueprint_id} and version_id: {inv.version_id or 'any'}", 404

        project_domain = SQL_database.get_project_domain(inv.blueprint_id)
        if project_domain and not check_roles(project_domain):
            return f"Unauthorized request for project: {project_domain}", 401

        return func(*args, **kwargs)

    return wrapper_check_role_auth
