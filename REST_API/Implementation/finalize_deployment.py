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

Settings.load_settings()
try:
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
    timestamp_start = sys.argv[3]
    blueprint_token, session_token = xopera_util.parse_path(deploy_location)
    try:
        inputs_file = sys.argv[4]
    except IndexError:
        inputs_file = None

    # reading logfile
    state, log_str = xopera_util.parse_log(deploy_location)
    timestamp_end = timestamp_util.datetime_now_to_string()
    json_log = {
        "session_token": session_token,
        "blueprint_token": blueprint_token,
        "job": mode,
        "state": state,
        "timestamp_start": timestamp_start,
        "timestamp_end": timestamp_end,
        "log": log_str
    }

    # create json_log
    logfile = json.dumps(json_log, indent=2, sort_keys=False)

    # save logfile to
    SQL_database.update_deployment_log(blueprint_token=blueprint_token, _log=logfile, session_token=session_token,
                                       timestamp=timestamp_end)

    # remove logfile
    (deploy_location / Settings.logfile_name).unlink()

    # remove inputs
    with (deploy_location / ".opera" / "inputs").open('w') as xopera_inputs_file:
        xopera_inputs_file.write('{}')

    if inputs_file:
        (deploy_location / inputs_file).unlink()

    # remove openrc file
    openrc_path = deploy_location / Path('openrc.sh')
    if openrc_path.exists():
        openrc_path.unlink()

    # save deployment data to database
    revision_msg = git_util.after_job_commit_msg(token=blueprint_token, mode=mode)
    result, _ = CSAR_db.add_revision(blueprint_token=blueprint_token, blueprint_path=deploy_location,
                                     revision_msg=revision_msg)

    # register adding revision
    SQL_database.save_git_transaction_data(blueprint_token=result['blueprint_token'],
                                           version_tag=result['version_tag'],
                                           revision_msg=revision_msg,
                                           job='update',
                                           git_backend=str(CSAR_db.connection.git_connector),
                                           repo_url=result['url'])

    shutil.rmtree(deploy_location)
    os.mkdir(deploy_location)

    # leave json deploy.data or undeploy.data in deployment data dir
    json_log.pop("log")
    with open(f"{deploy_location}/{mode}.json", 'w') as file:
        file.write(json.dumps(json_log, indent=2, sort_keys=False))


if __name__ == '__main__':
    main()
