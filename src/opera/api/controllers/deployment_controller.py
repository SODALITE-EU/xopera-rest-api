from opera.api.service.sqldb_service import PostgreSQL
from opera.api.controllers import security_controller
from opera.api.controllers.background_invocation import InvocationService
from opera.api.controllers.background_invocation import InvocationWorkerProcess
from opera.api.log import get_logger
from opera.api.openapi.models import InvocationState
from opera.api.openapi.models import OperationType, Invocation
from opera.api.settings import Settings
from opera.api.util import xopera_util

logger = get_logger(__name__)
invocation_service = InvocationService(workers_num=Settings.invocation_service_workers)


@security_controller.check_role_auth_deployment
def get_deploy_log(deployment_id):
    """Get deployment history

    :param deployment_id: Id of deployment
    :type deployment_id:

    :rtype: List[Invocation]
    """
    history = PostgreSQL.get_deployment_history(deployment_id)
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
    if not inv:
        return "Job not found", 404
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
    username = security_controller.get_username()

    inv = PostgreSQL.get_deployment_status(deployment_id)

    if inv.state in [InvocationState.PENDING, InvocationState.IN_PROGRESS]:
        return f"Previous operation on this deployment still running", 403

    result = invocation_service.invoke(
        operation_type=OperationType.DEPLOY_CONTINUE,
        blueprint_id=inv.blueprint_id,
        version_id=inv.version_id,
        deployment_label=inv.deployment_label,
        deployment_id=deployment_id,
        workers=workers,
        inputs=inputs,
        clean_state=clean_state,
        username=username,
        access_token=xopera_util.get_access_token()
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
    username = security_controller.get_username()

    result = invocation_service.invoke(
        operation_type=OperationType.DEPLOY_FRESH,
        blueprint_id=blueprint_id,
        version_id=version_id,
        deployment_label=deployment_label,
        workers=workers,
        inputs=inputs,
        username=username,
        access_token=xopera_util.get_access_token()
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
def post_undeploy(deployment_id, workers=1, force=False):
    """Undeploy deployment.

    :param deployment_id: Id of deployment
    :type deployment_id:
    :param workers: Number of workers
    :type workers: int
    :param force: Undeploy forcefully (for stuck deployments).
    :type force: bool

    :rtype: Invocation
    """
    inputs = xopera_util.get_preprocessed_inputs()
    username = security_controller.get_username()

    inv = PostgreSQL.get_deployment_status(deployment_id)
    if not force:
        if inv.state in [InvocationState.PENDING, InvocationState.IN_PROGRESS]:
            return f"Previous operation on this deployment still running", 403

    result = invocation_service.invoke(
        operation_type=OperationType.UNDEPLOY,
        blueprint_id=inv.blueprint_id,
        version_id=inv.version_id,
        deployment_label=inv.deployment_label,
        deployment_id=deployment_id,
        workers=workers,
        inputs=inputs,
        username=username,
        access_token=xopera_util.get_access_token()
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
    username = security_controller.get_username()

    inv = PostgreSQL.get_deployment_status(deployment_id)
    if inv.state in [InvocationState.PENDING, InvocationState.IN_PROGRESS]:
        return f"Previous operation on this deployment still running", 403

    result = invocation_service.invoke(
        operation_type=OperationType.UPDATE,
        blueprint_id=blueprint_id,
        version_id=version_id,
        deployment_id=deployment_id,
        workers=workers,
        inputs=inputs,
        username=username,
        access_token=xopera_util.get_access_token()
    )
    logger.info(f"Updating '{deployment_id}' with blueprint '{blueprint_id}', version_id: {version_id}")
    return result, 202


@security_controller.check_role_auth_deployment
def delete_deployment(deployment_id, force=False):
    """Delete all deployment data

    This endpoint deletes all data, about deployment, that are stored on xOpera REST API. It does not modify actual
    deployed instance. To undeploy actual instance, use /deployment/{deployment_id}/undeploy

    :param deployment_id: Id of deployment
    :type deployment_id:
    :param force: Force-remove deployment data
    :type force: bool

    :rtype: str
    """

    inv = PostgreSQL.get_deployment_status(deployment_id)
    if not force:
        if inv.state in [InvocationState.PENDING, InvocationState.IN_PROGRESS]:
            return f"Previous operation on this deployment still running", 403

    success_deployment = PostgreSQL.delete_deployment(deployment_id)
    success_session_data = PostgreSQL.delete_opera_session_data(deployment_id)
    if not (success_deployment and success_session_data):
        return "Failed to delete deployment", 500

    return 'Deployment deleted', 200
