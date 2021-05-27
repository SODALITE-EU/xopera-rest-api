import connexion

from opera.api.controllers import security_controller
from opera.api.controllers.background_invocation import InvocationWorkerProcess
from opera.api.log import get_logger
from opera.api.openapi.models.blueprint_validation import BlueprintValidation
from opera.api.util import xopera_util

logger = get_logger(__name__)


@security_controller.check_role_auth_blueprint
def validate_existing(blueprint_id):
    """Validate last version of existing blueprint.

    Validates TOSCA service template

    :param blueprint_id: Id of TOSCA blueprint
    :type blueprint_id:

    :rtype: str
    """
    inputs = xopera_util.get_preprocessed_inputs()

    exception = InvocationWorkerProcess.validate(blueprint_id, None, inputs)
    blueprint_valid = exception is None
    return BlueprintValidation(blueprint_valid, exception), 200


@security_controller.check_role_auth_blueprint
def validate_existing_version(blueprint_id, version_id):
    """Validate specific version of existing blueprint.

    Validates TOSCA service template

    :param blueprint_id: Id of TOSCA blueprint
    :type blueprint_id:
    :param version_id: Id of blueprint version
    :type version_id: str

    :rtype: str
    """
    inputs = xopera_util.get_preprocessed_inputs()

    exception = InvocationWorkerProcess.validate(blueprint_id, version_id, inputs)
    blueprint_valid = exception is None
    return BlueprintValidation(blueprint_valid, exception), 200


def validate_new():
    """Validate new blueprint.

    Validates TOSCA service template

    :rtype: str
    """
    inputs = xopera_util.get_preprocessed_inputs()
    csar_file = connexion.request.files['CSAR']

    exception = InvocationWorkerProcess.validate_new(csar_file, inputs)
    blueprint_valid = exception is None
    return BlueprintValidation(blueprint_valid, exception), 200
