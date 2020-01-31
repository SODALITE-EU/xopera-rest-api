import json
import logging as log
import os
import shutil
import sys
from pathlib import Path

import psycopg2

from deployment_preparation.deployment_io import PostgreSQL, OfflineStorage
from deployment_preparation.settings import Settings

try:
    Settings.load_settings()
    database = PostgreSQL(Settings.connection)
    log.info('database for finalizing deployment: PostgreSQL')
except psycopg2.Error:
    database = OfflineStorage()
    log.info('database for finalizing deployment: OfflineStorage')


def main():
    mode = sys.argv[1]
    if mode not in {'deploy', 'undeploy'}:
        log.error(msg='first argument should be either "deploy" or "undeploy", was {}'.format(mode))
        return

    location = sys.argv[2]
    _id = sys.argv[3]
    logfile_name = sys.argv[4]
    blueprint_token = sys.argv[5]
    session_token = sys.argv[6]
    timestamp_start = sys.argv[7]
    timestamp_blueprint = sys.argv[8]
    inputs_file = sys.argv[9]
    # print("finalize deployment variables: location: {} _id {} logfile_name {} blueprint_token {} session_token {} "
    # "timestamp_start {} timestamp blueprint: {}".format(location, _id, logfile_name, blueprint_token,
    # session_token, timestamp_start, timestamp_blueprint))

    # reading logfile
    path_to_logfile = Path(location + "/" + logfile_name)
    with open(path_to_logfile, 'r') as file:
        logfile = file.readlines()
        log_str = "".join(logfile)

    failed_keywords = ["fail", "Traceback", "ERROR", "Error", "error"]
    state = "failed" if len([i for i in failed_keywords if i in log_str]) != 0 else "done"

    timestamp_end = Settings.datetime_now_to_string()
    _json = dict()
    _json["session_token"] = session_token
    _json["blueprint_token"] = blueprint_token
    _json["blueprint_id"] = _id
    _json["job"] = mode
    _json["state"] = state
    _json["timestamp_start"] = timestamp_start
    _json["timestamp_end"] = timestamp_end
    _json["log"] = log_str

    # create json_log
    logfile = json.dumps(_json, indent=2, sort_keys=False)

    # save logfile to database
    database.update_deployment_log(_id=_id, blueprint_token=blueprint_token, _log=logfile, session_token=session_token, timestamp=timestamp_end)
    os.remove(path_to_logfile)

    # saving deployment data to database

    # remove inputs
    with open(f"{location}/{_id}.deploy", 'w') as deploy_file:
        deploy_file.write('{"name": "service.yaml", "inputs": {}}')

    if inputs_file:
        os.remove(f"{location}/{inputs_file}")

    # save deployment data to database
    database.update_blueprint_data(location=location, blueprint_token=blueprint_token, last_job=mode, timestamp=timestamp_blueprint)
    shutil.rmtree(location)
    os.mkdir(location)

    # leave json deploy.data or undeploy.data in deployment data dir
    _json.pop("log")
    with open(location + "/{}.data".format(mode), 'w') as file:
        file.write(json.dumps(_json, indent=2, sort_keys=False))


if __name__ == '__main__':
    main()

