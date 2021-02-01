import datetime
import json
import multiprocessing
import os
import shutil
import tempfile
import traceback
import uuid
from pathlib import Path
from typing import Optional

from opera.commands.deploy import deploy_service_template as opera_deploy
from opera.commands.diff import diff_instances as opera_diff_instances
from opera.commands.undeploy import undeploy as opera_undeploy
from opera.commands.update import update as opera_update
from opera.commands.validate import validate_service_template as opera_validate
from opera.commands.outputs import outputs as opera_outputs
from opera.compare.instance_comparer import InstanceComparer as opera_InstanceComparer
from opera.compare.template_comparer import TemplateComparer as opera_TemplateComparer
from opera.storage import Storage

from opera.api.blueprint_converters.blueprint2CSAR import entry_definitions
from opera.api.cli import CSAR_db, SQL_database
from opera.api.log import get_logger
from opera.api.openapi.models import Invocation, InvocationState, OperationType
from opera.api.settings import Settings
from opera.api.util import xopera_util, file_util

logger = get_logger(__name__)


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

            inv.state = InvocationState.IN_PROGRESS
            InvocationService.write_invocation(inv)

            try:
                if inv.operation == OperationType.DEPLOY_FRESH:
                    InvocationWorkerProcess._deploy_fresh(location, inv)
                elif inv.operation == OperationType.DEPLOY_CONTINUE:
                    InvocationWorkerProcess._deploy_continue(location, inv)
                elif inv.operation == OperationType.UNDEPLOY:
                    InvocationWorkerProcess._undeploy(location, inv)
                elif inv.operation == OperationType.UPDATE:
                    InvocationWorkerProcess._update(location, inv)
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

            InvocationService.save_to_database(inv)
            InvocationService.save_dot_opera_to_db(inv, location)
            InvocationService.write_invocation(inv)

            # clean
            shutil.rmtree(location)
            shutil.rmtree(InvocationService.stdstream_dir(inv.session_token))

    @staticmethod
    def _deploy_fresh(location: Path, inv: Invocation):
        CSAR_db.get_revision(inv.blueprint_token, location, inv.version_tag)

        with xopera_util.cwd(location):
            opera_storage = Storage.create(".opera")
            service_template = str(entry_definitions(location))
            opera_deploy(service_template, inv.inputs, opera_storage,
                         verbose_mode=True, num_workers=inv.workers, delete_existing_state=True)

    @staticmethod
    def _deploy_continue(location: Path, inv: Invocation):

        # get blueprint
        CSAR_db.get_revision(inv.blueprint_token, location, inv.version_tag)
        # get session data (.opera)
        InvocationService.get_dot_opera_from_db(inv.session_token_old, location)

        with xopera_util.cwd(location):
            opera_storage = Storage.create(".opera")
            service_template = str(entry_definitions(location))
            opera_deploy(service_template, inv.inputs, opera_storage,
                         verbose_mode=True, num_workers=inv.workers, delete_existing_state=(not inv.resume))

    @staticmethod
    def _undeploy(location: Path, inv: Invocation):

        # get blueprint
        CSAR_db.get_revision(inv.blueprint_token, location, inv.version_tag)
        # get session data (.opera)
        InvocationService.get_dot_opera_from_db(inv.session_token_old, location)

        with xopera_util.cwd(location):
            opera_storage = Storage.create(".opera")
            if inv.inputs:
                opera_storage.write_json(inv.inputs, "inputs")
            opera_undeploy(opera_storage, verbose_mode=True, num_workers=inv.workers)

    @staticmethod
    def _update(location: Path, inv: Invocation):

        storage_old, location_old, storage_new, location_new = InvocationWorkerProcess.prepare_two_workdirs(
            inv.session_token_old, inv.blueprint_token, inv.version_tag, inv.inputs, location)

        assert location_new == str(location)

        with xopera_util.cwd(location_new):
            instance_diff = opera_diff_instances(storage_old, location_old,
                                                 storage_new, location_new,
                                                 opera_TemplateComparer(), opera_InstanceComparer(),
                                                 verbose_mode=True)

            opera_update(storage_old, location_old,
                         storage_new, location_new,
                         opera_InstanceComparer(), instance_diff,
                         verbose_mode=True, num_workers=inv.workers, overwrite=True)

        shutil.rmtree(location_old)
        # location_new is needed in __run_internal and deleted afterwards

    @staticmethod
    def prepare_two_workdirs(session_token_old: str, blueprint_token: str, version_tag: str,
                             inputs: dict, location: Path = None):
        location_old = InvocationService.deployment_location(str(uuid.uuid4()), str(uuid.uuid4()))
        location_new = location or InvocationService.deployment_location(str(uuid.uuid4()), str(uuid.uuid4()))

        # old Deployed instance
        old_session_data = SQL_database.get_session_data(session_token_old)
        old_blueprint_token = old_session_data['blueprint_token']
        old_version_tag = old_session_data['version_tag']
        CSAR_db.get_revision(old_blueprint_token, location_old, old_version_tag)
        InvocationService.get_dot_opera_from_db(session_token_old, location_old)
        storage_old = Storage.create(str(location_old / '.opera'))

        # new blueprint
        CSAR_db.get_revision(blueprint_token, location_new, version_tag)
        storage_new = Storage.create(str(location_new / '.opera'))
        storage_new.write_json(inputs or {}, "inputs")
        storage_new.write(str(entry_definitions(location_new)), "root_file")

        ##############################################################
        # TODO remove when fixed
        #  Due to bug in xOpera, copy old TOSCA to new workdir with random name
        new_filename = str(uuid.uuid4())
        shutil.copyfile(str(location_old / entry_definitions(location_old)), str(location_new / new_filename))
        storage_old.write(str(new_filename), "root_file")

        ############################################################################

        return storage_old, str(location_old), storage_new, str(location_new)

    @staticmethod
    def diff(session_token_old: str, blueprint_token: str, version_tag: str, inputs: dict):

        storage_old, location_old, storage_new, location_new = InvocationWorkerProcess.prepare_two_workdirs(
            session_token_old, blueprint_token, version_tag, inputs)

        with xopera_util.cwd(location_new):
            instance_diff = opera_diff_instances(storage_old, location_old,
                                                 storage_new, location_new,
                                                 opera_TemplateComparer(), opera_InstanceComparer(),
                                                 verbose_mode=True)
        shutil.rmtree(location_new)
        shutil.rmtree(location_old)
        return instance_diff

    @staticmethod
    def validate(blueprint_token: str, version_tag: str, inputs: dict):
        with tempfile.TemporaryDirectory() as location:
            CSAR_db.get_revision(blueprint_token, location, version_tag)
            try:
                with xopera_util.cwd(location):
                    service_template = str(entry_definitions(location))
                    opera_validate(service_template, inputs)
                return None
            except Exception as e:
                return e.__class__.__name__, xopera_util.mask_workdir(location, str(e))

    @staticmethod
    def outputs(session_token: str):
        with tempfile.TemporaryDirectory() as location:
            InvocationService.prepare_location(session_token, Path(location))
            try:
                with xopera_util.cwd(location):
                    opera_storage = Storage.create(".opera")
                    return opera_outputs(opera_storage), None
            except Exception as e:
                return None, (e.__class__.__name__, xopera_util.mask_workdir(location, str(e)))

    @staticmethod
    def read_file(filename):
        with open(filename, "r") as f:
            return f.read()


