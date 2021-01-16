import datetime
import json
import multiprocessing
import os
import traceback
import typing
import uuid
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

from opera.commands.deploy import deploy as opera_deploy
from opera.commands.undeploy import undeploy as opera_undeploy
from opera.storage import Storage


from opera.api.util import xopera_util, git_util
from opera.api.blueprint_converters.blueprint2CSAR import entry_definitions
from opera.api.service import csardb_service, sqldb_service
from opera.api.log import get_logger
from opera.api.settings import Settings
from opera.api.openapi.models import Invocation, InvocationState, OperationType

logger = get_logger(__name__)
CSAR_db = csardb_service.GitDB(**Settings.git_config)
SQL_database = sqldb_service.connect(Settings.sql_config)


class InvocationWorkerProcess(multiprocessing.Process):

    def __init__(self, work_queue: multiprocessing.Queue):
        super(InvocationWorkerProcess, self).__init__(
            group=None, target=self._run_internal, name="Invocation-Worker", args=(),
            kwargs={
                "work_queue": work_queue,
            }, daemon=None)

    @staticmethod
    def _run_internal(work_queue: multiprocessing.Queue):

        while True:
            inv: Invocation = work_queue.get(block=True)
            location = xopera_util.deployment_location(inv.session_token, inv.blueprint_token)

            # stdout&err
            file_stdout = open(xopera_util.stdout_file(inv.session_token), "w")
            file_stderr = open(xopera_util.stderr_file(inv.session_token), "w")

            os.dup2(file_stdout.fileno(), 1)
            os.dup2(file_stderr.fileno(), 2)

            # pull from GIT
            CSAR_db.get_revision(inv.blueprint_token, location, inv.version_tag)
            # TODO catch error

            inv.state = InvocationState.IN_PROGRESS
            InvocationService.write_invocation(inv)

            try:
                if inv.operation == OperationType.DEPLOY:
                    InvocationWorkerProcess._deploy(location, inv.inputs, num_workers=1)
                elif inv.operation == OperationType.UNDEPLOY:
                    InvocationWorkerProcess._undeploy(location, num_workers=1)
                else:
                    raise RuntimeError("Unknown operation type:" + str(inv.operation))

                inv.state = InvocationState.SUCCESS
            except BaseException as e:
                if isinstance(e, RuntimeError):
                    raise e
                inv.state = InvocationState.FAILED
                inv.exception = "{}: {}\n\n{}".format(e.__class__.__name__, str(e), traceback.format_exc())

            instance_state = InvocationService.get_instance_state(location)
            stdout = InvocationWorkerProcess.read_file(xopera_util.stdout_file(inv.session_token))
            stderr = InvocationWorkerProcess.read_file(xopera_util.stderr_file(inv.session_token))
            file_stdout.truncate()
            file_stderr.truncate()

            inv.instance_state = instance_state
            inv.stdout = stdout
            inv.stderr = stderr

            # create logfile
            InvocationService.write_invocation(inv)

            # save logfile to
            InvocationService.save_to_database(inv)

            # save to git
            InvocationService.save_to_git(inv, location)

            # clean
            shutil.rmtree(location)
            shutil.rmtree(xopera_util.stdstream_dir(inv.session_token))

    @staticmethod
    def _deploy(location: Path, inputs: typing.Optional[dict], num_workers: int):
        with xopera_util.cwd(location):
            opera_storage = Storage.create(".opera")
            service_template = str(entry_definitions(location))
            opera_deploy(service_template, inputs, opera_storage,
                         verbose_mode=True, num_workers=num_workers, delete_existing_state=True)

    @staticmethod
    def _undeploy(location: Path, num_workers: int):
        with xopera_util.cwd(location):
            opera_storage = Storage.create(".opera")
            opera_undeploy(opera_storage, verbose_mode=True, num_workers=num_workers)

    @staticmethod
    def read_file(filename):
        with open(filename, "r") as f:
            return f.read()


