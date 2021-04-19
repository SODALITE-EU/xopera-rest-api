import datetime
import json
import multiprocessing
import os
import shutil
import tempfile
import traceback
import uuid
import sys
from pathlib import Path
from typing import Optional
from werkzeug.datastructures import FileStorage

from opera.commands.deploy import deploy_service_template as opera_deploy
from opera.commands.diff import diff_instances as opera_diff_instances
from opera.commands.outputs import outputs as opera_outputs
from opera.commands.undeploy import undeploy as opera_undeploy
from opera.commands.update import update as opera_update
from opera.commands.validate import validate_service_template as opera_validate
from opera.compare.instance_comparer import InstanceComparer as opera_InstanceComparer
from opera.compare.template_comparer import TemplateComparer as opera_TemplateComparer
from opera.error import ParseError
from opera.storage import Storage

from opera.api.blueprint_converters.blueprint2CSAR import entry_definitions
from opera.api.blueprint_converters import csar_to_blueprint
from opera.api.cli import CSAR_db, SQL_database
from opera.api.log import get_logger
from opera.api.openapi.models import Invocation, InvocationState, OperationType
from opera.api.settings import Settings
from opera.api.util import xopera_util, file_util

logger = get_logger(__name__)


class InvocationWorkerProcess:

    @staticmethod
    def run_internal(work_queue: multiprocessing.Queue):

        while True:
            inv: Invocation = work_queue.get(block=True)
            inv.timestamp_start = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

            invocation_id = SQL_database.get_last_invocation_id(inv.deployment_id)
            location = InvocationService.deployment_location(inv.deployment_id, inv.blueprint_id)

            inv.state = InvocationState.IN_PROGRESS
            InvocationService.save_invocation(invocation_id, inv)

            # stdout&err
            file_stdout = open(InvocationService.stdout_file(inv.deployment_id), "w")
            file_stderr = open(InvocationService.stderr_file(inv.deployment_id), "w")

            os.dup2(file_stdout.fileno(), 1)
            os.dup2(file_stderr.fileno(), 2)

            try:
                if inv.operation == OperationType.DEPLOY_FRESH:
                    outputs = InvocationWorkerProcess._deploy_fresh(location, inv)
                elif inv.operation == OperationType.DEPLOY_CONTINUE:
                    outputs = InvocationWorkerProcess._deploy_continue(location, inv)
                elif inv.operation == OperationType.UNDEPLOY:
                    outputs = InvocationWorkerProcess._undeploy(location, inv)
                elif inv.operation == OperationType.UPDATE:
                    outputs = InvocationWorkerProcess._update(location, inv)
                else:
                    raise RuntimeError("Unknown operation type:" + str(inv.operation))

                inv.state = InvocationState.SUCCESS
                inv.outputs = outputs or None
            except RuntimeError as e:
                inv.state = InvocationState.FAILED
                inv.exception = 'Runtime exception on xopera-rest-api'
                raise e
            except ParseError as e:
                inv.state = InvocationState.FAILED
                inv.exception = "{}: {}: {}\n\n{}".format(e.__class__.__name__, e.loc, str(e),
                                                          traceback.format_exc())
            except BaseException as e:
                inv.state = InvocationState.FAILED
                inv.exception = "{}: {}\n\n{}".format(e.__class__.__name__, str(e), traceback.format_exc())

            finally:

                inv.instance_state = InvocationService.get_instance_state(location)

                sys.stdout.flush()
                sys.stderr.flush()
                inv.stdout = InvocationWorkerProcess.read_file(InvocationService.stdout_file(inv.deployment_id))
                inv.stderr = InvocationWorkerProcess.read_file(InvocationService.stderr_file(inv.deployment_id))
                file_stdout.close()
                file_stderr.close()

                inv.timestamp_end = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

                InvocationService.save_dot_opera_to_db(inv, location)
                InvocationService.save_invocation(invocation_id, inv)

                # clean
                shutil.rmtree(location)
                shutil.rmtree(InvocationService.stdstream_dir(inv.deployment_id))

    @staticmethod
    def _deploy_fresh(location: Path, inv: Invocation):
        CSAR_db.get_revision(inv.blueprint_id, location, inv.version_id)

        with xopera_util.cwd(location):
            opera_storage = Storage.create(".opera")
            service_template = str(entry_definitions(location))
            opera_deploy(service_template, inv.inputs, opera_storage,
                         verbose_mode=False, num_workers=inv.workers, delete_existing_state=True)
            return opera_outputs(opera_storage)

    @staticmethod
    def _deploy_continue(location: Path, inv: Invocation):

        # get blueprint
        CSAR_db.get_revision(inv.blueprint_id, location, inv.version_id)
        # get session data (.opera)
        InvocationService.get_dot_opera_from_db(inv.deployment_id, location)

        with xopera_util.cwd(location):
            opera_storage = Storage.create(".opera")
            service_template = str(entry_definitions(location))
            opera_deploy(service_template, inv.inputs, opera_storage,
                         verbose_mode=False, num_workers=inv.workers, delete_existing_state=inv.clean_state)
            return opera_outputs(opera_storage)

    @staticmethod
    def _undeploy(location: Path, inv: Invocation):

        # get blueprint
        CSAR_db.get_revision(inv.blueprint_id, location, inv.version_id)
        # get session data (.opera)
        InvocationService.get_dot_opera_from_db(inv.deployment_id, location)

        with xopera_util.cwd(location):
            opera_storage = Storage.create(".opera")
            if inv.inputs:
                opera_storage.write_json(inv.inputs, "inputs")
            opera_undeploy(opera_storage, verbose_mode=False, num_workers=inv.workers)
            return opera_outputs(opera_storage)

    @staticmethod
    def _update(location: Path, inv: Invocation):

        storage_old, location_old, storage_new, location_new = InvocationWorkerProcess.prepare_two_workdirs(
            inv.deployment_id, inv.blueprint_id, inv.version_id, inv.inputs, location)

        assert location_new == str(location)

        with xopera_util.cwd(location_new):
            instance_diff = opera_diff_instances(storage_old, location_old,
                                                 storage_new, location_new,
                                                 opera_TemplateComparer(), opera_InstanceComparer(),
                                                 verbose_mode=False)

            opera_update(storage_old, location_old,
                         storage_new, location_new,
                         opera_InstanceComparer(), instance_diff,
                         verbose_mode=False, num_workers=inv.workers, overwrite=False)
            outputs = opera_outputs(storage_new)

        shutil.rmtree(location_old)
        # location_new is needed in __run_internal and deleted afterwards
        return outputs

    @staticmethod
    def prepare_two_workdirs(deployment_id: str, blueprint_id: str, version_id: str,
                             inputs: dict, location: Path = None):
        location_old = InvocationService.deployment_location(str(uuid.uuid4()), str(uuid.uuid4()))
        location_new = location or InvocationService.deployment_location(str(uuid.uuid4()), str(uuid.uuid4()))

        # old Deployed instance
        # TODO Next line should use SQL_database.get_deployment_status(deployment_id), had to be changed since
        #  old blueprint_id is part of second to last invocation, last is already current
        inv_old = SQL_database.get_last_completed_invocation(deployment_id)
        CSAR_db.get_revision(inv_old.blueprint_id, location_old, inv_old.version_id)
        InvocationService.get_dot_opera_from_db(deployment_id, location_old)
        storage_old = Storage.create(str(location_old / '.opera'))

        # new blueprint
        CSAR_db.get_revision(blueprint_id, location_new, version_id)
        storage_new = Storage.create(str(location_new / '.opera'))
        storage_new.write_json(inputs or {}, "inputs")
        storage_new.write(str(entry_definitions(location_new)), "root_file")

        ##############################################################
        # TODO remove when fixed
        #  Due to bug in xOpera, copy old TOSCA to new workdir with random name
        #  we also have to copy all the other files in TOSCA blueprint to new workdir
        new_filename = str(uuid.uuid4())
        shutil.copyfile(str(location_old / entry_definitions(location_old)), str(location_new / new_filename))
        storage_old.write(str(new_filename), "root_file")

        def copytree(src, dst, symlinks=False, ignore=None):
            for item in os.listdir(src):
                s = os.path.join(src, item)
                d = os.path.join(dst, item)
                if os.path.isdir(s) and Path(s).name != '.opera':
                    if not os.path.exists(d):
                        os.mkdir(d)
                    copytree(s, d, symlinks, ignore)
                else:
                    if not os.path.exists(d):
                        shutil.copy2(s, d)

        copytree(location_old, location_new)

        ############################################################################

        return storage_old, str(location_old), storage_new, str(location_new)

    @staticmethod
    def diff(deployment_id: str, blueprint_id: str, version_id: str, inputs: dict):

        storage_old, location_old, storage_new, location_new = InvocationWorkerProcess.prepare_two_workdirs(
            deployment_id, blueprint_id, version_id, inputs)

        with xopera_util.cwd(location_new):
            instance_diff = opera_diff_instances(storage_old, location_old,
                                                 storage_new, location_new,
                                                 opera_TemplateComparer(), opera_InstanceComparer(),
                                                 verbose_mode=False)
        shutil.rmtree(location_new)
        shutil.rmtree(location_old)
        return instance_diff

    @staticmethod
    def validate(blueprint_id: str, version_tag: str, inputs: dict):
        with tempfile.TemporaryDirectory() as location:
            CSAR_db.get_revision(blueprint_id, location, version_tag)
            try:
                with xopera_util.cwd(location):
                    service_template = str(entry_definitions(location))
                    opera_validate(service_template, inputs)
                return None
            except Exception as e:
                return "{}: {}".format(e.__class__.__name__, xopera_util.mask_workdir(location, str(e)))

    @staticmethod
    def validate_new(CSAR: FileStorage, inputs: dict):
        try:
            with tempfile.TemporaryDirectory() as location:
                with tempfile.TemporaryDirectory() as csar_workdir:
                    csar_path = Path(csar_workdir) / Path(CSAR.filename)
                    CSAR.save(Path(csar_path).open('wb'))
                    csar_to_blueprint(csar=csar_path, dst=location)

                with xopera_util.cwd(location):
                    service_template = str(entry_definitions(location))
                    opera_validate(service_template, inputs)
                return None
        except Exception as e:
            return "{}: {}".format(e.__class__.__name__, xopera_util.mask_workdirs([location, csar_workdir], str(e)),)

    @staticmethod
    def outputs(deployment_id: str):
        with tempfile.TemporaryDirectory() as location:
            InvocationService.prepare_location(deployment_id, Path(location))
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

    @staticmethod
    def rm_file(filename):
        Path(filename).unlink(missing_ok=True)