class InvocationService:

    def __init__(self):
        self.work_queue: multiprocessing.Queue = multiprocessing.Queue()
        self.worker = InvocationWorkerProcess(self.work_queue)
        self.worker.start()

    def invoke(self, operation_type: OperationType, blueprint_token: str, version_tag: Optional[str],
               session_token_old: Optional[str], workers: int, inputs: Optional[dict],
               resume: bool = None) -> Invocation:
        invocation_uuid = str(uuid.uuid4())
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        logger.info("Invoking %s with ID %s at %s", operation_type, invocation_uuid, now.isoformat())

        inv = Invocation()
        inv.blueprint_token = blueprint_token
        inv.session_token = invocation_uuid
        inv.session_token_old = session_token_old
        inv.version_tag = version_tag or CSAR_db.get_last_tag(blueprint_token)
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
    def get_dot_opera_from_db(cls, session_token, location: Path) -> None:
        dot_opera_data = SQL_database.get_session_data(session_token)
        if not dot_opera_data:
            logger.error(f"sqldb_service.get_session_data failed: session_token: {session_token}")
        file_util.json_to_dir(dot_opera_data['tree'], (location / '.opera'))

    @classmethod
    def prepare_location(cls, session_token: str, location: Path):
        """
        Prepare location with blueprint and session_data (.opera dir)
        """
        session_data = SQL_database.get_session_data(session_token)
        blueprint_token = session_data['blueprint_token']
        version_tag = session_data['version_tag']
        if not CSAR_db.get_revision(blueprint_token, location, version_tag):
            logger.error(f'csardb_service.get_revision failed: blueprint_token: {blueprint_token}, '
                         f'location: {location}, version_tag: {version_tag}')
        InvocationService.get_dot_opera_from_db(session_token, location)

    @classmethod
    def get_instance_state(cls, location):
        json_dict = {}
        for file_path in Path(location / '.opera' / 'instances').glob("*"):
            parsed = json.load(open(file_path, 'r'))
            component_name = parsed['tosca_name']['data']
            json_dict[component_name] = parsed['state']['data']
        return json_dict
