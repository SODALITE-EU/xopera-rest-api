import shutil
import tempfile
import uuid
from pathlib import Path

from werkzeug.datastructures import FileStorage

from opera.api import gitCsarDB
from opera.api.blueprint_converters import csar_to_blueprint
from opera.api.blueprint_converters.blueprint2CSAR import validate_csar
from opera.api.log import get_logger
from opera.api.util.timestamp_util import datetime_now_to_string

logger = get_logger(__name__)


class GitDB:
    def __init__(self, **kwargs):
        self.connection = gitCsarDB.connect(**kwargs)

    def check_token_exists(self, blueprint_id: uuid) -> bool:
        """
        check if blueprint_id exists in database
        """
        return self.connection.CSAR_exists(blueprint_id)

    def version_exists(self, blueprint_id: uuid, version_id=None) -> bool:
        if not version_id:
            return self.connection.CSAR_exists(blueprint_id)
        return self.connection.tag_exists(blueprint_id, version_id)

    def add_tag(self, blueprint_id: uuid, commit_sha: str, tag: str, tag_msg: str):
        """
        Adds tag to specific commit in repo of blueprint_token
        """
        self.connection.add_tag(csar_token=blueprint_id, commit_sha=commit_sha, tag=tag, tag_msg=tag_msg)

    def get_tags(self, blueprint_id: uuid):
        """
        returns list of all tags
        """
        return self.connection.get_tags_list(csar_token=blueprint_id)

    def get_last_tag(self, blueprint_id: uuid):
        try:
            return self.get_tags(blueprint_id)[-1]
        except IndexError:
            return None

    def add_revision(self, blueprint_id: uuid = None, CSAR: FileStorage = None,
                     blueprint_path: Path = None, revision_msg: str = None, minor_to_increment: str = None):
        """
        saves blueprint into database. One of (CSAR, blueprint_path) must not be None. If blueprint_token is None,
        it is generated and returned together with version_id

        if minor_to_increment not None, minor version of tag will be incremented, else, major version (of all tags)
        will be incremented
        """
        token = blueprint_id or uuid.uuid4()
        path = Path(tempfile.mkdtemp()) if not blueprint_path else blueprint_path

        if CSAR is not None:
            workdir = Path(tempfile.mkdtemp())
            CSAR_path = workdir / Path(CSAR.filename)
            workdir.mkdir(parents=True, exist_ok=True)
            CSAR.save(CSAR_path.open('wb'))
            try:
                csar_to_blueprint(csar=CSAR_path, dst=path)
            except shutil.ReadError as e:
                logger.error(str(e))
                shutil.rmtree(str(workdir))
                return None, str(e)
            shutil.rmtree(str(workdir))
            try:
                validate_csar(path, raise_exceptions=True)
            except Exception as e:
                logger.error(str(e))
                shutil.rmtree(str(path))
                return None, str(e)

        elif blueprint_path is None:
            # both params cannot be None
            raise AttributeError('Both CSAR and blueprint path cannot be None')
        result = self.connection.save_CSAR(csar_path=path, csar_token=token,
                                           message=revision_msg, minor_to_increment=minor_to_increment)
        https_url = self.connection.get_repo_url(csar_token=token)
        users = self.connection.get_user_list(csar_token=token)
        if CSAR is not None:
            shutil.rmtree(str(path))

        return {
                   'message': "Revision saved to GitDB",
                   'blueprint_id': result['token'],
                   'url': https_url,
                   'commit_sha': result['commit_sha'],
                   'version_id': result['version_tag'],
                   'users': users,
                   'timestamp': datetime_now_to_string()
               }, None

    def get_revision(self, blueprint_id: uuid, dst: Path, version_id: str = None):
        """
        Retrieves blueprint and saves it to destination.
        - if version_tag not None -> retrieves by blueprint_token and version_tag
        - if both None -> retrieves just by blueprint_token
        In case of no results returns None
        """

        try:
            return self.connection.get_CSAR(csar_token=blueprint_id, version_tag=version_id, dst=dst)
        except FileNotFoundError:
            return None

    def add_member_to_blueprint(self, blueprint_id: uuid, username: str):
        try:
            self.connection.add_user(csar_token=blueprint_id, username=username)
            return True, None
        except Exception as e:
            return False, str(e)

    def delete_blueprint_user(self, blueprint_id: uuid, username: str):
        try:
            self.connection.delete_user(csar_token=blueprint_id, username=username)
            return True, None
        except Exception as e:
            return False, str(e)

    def get_blueprint_user_list(self, blueprint_id: uuid):
        try:
            return self.connection.get_user_list(csar_token=blueprint_id), None
        except Exception as e:
            return None, str(e)

    def get_repo_url(self, blueprint_id: uuid):
        try:
            return self.connection.get_repo_url(csar_token=blueprint_id), None
        except Exception as e:
            return None, str(e)

    def get_tag_msg(self, blueprint_id: uuid, tag_name=None):
        try:
            msg = self.connection.get_tag_msg(csar_token=blueprint_id, tag_name=tag_name)
            return msg, None
        except Exception as e:
            return None, str(e)

    def delete_blueprint(self, blueprint_id, version_id: str = None):
        """
        Deletes blueprint(s).
        - if version_tag not None -> delete by blueprint_token and version_tag
        - if both None -> delete all blueprints with blueprint_id
        Method returns number of deleted database entries
        """
        if version_id is not None:
            try:
                if self.connection.delete_tag(csar_token=blueprint_id, version_tag=version_id):
                    logger.debug(f'deleted tag {version_id}')
                    return 1, 200
                logger.debug(f'tag {version_id} does not exist')
                return 0, 404  # tag does not exist
            except FileNotFoundError as e:
                logger.debug(str(e))
                return 0, 404  # blueprint does not exist

        try:

            return self.connection.delete_repo(csar_token=blueprint_id), 200
        except FileNotFoundError as e:
            logger.debug(str(e))
            return 0, 404
        except Exception as e:
            logger.error(str(e))
            return 0, 500