class InvocationService:
    def __init__(self):
        self.work_queue: multiprocessing.Queue = multiprocessing.Queue()
        self.worker = InvocationWorkerProcess(self.work_queue)
        self.worker.start()

    def invoke(self, operation_type: OperationType, blueprint_token: str, version_tag: Optional[str], inputs: Optional[dict]) \
            -> Invocation:
        invocation_uuid = str(uuid.uuid4())
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        logger.info("Invoking %s with ID %s at %s", operation_type, invocation_uuid, now.isoformat())

        inv = Invocation()
        inv.blueprint_token = blueprint_token
        inv.session_token = invocation_uuid
        inv.version_tag = version_tag
        inv.state = InvocationState.PENDING
        inv.operation = operation_type
        inv.timestamp = now.isoformat()
        inv.inputs = inputs
        inv.instance_state = None
        inv.exception = None
        inv.stdout = None
        inv.stderr = None
        self.write_invocation(inv)

        self.work_queue.put(inv)
        return inv
    """
    @classmethod
    def invocation_history(cls) -> List[Invocation]:
        logger.info("Loading invocation history.")

        invocations = []
        for file_path in Path(".opera-api").glob('*.json'):
            logger.debug(file_path)
            invocation = Invocation.from_dict(json.load(open(file_path, 'r')))

            if invocation.state == InvocationState.IN_PROGRESS:
                invocation.stdout = InvocationWorkerProcess.read_file(InvocationWorkerProcess.IN_PROGRESS_STDOUT_FILE)
                invocation.stderr = InvocationWorkerProcess.read_file(InvocationWorkerProcess.IN_PROGRESS_STDERR_FILE)

            invocations.append(invocation)

        if invocations:
            invocations.sort(
                key=lambda x: datetime.datetime.strptime(
                    x.timestamp,
                    '%Y-%m-%dT%H:%M:%S.%f+00:00'
                ),
                reverse=True
            )

        return invocations

    @classmethod
    def latest_invocation(cls) -> Optional[Invocation]:
        all_invocations = cls.invocation_history()
        try:
            return next(all_invocations)
        except StopIteration:
            return None
    """

    @classmethod
    def load_invocation(cls, session_token: str) -> Optional[Invocation]:
        storage = Storage.create(".opera-api")
        file_path = f"invocation-{session_token}.json"
        try:
            inv = Invocation.from_dict(storage.read_json(file_path))
            if inv.state == InvocationState.IN_PROGRESS:
                inv.stdout = InvocationWorkerProcess.read_file(xopera_util.stdout_file(inv.session_token))
                inv.stderr = InvocationWorkerProcess.read_file(xopera_util.stderr_file(inv.session_token))
                location = xopera_util.deployment_location(inv.session_token, inv.blueprint_token)
                inv.instance_state = InvocationService.get_instance_state(location)

            return inv

        except BaseException:
            return None

    @classmethod
    def write_invocation(cls, inv: Invocation):
        storage = Storage.create(".opera-api")
        filename = "invocation-{}.json".format(inv.session_token)
        dump = json.dumps(inv.to_dict())
        storage.write(dump, filename)

    @classmethod
    def save_to_database(cls, inv: Invocation):
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        json_log = {
            "session_token": inv.session_token,
            "blueprint_token": inv.blueprint_token,
            "job": inv.operation,
            "state": inv.state,
            "timestamp_start": inv.timestamp,
            "timestamp_end": now.isoformat(),
            "log": inv.stdout
        }

        logfile = json.dumps(json_log, indent=2, sort_keys=False)

        SQL_database.update_deployment_log(inv.blueprint_token, logfile, inv.session_token, inv.timestamp)

    @classmethod
    # TODO get rid of saving to git after job
    def save_to_git(cls, inv: Invocation, location):
        # save deployment data to database
        revision_msg = git_util.after_job_commit_msg(inv.blueprint_token, inv.operation)
        version_tag = inv.version_tag
        if version_tag is None:
            version_tag = CSAR_db.get_tags(inv.blueprint_token)[-1]
        result, _ = CSAR_db.add_revision(blueprint_token=inv.blueprint_token, blueprint_path=location,
                                         revision_msg=revision_msg, minor_to_increment=version_tag)

        # register adding revision
        SQL_database.save_git_transaction_data(blueprint_token=result['blueprint_token'],
                                               version_tag=result['version_tag'],
                                               revision_msg=revision_msg,
                                               job='update',
                                               git_backend=str(CSAR_db.connection.git_connector),
                                               repo_url=result['url'],
                                               commit_sha=result['commit_sha'])

    @classmethod
    def get_instance_state(cls, location):
        json_dict = {}
        for file_path in Path(location / '.opera' / 'instances' ).glob("*"):
            parsed = json.load(open(file_path, 'r'))
            component_name = parsed['tosca_name']['data']
            json_dict[component_name] = parsed['state']['data']
        return json_dict