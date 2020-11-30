import json
import os
import shutil
import sys
from pathlib import Path

from opera.api.service import csardb_service, sqldb_service
from opera.api.settings import Settings
from opera.api.util import xopera_util, timestamp_util, git_util
from opera.api.log import get_logger

Settings.load_settings()
logger = get_logger(__name__)

CSAR_db = csardb_service.GitDB(**Settings.git_config)
SQL_database = sqldb_service.connect(Settings.sql_config)


def main():
    mode = sys.argv[1]
    if mode not in {'deploy', 'undeploy'}:
        logger.error(msg='first argument should be either "deploy" or "undeploy", was {}'.format(mode))
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

    # save deployment data to database
    revision_msg = git_util.after_job_commit_msg(token=blueprint_token, mode=mode)
    version_tag = xopera_util.read_version_tag(deploy_location=deploy_location)
    if version_tag == 'None':
        version_tag = CSAR_db.get_tags(blueprint_token=blueprint_token)[-1]
    result, _ = CSAR_db.add_revision(blueprint_token=blueprint_token, blueprint_path=deploy_location,
                                     revision_msg=revision_msg, minor_to_increment=version_tag)

    # register adding revision
    SQL_database.save_git_transaction_data(blueprint_token=result['blueprint_token'],
                                           version_tag=result['version_tag'],
                                           revision_msg=revision_msg,
                                           job='update',
                                           git_backend=str(CSAR_db.connection.git_connector),
                                           repo_url=result['url'],
                                           commit_sha=result['commit_sha'])

    shutil.rmtree(deploy_location)
    os.mkdir(deploy_location)

    # leave json deploy.data or undeploy.data in deployment data dir
    json_log.pop("log")
    with open(f"{deploy_location}/{mode}.json", 'w') as file:
        file.write(json.dumps(json_log, indent=2, sort_keys=False))


if __name__ == '__main__':
    main()
