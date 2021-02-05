import functools
import re
from base64 import b64encode

import connexion
import requests

from opera.api.cli import CSAR_db, SQL_database
from opera.api.openapi.models.just_message import JustMessage
from opera.api.settings import Settings

# use connection pool for OAuth tokeninfo
adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
session = requests.Session()
for protocol in Settings.introspection_protocols:
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
    # TODO add multiple client support
    basic_auth_string = '{0}:{1}'.format(
        Settings.oidc_client_id,
        Settings.oidc_client_secret
    )
    basic_auth_bytes = bytearray(basic_auth_string, 'utf-8')
    headers['Authorization'] = 'Basic {0}'.format(
        b64encode(basic_auth_bytes).decode('utf-8')
    )

    token_request = session.post(token_info_url, data=request, headers=headers)
    if not token_request.ok:
        return None
    json = token_request.json()
    if "active" in json and json["active"] == False:
        return None
    return json


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


def get_access_token(request):
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise Exception("Authorization header absent")
    try:
        auth_type, token = authorization.split(None, 1)
    except ValueError:
        raise Exception("Invalid authorization header")

    if auth_type.lower() != "bearer":
        raise Exception("Invalid authorization type")
    return token


def check_role_auth_blueprint(func):
    @functools.wraps(func)
    def wrapper_check_role_auth(*args, **kwargs):
        blueprint_token = kwargs.get("blueprint_token")
        if not blueprint_token:
            return JustMessage(f"Authorization configuration error"), 401

        version_tag = kwargs.get("version_tag")
        if not CSAR_db.version_exists(blueprint_token, version_tag):
            return JustMessage(
                f"Did not find blueprint with token: {blueprint_token} and version_id: {version_tag or 'any'}"), 404

        project_domain = SQL_database.get_project_domain(blueprint_token)
        if project_domain and not check_roles(project_domain):
            return JustMessage(f"Unauthorized request for project: {project_domain}"), 401

        return func(*args, **kwargs)

    return wrapper_check_role_auth


def check_role_auth_session(func):
    @functools.wraps(func)
    def wrapper_check_role_auth(*args, **kwargs):
        session_token = kwargs.get("session_token")
        if not session_token:
            return JustMessage(f"Authorization configuration error"), 401

        session_data = SQL_database.get_session_data(session_token)
        if not session_data:
            return JustMessage(f"Session with session_token: {session_token} does not exist"), 404

        blueprint_token = session_data['blueprint_token']
        version_tag = kwargs.get("version_tag", session_data['version_tag'])
        if not CSAR_db.version_exists(blueprint_token, version_tag):
            return JustMessage(
                f"Did not find blueprint with token: {blueprint_token} and version_id: {version_tag or 'any'}"), 404

        project_domain = SQL_database.get_project_domain(blueprint_token)
        if project_domain and not check_roles(project_domain):
            return JustMessage(f"Unauthorized request for project: {project_domain}"), 401

        return func(*args, **kwargs)

    return wrapper_check_role_auth


def check_role_auth_session_or_blueprint(func):
    @functools.wraps(func)
    def wrapper_check_role_auth(*args, **kwargs):
        session_token = kwargs.get("session_token")
        blueprint_token = kwargs.get("blueprint_token")
        if not session_token and not blueprint_token:
            return JustMessage(f"No tokens provided"), 404

        elif session_token:
            session_data = SQL_database.get_session_data(session_token)
            if not session_data:
                return JustMessage(f"Session with session_token: {session_token} does not exist"), 404

            blueprint_token = session_data['blueprint_token']
            version_tag = kwargs.get("version_tag", session_data['version_tag'])
            if not CSAR_db.version_exists(blueprint_token, version_tag):
                return JustMessage(
                    f"Did not find blueprint with token: {blueprint_token} and version_id: {version_tag or 'any'}"), 404
        elif blueprint_token:
            version_tag = kwargs.get("version_tag")
            if not CSAR_db.version_exists(blueprint_token, version_tag):
                return JustMessage(
                    f"Did not find blueprint with token: {blueprint_token} and version_id: {version_tag or 'any'}"), 404

        project_domain = SQL_database.get_project_domain(blueprint_token)
        if project_domain and not check_roles(project_domain):
            return JustMessage(f"Unauthorized request for project: {project_domain}"), 401

        return func(*args, **kwargs)

    return wrapper_check_role_auth
