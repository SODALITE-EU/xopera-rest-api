import datetime
import json
import multiprocessing
import os
import shutil
import sys
import tempfile
import traceback
import uuid
from pathlib import Path
from typing import Optional

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
from werkzeug.datastructures import FileStorage

from opera.api.blueprint_converters import csar_to_blueprint
from opera.api.blueprint_converters.blueprint2CSAR import entry_definitions
from opera.api.cli import CSAR_db, SQL_database
from opera.api.log import get_logger
from opera.api.openapi.models import Invocation, InvocationState, OperationType
from opera.api.settings import Settings
from opera.api.util import xopera_util, file_util

logger = get_logger(__name__)

class MissingDeploymentDataError(BaseException):
    pass

class ExtendedInvocation(Invocation):
    def __init__(self, access_token=None, blueprint_id=None,
                 version_id=None, deployment_id=None, user_id=None,
                 deployment_label=None, state=None, operation=None,
                 timestamp_submission=None, timestamp_start=None,
                 timestamp_end=None, inputs=None, instance_state=None,
                 outputs=None, exception=None, stdout=None,
                 stderr=None, workers=None, clean_state=None):
        super().__init__(blueprint_id=blueprint_id, version_id=version_id, deployment_id=deployment_id,
                         user_id=user_id, deployment_label=deployment_label, state=state, operation=operation,
                         timestamp_submission=timestamp_submission, timestamp_start=timestamp_start,
                         timestamp_end=timestamp_end, inputs=inputs, instance_state=instance_state,
                         outputs=outputs, exception=exception, stdout=stdout, stderr=stderr,
                         workers=workers, clean_state=clean_state)
        self.access_token = access_token


