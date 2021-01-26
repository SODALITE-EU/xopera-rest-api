import datetime
import json
import multiprocessing
import os
import traceback
import typing
import uuid
import shutil
from pathlib import Path
from typing import Optional

from opera.commands.deploy import deploy_service_template as opera_deploy
from opera.commands.undeploy import undeploy as opera_undeploy
from opera.storage import Storage


from opera.api.util import xopera_util, git_util, file_util
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
            location = InvocationService.deployment_location(inv.session_token, inv.blueprint_token)

            # stdout&err
            file_stdout = open(InvocationService.stdout_file(inv.session_token), "w")
            file_stderr = open(InvocationService.stderr_file(inv.session_token), "w")

            os.dup2(file_stdout.fileno(), 1)
            os.dup2(file_stderr.fileno(), 2)

            # pull from GIT
            CSAR_db.get_revision(inv.blueprint_token, location, inv.version_tag)
            # TODO catch error

            inv.state = InvocationState.IN_PROGRESS
            InvocationService.write_invocation(inv)

            try:
                if inv.operation == OperationType.DEPLOY:
                    InvocationWorkerProcess._deploy(location, inv.inputs, num_workers=inv.workers, resume=inv.resume)
                elif inv.operation == OperationType.UNDEPLOY:
                    InvocationWorkerProcess._undeploy(location, inv.inputs, num_workers=inv.workers)
                else:
                    raise RuntimeError("Unknown operation type:" + str(inv.operation))

                inv.state = InvocationState.SUCCESS
            except BaseException as e:
                if isinstance(e, RuntimeError):
                    raise e
                inv.state = InvocationState.FAILED
                inv.exception = "{}: {}\n\n{}".format(e.__class__.__name__, str(e), traceback.format_exc())

            instance_state = InvocationService.get_instance_state(location)
            stdout = InvocationWorkerProcess.read_file(InvocationService.stdout_file(inv.session_token))
            stderr = InvocationWorkerProcess.read_file(InvocationService.stderr_file(inv.session_token))
            file_stdout.truncate()
            file_stderr.truncate()

            inv.instance_state = instance_state
            inv.stdout = stdout
            inv.stderr = stderr

            # remove inputs
            # TODO remove
            InvocationService.remove_inputs(location)

            # save logfile to SQL database
            InvocationService.save_to_database(inv)

            # TODO remove
            InvocationService.save_to_git(inv, location)

            # clean
            shutil.rmtree(location)
            shutil.rmtree(InvocationService.stdstream_dir(inv.session_token))

            # create logfile
            InvocationService.write_invocation(inv)

    @staticmethod
    def _deploy(location: Path, inputs: typing.Optional[dict], num_workers: int, resume: bool):
        with xopera_util.cwd(location):
            opera_storage = Storage.create(".opera")
            service_template = str(entry_definitions(location))
            opera_deploy(service_template, inputs, opera_storage,
                         verbose_mode=True, num_workers=num_workers, delete_existing_state=(not resume))

    @staticmethod
    def _undeploy(location: Path, inputs: typing.Optional[dict], num_workers: int):
        with xopera_util.cwd(location):
            opera_storage = Storage.create(".opera")
            if inputs:
                opera_storage.write_json(inputs, "inputs")
            opera_undeploy(opera_storage, verbose_mode=True, num_workers=num_workers)

    @staticmethod
    def _redeploy():
        pass

    @staticmethod
    def read_file(filename):
        with open(filename, "r") as f:
            return f.read()


class InvocationService:

    def __init__(self):
        self.work_queue: multiprocessing.Queue = multiprocessing.Queue()
        self.worker = InvocationWorkerProcess(self.work_queue)
        self.worker.start()

    def invoke(self, operation_type: OperationType, blueprint_token: str, version_tag: Optional[str], workers: int,
               resume: bool, inputs: Optional[dict]) -> Invocation:
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
        inv.workers = workers
        inv.resume = resume
        self.stdstream_dir(inv.session_token).mkdir(parents=True, exist_ok=True)
        self.write_invocation(inv)

        self.work_queue.put(inv)
        return inv

    @classmethod
    def stdstream_dir(cls, session_token: uuid) -> Path:
        return Path(Settings.STDFILE_DIR) / session_token

    @classmethod
    def stdout_file(cls, session_token: str) -> Path:
        return cls.stdstream_dir(session_token) / 'stdout.txt'

    @classmethod
    def stderr_file(cls, session_token: str) -> Path:
        return cls.stdstream_dir(session_token) / 'stderr.txt'

    @classmethod
    def deployment_location(cls, session_token: uuid, blueprint_token: uuid) -> Path:
        return (Path(Settings.DEPLOYMENT_DIR) / blueprint_token / session_token).absolute()

    @classmethod
    def load_invocation(cls, session_token: str) -> Optional[Invocation]:
        storage = Storage.create(Settings.INVOCATION_DIR)
        file_path = f"invocation-{session_token}.json"
        try:
            inv = Invocation.from_dict(storage.read_json(file_path))
            if inv.state == InvocationState.IN_PROGRESS:
                inv.stdout = InvocationWorkerProcess.read_file(cls.stdout_file(inv.session_token))
                inv.stderr = InvocationWorkerProcess.read_file(cls.stderr_file(inv.session_token))
                # takes way too much time
                # location = xopera_util.deployment_location(inv.session_token, inv.blueprint_token)
                # inv.instance_state = InvocationService.get_instance_state(location)

            return inv

        except BaseException:
            return None

    @classmethod
    def write_invocation(cls, inv: Invocation):
        storage = Storage.create(Settings.INVOCATION_DIR)
        filename = "invocation-{}.json".format(inv.session_token)
        dump = json.dumps(inv.to_dict())
        storage.write(dump, filename)

    @classmethod
    def save_to_database(cls, inv: Invocation) -> None:
        logfile = json.dumps(inv.to_dict(), indent=2, sort_keys=False)
        SQL_database.update_deployment_log(inv.blueprint_token, logfile, inv.session_token, inv.timestamp)

    @classmethod
    def save_dot_opera_to_db(cls, inv: Invocation, location: Path) -> None:
        data = file_util.dir_to_json((location / '.opera'))
        SQL_database.save_session_data(inv.session_token, inv.blueprint_token, inv.version_tag, data)

    @classmethod
    def read_dot_opera_from_db(cls, session_token_old: str, session_token_new: str) -> Path:
        blueprint_token, version_tag, tree = SQL_database.get_session_data(session_token_old)
        location = cls.deployment_location(session_token_new, blueprint_token)
        file_util.json_to_dir(tree, (location / '.opera'))
        return location

    @classmethod
    def remove_inputs(cls, location):
        with xopera_util.cwd(location):
            opera_storage = Storage.create(".opera")
            opera_storage.write('{}', "inputs")

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
        for file_path in Path(location / '.opera' / 'instances').glob("*"):
            parsed = json.load(open(file_path, 'r'))
            component_name = parsed['tosca_name']['data']
            json_dict[component_name] = parsed['state']['data']
        return json_dict
