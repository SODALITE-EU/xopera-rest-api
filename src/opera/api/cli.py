import os

import connexion

from opera.api.log import get_logger
from opera.api.openapi import encoder
from opera.api.service import csardb_service
from opera.api.service.sqldb_service import PostgreSQL
from opera.api.settings import Settings
from opera.api.util import xopera_util

DEBUG = os.getenv("DEBUG", "false") == "true"
logger = get_logger(__name__)
Settings.load_settings()
CSAR_db = csardb_service.GitDB(**Settings.git_config)


def main():
    xopera_util.init_data()
    xopera_util.configure_ssh_keys()
    PostgreSQL.initialize()

    if DEBUG:
        logger.info("Running in debug mode: flask backend.")
        server = "flask"
    else:
        logger.info("Running in production mode: tornado backend.")
        server = "tornado"

    app = connexion.App(__name__, specification_dir="./openapi/openapi/", server=server, options=dict(
        serve_spec=True,
        swagger_ui=True
    ))
    app.app.json_encoder = encoder.JSONEncoder
    app.add_api("openapi.yaml", arguments={"title": "xOpera REST API"}, pythonic_params=True)
    app.run(port=8080, debug=DEBUG)


def test():
    app = connexion.App(__name__, specification_dir="./openapi/openapi/", options=dict(
        serve_spec=False,
        swagger_ui=False
    ))
    app.app.json_encoder = encoder.JSONEncoder
    app.add_api("openapi.yaml")
    app.testing = True
    return app


if __name__ == "__main__":
    main()