class InvocationWorkerProcess:

    @staticmethod
    def run_internal(work_queue: multiprocessing.Queue):

        while True:
            inv: ExtendedInvocation = work_queue.get(block=True)
            inv.timestamp_start = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

            invocation_id = SQL_database.get_last_invocation_id(inv.deployment_id)
            location = InvocationService.deployment_location(inv.deployment_id, inv.blueprint_id)

            inv.state = InvocationState.IN_PROGRESS
            InvocationService.save_invocation(invocation_id, inv)

            # for catching stdout&err
            file_stdout = open(InvocationService.stdout_file(inv.deployment_id), "w")
            file_stderr = open(InvocationService.stderr_file(inv.deployment_id), "w")

            # Copy file descriptors of stdout&&err for later restoration
            stdout_copy = os.dup(1)
            stderr_copy = os.dup(2)
            # Reroute stdout&err to file_stdout and file_stderr,
            os.dup2(file_stdout.fileno(), 1)
            os.dup2(file_stderr.fileno(), 2)

            try:
                if inv.operation == OperationType.DEPLOY_FRESH:
                    outputs = InvocationWorkerProcess._deploy_fresh(location, inv)
                elif inv.operation == OperationType.DEPLOY_CONTINUE:
                    outputs = InvocationWorkerProcess._deploy_continue(location, inv)
                elif inv.operation == OperationType.UNDEPLOY:
                    InvocationWorkerProcess._undeploy(location, inv)
                    outputs = None
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

                # Restore stdout&&err
                os.dup2(stdout_copy, 1)
                os.dup2(stderr_copy, 2)

                inv.timestamp_end = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

                if InvocationService.deployment_exists(inv):
                    InvocationService.save_dot_opera_to_db(inv, location)
                    InvocationService.save_invocation(invocation_id, inv)
                else:
                    logger.error(f"Deployment with deployment_id={inv.deployment_id} does not exist any more, it could "
                                 f"have been deleted with force, therefore I cannot save following invocation to DB:"
                                 f"\n" + inv.to_str())

                # clean
                shutil.rmtree(location)
                shutil.rmtree(InvocationService.stdstream_dir(inv.deployment_id))

    @staticmethod
    def _deploy_fresh(location: Path, inv: ExtendedInvocation):
        CSAR_db.get_revision(inv.blueprint_id, location, inv.version_id)

        with xopera_util.cwd(location):
            try:
                if inv.user_id and Settings.secure_workdir:
                    xopera_util.setup_user([location], inv.user_id, inv.access_token)
                opera_storage = Storage.create(".opera")
                service_template = str(entry_definitions(location))
                opera_deploy(service_template, inv.inputs, opera_storage,
                             verbose_mode=False, num_workers=inv.workers, delete_existing_state=True)

                outputs = opera_outputs(opera_storage)
                return outputs
            finally:
                if inv.user_id and Settings.secure_workdir:
                    xopera_util.cleanup_user()

    @staticmethod
    def _deploy_continue(location: Path, inv: ExtendedInvocation):

        # get blueprint
        CSAR_db.get_revision(inv.blueprint_id, location, inv.version_id)
        # get session data (.opera)
        InvocationService.get_dot_opera_from_db(inv.deployment_id, location)

        with xopera_util.cwd(location):
            try:
                if inv.user_id and Settings.secure_workdir:
                    xopera_util.setup_user([location], inv.user_id, inv.access_token)
                opera_storage = Storage.create(".opera")
                service_template = str(entry_definitions(location))
                opera_deploy(service_template, inv.inputs, opera_storage,
                             verbose_mode=False, num_workers=inv.workers, delete_existing_state=inv.clean_state)
                outputs = opera_outputs(opera_storage)
                return outputs
            finally:
                if inv.user_id and Settings.secure_workdir:
                    xopera_util.cleanup_user()

    @staticmethod
    def _undeploy(location: Path, inv: ExtendedInvocation):

        # get blueprint
        CSAR_db.get_revision(inv.blueprint_id, location, inv.version_id)
        # get session data (.opera)
        if not InvocationService.get_dot_opera_from_db(inv.deployment_id, location):
            raise MissingDeploymentDataError('Could not get .opera data from previous job, aborting...')

        with xopera_util.cwd(location):
            try:
                if inv.user_id and Settings.secure_workdir:
                    xopera_util.setup_user([location], inv.user_id, inv.access_token)
                opera_storage = Storage.create(".opera")
                if inv.inputs:
                    opera_storage.write_json(inv.inputs, "inputs")
                opera_undeploy(opera_storage, verbose_mode=False, num_workers=inv.workers)
                # Outputs in undeployment are not returned
                return None
            finally:
                if inv.user_id and Settings.secure_workdir:
                    xopera_util.cleanup_user()

    @staticmethod
    def _update(location: Path, inv: ExtendedInvocation):

        storage_old, location_old, storage_new, location_new = InvocationWorkerProcess.prepare_two_workdirs(
            inv.deployment_id, inv.blueprint_id, inv.version_id, inv.inputs, location)

        assert location_new == str(location)

        with xopera_util.cwd(location_new):
            try:
                if inv.user_id and Settings.secure_workdir:
                    xopera_util.setup_user([location_old, location_new], inv.user_id, inv.access_token)
                instance_diff = opera_diff_instances(storage_old, location_old,
                                                     storage_new, location_new,
                                                     opera_TemplateComparer(), opera_InstanceComparer(),
                                                     verbose_mode=False)

                opera_update(storage_old, location_old,
                             storage_new, location_new,
                             opera_InstanceComparer(), instance_diff,
                             verbose_mode=False, num_workers=inv.workers, overwrite=False)
                outputs = opera_outputs(storage_new)
                return outputs
            finally:
                if inv.user_id and Settings.secure_workdir:
                    xopera_util.cleanup_user()
                shutil.rmtree(location_old)
                # location_new is needed in __run_internal and deleted afterwards

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
                    service_template = Path(location) / entry_definitions(location)
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
                    service_template = Path(location) / entry_definitions(location)
                    opera_validate(service_template, inputs)
                return None
        except Exception as e:
            return "{}: {}".format(e.__class__.__name__, xopera_util.mask_workdirs([location, csar_workdir], str(e)), )

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
        self.workers_pool = multiprocessing.Pool(workers_num, InvocationWorkerProcess.run_internal, (self.work_queue,))

    def invoke(self, operation_type: OperationType, blueprint_id: uuid, version_id: uuid,
               workers: int, inputs: dict, deployment_id: uuid = None, username: str = None,
               clean_state: bool = None, deployment_label: str = None, access_token: str = None) -> Invocation:

        now = datetime.datetime.now(tz=datetime.timezone.utc)
        logger.info("Invoking %s with ID %s at %s", operation_type, deployment_id, now.isoformat())

        invocation_id = uuid.uuid4()

        inv = ExtendedInvocation()
        inv.blueprint_id = blueprint_id
        inv.deployment_label = deployment_label
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
        inv.user_id = username
        inv.access_token = access_token

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
        # TODO check if it can introduce errors, then catch error
        inv = SQL_database.get_deployment_status(deployment_id)
        if not inv:
            return None
        try:
            if inv.state == InvocationState.IN_PROGRESS:
                inv.stdout = InvocationWorkerProcess.read_file(cls.stdout_file(inv.deployment_id))
                inv.stderr = InvocationWorkerProcess.read_file(cls.stderr_file(inv.deployment_id))
                location = InvocationService.deployment_location(inv.deployment_id, inv.blueprint_id)
                inv.instance_state = InvocationService.get_instance_state(location)

        except BaseException as e:
            if not isinstance(e, FileNotFoundError) and not isinstance(e, AttributeError):
                logger.error(str(e))
            else:
                logger.warning(str(e))

        return inv

    @classmethod
    def deployment_exists(cls, inv: Invocation) -> bool:
        """Check if records about deployment exist in DB"""
        return SQL_database.get_deployment_status(inv.deployment_id) is not None

    @classmethod
    def save_invocation(cls, invocation_id: uuid, inv: Invocation):
        SQL_database.update_deployment_log(invocation_id, inv)

    @classmethod
    def save_dot_opera_to_db(cls, inv: Invocation, location: Path) -> None:
        data = file_util.dir_to_json((location / '.opera'))
        SQL_database.save_opera_session_data(inv.deployment_id, data)

    @classmethod
    def get_dot_opera_from_db(cls, deployment_id: uuid, location: Path) -> bool:
        dot_opera_data = SQL_database.get_opera_session_data(deployment_id)
        if not dot_opera_data:
            logger.error(f"sqldb_service.get_opera_session_data failed: deployment_id: {deployment_id}")
            return False
        else:
            file_util.json_to_dir(dot_opera_data['tree'], (location / '.opera'))
            return True

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
