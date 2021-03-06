import shutil
import tempfile
import time
import uuid
from pathlib import Path

import git

from . import tag_util
from .connectors import Connector


class GitCsarDB:
    class GitCsarDBError(Exception):
        pass

    class UnsupportedConnectorType(GitCsarDBError):
        pass

    def __init__(self, connector: Connector, workdir=tempfile.mkdtemp(), repo_prefix='gitDB_',
                 commit_name="SODALITE-xOpera-REST-API", commit_mail="some-email@xlab.si",
                 guest_permissions="reporter", timeout=60):
        self.git_connector = connector
        self.workdir = Path(workdir)
        self.workdir.mkdir(exist_ok=True, parents=True)
        self.repo_prefix = repo_prefix
        self.guest_permissions = guest_permissions
        self.commit_name = commit_name
        self.commit_mail = commit_mail
        self.timeout = timeout

    def generate_repo_path(self, csar_token):
        return self.workdir / Path(str(uuid.uuid4())) / Path(self.repo_name(csar_token))

    def save_CSAR(self, csar_path: Path, csar_token: uuid, message: str = None, minor_to_increment: str = None):
        if not self.CSAR_exists(csar_token):
            self.git_connector.init_repo(self.repo_name(csar_token))

        repo_path = self.generate_repo_path(csar_token)
        start_time = time.time()
        while True:
            try:
                shutil.rmtree(path=repo_path, ignore_errors=True)
                repo = self.git_connector.clone(repo_name=self.repo_name(csar_token), repo_dst=repo_path)

                repo.config_writer().set_value("user", "name", self.commit_name).release()
                repo.config_writer().set_value("user", "email", self.commit_mail).release()

                try:
                    repo.git.rm('*')
                except git.exc.GitCommandError:
                    pass
                self.copy_content(csar_path, repo_path)
                repo.git.add('--all')
                if minor_to_increment:
                    tag_name = tag_util.next_minor(repo.tags, minor_to_increment)
                else:
                    tag_name = tag_util.next_major(repo.tags)
                commit_msg = f'gitCsarDB: {message or tag_name}'
                commit_obj = repo.index.commit(message=commit_msg)
                commit_sha = str(commit_obj)
                repo.remotes.origin.push()
                self.add_tag(csar_token, commit_sha, tag_name, commit_msg)
                break
            except Exception as e:

                if time.time() - start_time > self.timeout:
                    # 5 min
                    shutil.rmtree(path=repo_path)
                    return {
                        'success': False,
                        'message': f'Timeout of {self.timeout}s exceeded',
                        'exception': str(e)
                    }
                else:
                    # apparently, there was a fail in pushing repo back to remote. Just repeat procedure.
                    pass

        shutil.rmtree(path=repo_path)
        return {
            'success': True,
            'token': str(csar_token),
            'version_tag': tag_name,
            'commit_sha': commit_sha
        }

    def add_tag(self, csar_token: uuid, commit_sha: str, tag: str, tag_msg: str = None):
        self.git_connector.add_tag(repo_name=self.repo_name(csar_token), commit_sha=commit_sha,
                                   tag=tag, tag_msg=tag_msg)

    def get_CSAR(self, csar_token, version_tag=None, dst: Path = None):
        if not self.CSAR_exists(csar_token):
            raise FileNotFoundError(f"CSAR with token '{csar_token}' not found")

        git_clone_path = self.generate_repo_path(csar_token)
        shutil.rmtree(path=git_clone_path, ignore_errors=True)
        self.git_connector.clone(repo_name=self.repo_name(csar_token), repo_dst=git_clone_path)
        if version_tag:
            try:
                g = git.Git(git_clone_path)
                g.init()
                g.checkout(version_tag)
            except Exception:
                raise FileNotFoundError(f"Tag '{version_tag}' not found")
        repo_path = dst or git_clone_path
        if repo_path != git_clone_path:
            shutil.copytree(git_clone_path, repo_path, dirs_exist_ok=True)
            # remove .git dir
            shutil.rmtree(Path(repo_path / Path(".git")))
            shutil.rmtree(git_clone_path)

        return repo_path

    def delete_tag(self, csar_token: uuid, version_tag):
        if not self.CSAR_exists(csar_token):
            raise FileNotFoundError(f"CSAR with token '{csar_token}' not found")
        return self.git_connector.delete_tag(repo_name=self.repo_name(csar_token), tag=version_tag)

    def delete_repo(self, csar_token: uuid):
        if not self.CSAR_exists(csar_token):
            raise FileNotFoundError(f"CSAR with token '{csar_token}' not found")

        return self.git_connector.delete_repo(repo_name=self.repo_name(csar_token))

    def get_repo_url(self, csar_token: uuid):
        repo_name = self.repo_name(csar_token)
        return self.git_connector.get_repo_url(repo_name)

    def add_user(self, csar_token: uuid, username: str):
        repo_name = self.repo_name(csar_token)
        return self.git_connector.add_collaborator(repo_name, username, permissions=self.guest_permissions)

    def delete_user(self, csar_token: uuid, username: str):
        repo_name = self.repo_name(csar_token)
        return self.git_connector.delete_collaborator(repo_name, username)

    def get_user_list(self, csar_token: uuid):
        repo_name = self.repo_name(csar_token)
        return self.git_connector.get_collaborators(repo_name)

    def CSAR_exists(self, csar_token):
        repo_name = self.repo_name(csar_token)
        if repo_name is None:
            return False
        return self.git_connector.repo_exist(repo_name)

    def get_commits_list(self, csar_token):
        repo_name = self.repo_name(csar_token)
        return self.git_connector.get_commits_list(repo_name)

    def get_tag_msg(self, csar_token, tag_name=None):
        repo_name = self.repo_name(csar_token)
        return self.git_connector.get_tag_msg(repo_name=repo_name, tag=tag_name)

    def tag_exists(self, csar_token, tag_name):
        repo_name = self.repo_name(csar_token)
        return self.git_connector.tag_exists(repo_name=repo_name, tag_name=tag_name)

    def get_tags_list(self, csar_token):
        repo_path = self.generate_repo_path(csar_token)
        shutil.rmtree(path=repo_path, ignore_errors=True)
        repo = self.git_connector.clone(repo_name=self.repo_name(csar_token), repo_dst=repo_path)
        tags = [str(tag) for tag in repo.tags]
        shutil.rmtree(path=repo_path)
        return tags

    @staticmethod
    def copy_content(src: Path, dst: Path):
        for obj in src.glob("*"):

            if obj.is_dir():
                if obj.name != '.git':
                    shutil.copytree(str(obj), str(dst / Path(obj.name)))
            else:
                shutil.copy(str(obj), str(dst))

    @staticmethod
    def make_repo_emtpy(repo_path: Path):
        for obj in repo_path.glob("*"):
            if obj.is_dir():
                if obj.name != '.git':
                    shutil.rmtree(str(obj))
                    # obj.rmdir()
            else:
                obj.unlink()

    def repo_name(self, csar_token: uuid):
        return f'{self.repo_prefix}{csar_token}'

    def csar_token(self, repo_name: str):
        if not repo_name.startswith(self.repo_prefix):
            return None
        return uuid.UUID(repo_name[len(self.repo_prefix):])
