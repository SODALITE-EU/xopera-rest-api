import json
import logging as log
import os
import shutil
import sys
from pathlib import Path

import psycopg2

from service.csardb_service import GitDB
from service.sqldb_service import PostgreSQL, OfflineStorage
from settings import Settings
from util import xopera_util, timestamp_util, git_util

try:
    Settings.load_settings()
    SQL_database = PostgreSQL(Settings.sql_config)
    log.info('SQL_database for finalizing deployment: PostgreSQL')
except psycopg2.Error:
    SQL_database = OfflineStorage()
    log.info('SQL_database for finalizing deployment: OfflineStorage')

CSAR_db = GitDB(**Settings.git_config)
log.info(f"GitCsarDB with {str(CSAR_db.connection.git_connector)}")


def main():
    mode = sys.argv[1]
    if mode not in {'deploy', 'undeploy'}:
        log.error(msg='first argument should be either "deploy" or "undeploy", was {}'.format(mode))
        return

    deploy_location = Path(sys.argv[2])
    logfile_name = Settings.logfile_name
    timestamp_start = sys.argv[3]
    path_args = xopera_util.parse_path(deploy_location)
    blueprint_token = path_args['blueprint_token']
    session_token = path_args['session_token']
    try:
        inputs_file = sys.argv[4]
    except IndexError:
        inputs_file = None

    # reading logfile
    path_to_logfile = deploy_location / Path(logfile_name)
    with open(path_to_logfile, 'r') as file:
        logfile = file.readlines()
        log_str = "".join(logfile)

    failed_keywords = ["fail", "Traceback", "ERROR", "Error", "error"]
    state = "failed" if len([i for i in failed_keywords if i in log_str]) != 0 else "done"

    timestamp_end = timestamp_util.datetime_now_to_string()
    json_log = {
        "session_token": session_token,
        "blueprint_token": blueprint_token,
        "job": mode, "state": state,
        "timestamp_start": timestamp_start,
        "timestamp_end": timestamp_end,
        "log": log_str
    }

    # create json_log
    logfile = json.dumps(json_log, indent=2, sort_keys=False)

    # save logfile to
    SQL_database.update_deployment_log(blueprint_token=blueprint_token, _log=logfile, session_token=session_token,
                                       timestamp=timestamp_end)

    os.remove(path_to_logfile)


    # remove inputs
    _id = 'blueprint_id'
    with open(f"{deploy_location}/{_id}.deploy", 'w') as deploy_file:
        deploy_file.write('{"name": "service.yaml", "inputs": {}}')

    if inputs_file:
        os.remove(f"{deploy_location}/{inputs_file}")

    # remove openrc file
    openrc_path = deploy_location / Path('openrc.sh')
    if openrc_path.exists():
        openrc_path.unlink()

    # save deployment data to database
    CSAR_db.add_revision(blueprint_token=blueprint_token, blueprint_path=deploy_location,
                         revision_msg=git_util.after_job_commit_msg(token=blueprint_token, mode=mode))

    shutil.rmtree(deploy_location)
    os.mkdir(deploy_location)

    # leave json deploy.data or undeploy.data in deployment data dir
    json_log.pop("log")
    with open(f"{deploy_location}/{mode}.data", 'w') as file:
        file.write(json.dumps(json_log, indent=2, sort_keys=False))


if __name__ == '__main__':
    main()
