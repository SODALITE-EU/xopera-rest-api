from opera.api.cli import SQL_database
from opera.api.controllers import security_controller
from opera.api.controllers.background_invocation import InvocationService
from opera.api.controllers.background_invocation import InvocationWorkerProcess
from opera.api.log import get_logger
from opera.api.openapi.models import InvocationState
from opera.api.openapi.models import OperationType, Invocation
from opera.api.settings import Settings
# from opera.api.openapi.models.deployment_exists import DeploymentExists
from opera.api.util import xopera_util

logger = get_logger(__name__)
invocation_service = InvocationService(workers_num=Settings.invocation_service_workers)


# def deployment_exists(blueprint_id, version_id=None, inputs_file=None):
#     """Check if deployment exists
#
#     :param blueprint_id: Id of blueprint
#     :type blueprint_id:
#     :param version_id: Id of blueprint version
#     :type version_id: str
#     :param inputs_file: File with inputs TOSCA blueprint
#     :type inputs_file: str
#
#     :rtype: DeploymentExists
#     """
#     # TODO implement
#     return 'Not implemented'


@security_controller.check_role_auth_deployment
def get_deploy_log(deployment_id):
    """Get deployment history

    :param deployment_id: Id of deployment
    :type deployment_id: 

    :rtype: List[Invocation]
    """
    history = SQL_database.get_deployment_history(deployment_id)
    if not history:
        return "History not found", 404
    return history, 200


@security_controller.check_role_auth_deployment
def get_status(deployment_id):
    """Get deployment status

    :param deployment_id: Id of deployment
    :type deployment_id: 

    :rtype: Invocation
    """
    inv = invocation_service.load_invocation(deployment_id)
    return inv, 200


@security_controller.check_role_auth_deployment
def post_deploy_continue(deployment_id, workers=1, clean_state=False):
    """Continue deploy

    :param deployment_id: Id of deployment
    :type deployment_id: 
    :param workers: Number of workers
    :type workers: int
    :param clean_state: Clean previous state and start over
    :type clean_state: bool

    :rtype: Invocation
    """

    inputs = xopera_util.get_preprocessed_inputs()

    inv = SQL_database.get_deployment_status(deployment_id)

    if inv.state in [InvocationState.PENDING, InvocationState.IN_PROGRESS]:
        return f"Previous operation on this deployment still running", 403

    result = invocation_service.invoke(
        operation_type=OperationType.DEPLOY_CONTINUE,
        blueprint_id=inv.blueprint_id,
        version_id=inv.version_id,
        deployment_id=deployment_id,
        workers=workers,
        inputs=inputs,
        clean_state=clean_state
    )
    logger.info(f"Deploying '{inv.blueprint_id}', version_id: {inv.version_id}")
    return result, 202


@security_controller.check_role_auth_blueprint
def post_deploy_fresh(blueprint_id, version_id=None, deployment_label=None, workers=None):  # noqa: E501
    """Initialize deployment and deploy

    :param blueprint_id: Id of blueprint
    :type blueprint_id:
    :param version_id: version_tag to deploy
    :type version_id: str
    :param deployment_label: Human-readable deployment label
    :type deployment_label: str
    :param workers: Number of workers
    :type workers: int

    :rtype: Invocation
    """
    inputs = xopera_util.get_preprocessed_inputs()

    result = invocation_service.invoke(
        operation_type=OperationType.DEPLOY_FRESH,
        blueprint_id=blueprint_id,
        version_id=version_id,
        deployment_label=deployment_label,
        workers=workers,
        inputs=inputs
    )
    logger.info(f"Deploying '{blueprint_id}', version_id: {version_id}")
    return result, 202


@security_controller.check_role_auth_blueprint
@security_controller.check_role_auth_deployment
def post_diff(deployment_id, blueprint_id, version_id=None):
    """Calculate diff between deployment and new blueprint.

    Calculates the diff between Deployed instance model (DI1) and New blueprint version (DB2 = B2 + V2 + I2)

    :param deployment_id: Id of Deployed instance model (DI1)
    :type deployment_id: 
    :param blueprint_id: Id of The new blueprint (B2)
    :type blueprint_id: 
    :param version_id: Id of version of The new blueprint (V2)
    :type version_id: str

    :rtype: object
    """
    inputs = xopera_util.get_preprocessed_inputs()

    return InvocationWorkerProcess.diff(deployment_id, blueprint_id, version_id, inputs).outputs(), 200


@security_controller.check_role_auth_deployment
def post_undeploy(deployment_id, workers=1):
    """Undeploy deployment.

    :param deployment_id: Id of deployment
    :type deployment_id: 
    :param workers: Number of workers
    :type workers: int

    :rtype: Invocation
    """
    inputs = xopera_util.get_preprocessed_inputs()

    inv = SQL_database.get_deployment_status(deployment_id)
    if inv.state in [InvocationState.PENDING, InvocationState.IN_PROGRESS]:
        return f"Previous operation on this deployment still running", 403

    result = invocation_service.invoke(
        operation_type=OperationType.UNDEPLOY,
        blueprint_id=inv.blueprint_id,
        version_id=inv.version_id,
        deployment_id=deployment_id,
        workers=workers,
        inputs=inputs
    )
    logger.info(f"Undeploying '{deployment_id}'")
    return result, 202


@security_controller.check_role_auth_blueprint
@security_controller.check_role_auth_deployment
def post_update(deployment_id, blueprint_id, version_id=None, workers=1):
    """Update deployment with new blueprint.

    Deploys Instance model (DI2), where DI2 &#x3D; diff(DI1, (B2,V2,I2))

    :param deployment_id: Id of Deployed instance model (DI1)
    :type deployment_id: 
    :param blueprint_id: Id of the new blueprint (B2)
    :type blueprint_id: 
    :param version_id: Id of version of the new blueprint (V2)
    :type version_id: str
    :param workers: Number of workers
    :type workers: int

    :rtype: Invocation
    """
    inputs = xopera_util.get_preprocessed_inputs()

    inv = SQL_database.get_deployment_status(deployment_id)
    if inv.state in [InvocationState.PENDING, InvocationState.IN_PROGRESS]:
        return f"Previous operation on this deployment still running", 403

    result = invocation_service.invoke(
        operation_type=OperationType.UPDATE,
        blueprint_id=blueprint_id,
        version_id=version_id,
        deployment_id=deployment_id,
        workers=workers,
        inputs=inputs
    )
    logger.info(f"Updating '{deployment_id}' with blueprint '{blueprint_id}', version_id: {version_id}")
    return result, 202