class InvocationService:

    def __init__(self, workers_num=10):
        """
        Initializes InvocationService

        It creates work_queue for invocations and workers_pool with [workers_num] workers
        Args:
            workers_num: number of workers
        """
        self.work_queue: multiprocessing.Queue = multiprocessing.Queue()
        self.workers_pool = multiprocessing.Pool(workers_num, InvocationWorkerProcess.run_internal, (self.work_queue, ))

    def invoke(self, operation_type: OperationType, blueprint_id: uuid, version_id: uuid,
               deployment_id: uuid, workers: int, inputs: dict,
               clean_state: bool = None) -> Invocation:
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        logger.info("Invoking %s with ID %s at %s", operation_type, deployment_id, now.isoformat())

        invocation_id = uuid.uuid4()

        inv = Invocation()
        inv.blueprint_id = blueprint_id
        inv.version_id = version_id or CSAR_db.get_last_tag(blueprint_id)
        inv.deployment_id = deployment_id or uuid.uuid4()
        inv.state = InvocationState.PENDING
        inv.operation = operation_type
        inv.timestamp_submission = now.isoformat()
        inv.inputs = inputs
        inv.instance_state = None
        inv.outputs = None
        inv.exception = None
        inv.stdout = None
        inv.stderr = None
        inv.workers = workers
        inv.clean_state = clean_state

        self.stdstream_dir(inv.deployment_id).mkdir(parents=True, exist_ok=True)
        self.save_invocation(invocation_id, inv)

        self.work_queue.put(inv)
        return inv

    @classmethod
    def stdstream_dir(cls, deployment_id: uuid) -> Path:
        return Path(Settings.STDFILE_DIR) / str(deployment_id)

    @classmethod
    def stdout_file(cls, deployment_id: str) -> Path:
        return cls.stdstream_dir(deployment_id) / 'stdout.txt'

    @classmethod
    def stderr_file(cls, deployment_id: str) -> Path:
        return cls.stdstream_dir(deployment_id) / 'stderr.txt'

    @classmethod
    def deployment_location(cls, deployment_id: uuid, blueprint_id: uuid) -> Path:
        return (Path(Settings.DEPLOYMENT_DIR) / str(blueprint_id) / str(deployment_id)).absolute()

    @classmethod
    def load_invocation(cls, deployment_id: str) -> Optional[Invocation]:
        try:
            inv = SQL_database.get_deployment_status(deployment_id)
            if inv.state == InvocationState.IN_PROGRESS:
                inv.stdout = InvocationWorkerProcess.read_file(cls.stdout_file(inv.deployment_id))
                inv.stderr = InvocationWorkerProcess.read_file(cls.stderr_file(inv.deployment_id))
                location = InvocationService.deployment_location(inv.deployment_id, inv.blueprint_id)
                inv.instance_state = InvocationService.get_instance_state(location)
            return inv

        except BaseException as e:
            if isinstance(e, FileNotFoundError) or isinstance(e, AttributeError):
                return None
            else:
                raise e

    @classmethod
    def save_invocation(cls, invocation_id: uuid, inv: Invocation):
        SQL_database.update_deployment_log(invocation_id, inv)

    @classmethod
    def save_dot_opera_to_db(cls, inv: Invocation, location: Path) -> None:
        data = file_util.dir_to_json((location / '.opera'))
        SQL_database.save_opera_session_data(inv.deployment_id, data)

    @classmethod
    def get_dot_opera_from_db(cls, deployment_id: uuid, location: Path) -> None:
        dot_opera_data = SQL_database.get_opera_session_data(deployment_id)
        if not dot_opera_data:
            logger.error(f"sqldb_service.get_opera_session_data failed: deployment_id: {deployment_id}")
        file_util.json_to_dir(dot_opera_data['tree'], (location / '.opera'))

    @classmethod
    def prepare_location(cls, deployment_id: uuid, location: Path):
        """
        Prepare location with blueprint and session_data (.opera dir)
        """
        inv = SQL_database.get_deployment_status(deployment_id)
        if not CSAR_db.get_revision(inv.blueprint_id, location, inv.version_tag):
            logger.error(f'csardb_service.get_revision failed: blueprint_id: {inv.blueprint_id}, '
                         f'location: {location}, version_d: {inv.version_id}')
        InvocationService.get_dot_opera_from_db(deployment_id, location)

    @classmethod
    def get_instance_state(cls, location):
        json_dict = {}
        for file_path in Path(location / '.opera' / 'instances').glob("*"):
            parsed = json.load(open(file_path, 'r'))
            component_name = parsed['tosca_name']['data']
            json_dict[component_name] = parsed['state']['data']
        return json_dict
