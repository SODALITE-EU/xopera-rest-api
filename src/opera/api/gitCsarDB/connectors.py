import json
import shutil
from pathlib import Path

import git
import gitlab
from github import Github, GithubException
from gitlab import Gitlab


class Connector:
    class ConnectorError(Exception):
        pass

    class RepoExistsError(ConnectorError):
        pass

    class GitAuthenticationError(ConnectorError):
        pass

    class RepoNotFoundError(ConnectorError):
        pass

    class UserNotFoundError(ConnectorError):
        pass

    class PermissionDenied(ConnectorError):
        pass

    def __str__(self):
        return "abstract class Connector"

    def init_repo(self, repo_name: str):
        """
        initializes repository
        Args:
            repo_name: desired name of repo

        Returns: init_success: bool

        """
        pass

    def repo_exist(self, repo_name: str):
        """
        checks if repo {repo_name} exists
        Args:
            repo_name: name of repository

        Returns: repo_exist: bool

        """
        pass

    def tag_exists(self, repo_name: str, tag_name) -> bool:
        """
        checks if repo {repo_name} exists and has tag {tag_name}
        Args:
            repo_name: name of repository
            tag_name: name of tag

        Returns: tag_exists: bool

        """
        pass

    def add_collaborator(self, repo_name: str, username: str, permissions: str = 'developer'):
        """
        Adds user as collaborator to repository.
        Args:
            permissions: either developer or reporter. Adopted after gitlab permissions
            repo_name: name of repository
            username: username of user to be added to repo

        Returns: success: bool

        """

        pass

    def delete_collaborator(self, repo_name: str, username: str):
        """
        Deletes user as from repository.
        Args:
            repo_name: name of repository
            username: username of user to be added to repo

        Returns: success: bool

        """

        pass

    def get_collaborators(self, repo_name):
        """
        returns list of collaborators for specific project
        Args:
            repo_name: name of repo

        Returns: collaborators (list of strings)

        """
        pass

    def get_repo_url(self, repo_name: str):
        """
        returns url of repo
        """
        pass

    def add_tag(self, repo_name: str, commit_sha: str, tag: str, tag_msg: str = None):
        """
        adds tag, which points to specific commit to repo
        """
        pass

    def delete_tag(self, repo_name: str, tag: str):
        """
        deletes tag from repo
        """
        pass

    def delete_repo(self, repo_name: str):
        """
        deletes repo
        Args:
            repo_name: name of repo to be deleted
        Returns: success: bool

        """
        pass

    def clone(self, repo_name, repo_dst: Path):
        """
        clones repo
        Args:
            repo_name: repo name to be cloned
            repo_dst: path to dir, where repo will be cloned.

        Returns: success: path to cloned repo

        """
        pass

    def get_commits_list(self, repo_name):
        """
        Gets list of commits, (pairs (commit_msg, commit_sha))
        """
        pass

    def get_tag_msg(self, repo_name, tag=None):
        """
        Gets commit message of commit with tag=[tag] or last commit
        """
        pass


class MockConnector(Connector):
    """
    Mock git connector, that maintains git repos on local computer
    """

    def __init__(self, workdir: Path):
        self.workdir = workdir
        if not self.workdir.exists():
            self.workdir.mkdir(parents=True)
        self.collab_file = self.workdir / 'collaborators.json'
        if not self.collab_file.exists():
            with self.collab_file.open('w') as file:
                json.dump({}, file)

    def __str__(self):
        return f"MockConnector, workdir: {self.workdir}"

    def init_repo(self, repo_name: str):

        repo_path = self.workdir / Path(repo_name)
        if repo_path.exists():
            return False  # repo already exist, could not initialize
        repo = git.Repo.init(repo_path, bare=True)
        collaborators = json.load(self.collab_file.open('r'))
        collaborators[repo_name] = []
        json.dump(collaborators, self.collab_file.open('w'))
        repo.config_writer().set_value("user", "name", "MockConnector").release()
        repo.config_writer().set_value("user", "email", "no-reply@xlab.si").release()
        return True

    def repo_exist(self, repo_name: str):

        repo_path = self.workdir / Path(repo_name)
        return repo_path.exists()

    def add_collaborator(self, repo_name: str, username: str, permissions='developer'):
        collaborators = json.load(self.collab_file.open('r'))
        if repo_name not in collaborators:
            return False
        if username in collaborators[repo_name]:
            return True
        collaborators[repo_name].append(username)
        json.dump(collaborators, self.collab_file.open('w'))
        return True

    def delete_collaborator(self, repo_name: str, username: str):
        collaborators = json.load(self.collab_file.open('r'))
        if repo_name not in collaborators:
            return False
        if username in collaborators[repo_name]:
            collaborators[repo_name].remove(username)
            json.dump(collaborators, self.collab_file.open('w'))
            return True
        return False

    def get_collaborators(self, repo_name):

        if not self.repo_exist(repo_name):
            return []
        return json.load(self.collab_file.open('r'))[repo_name]

    def get_repo_url(self, repo_name: str):
        repo_path = Path(f"{str(self.workdir)}/{repo_name}")
        if repo_path.exists():
            return str(repo_path)
        return None

    def delete_repo(self, repo_name: str):

        if not self.repo_exist(repo_name):
            return 0
        repo_path = self.workdir / Path(repo_name)
        n_of_tags = len(git.Repo(self.get_repo_url(repo_name)).tags)
        shutil.rmtree(repo_path, ignore_errors=True)
        return n_of_tags

    def add_tag(self, repo_name: str, commit_sha: str, tag: str, tag_msg: str = None):
        repo = git.Repo(self.get_repo_url(repo_name))
        new_tag = repo.create_tag(path=tag, ref=commit_sha, message=tag_msg)

    def delete_tag(self, repo_name: str, tag: str):
        repo = git.Repo(self.get_repo_url(repo_name))
        try:
            repo.delete_tag(tag)
            return True
        except git.exc.GitCommandError:
            return False

    def clone(self, repo_name, repo_dst: Path):

        if not self.repo_exist(repo_name):
            return None
        local_link = f"{str(self.workdir)}/{repo_name}"
        return git.Repo.clone_from(local_link, str(repo_dst))

    def get_commits_list(self, repo_name):
        """
        Gets list of commits, (pairs (commit_msg, commit_sha))
        """
        repo = git.Repo(self.get_repo_url(repo_name))
        commits = list(repo.iter_commits('master'))
        return [(commit.hexsha, commit.message) for commit in commits]

    def get_tag_msg(self, repo_name, tag=None):
        """
        Gets tag/release message of release with tag=[tag] or last release
        """
        repo = git.Repo(self.get_repo_url(repo_name))

        tags = repo.tags

        if tag:
            try:
                return [tagref.tag.message for tagref in tags if str(tagref) == tag][0]

            except IndexError:
                return None
        try:
            return tags[-1].tag.message
        except IndexError:
            return None

    def tag_exists(self, repo_name: str, tag_name):
        if not self.repo_exist(repo_name):
            return False

        repo = git.Repo(self.get_repo_url(repo_name))
        tags = repo.tags
        return any(str(tag) == tag_name for tag in tags)


class GitlabConnector(Connector):
    def __init__(self, url, auth_token):
        self.auth_token = auth_token
        self.url = url
        try:
            gl = Gitlab(url=url, private_token=auth_token)
            gl.projects.list()
        except gitlab.exceptions.GitlabAuthenticationError as e:
            raise self.GitAuthenticationError(f"Could not authenticate to Gitlab at {self.url}: {str(e)}")

    def __str__(self):
        return f"GitlabConnector, url: {self.url}, auth_token: {'****' if self.auth_token else None}"

    def init_repo(self, repo_name: str):
        gl = Gitlab(url=self.url, private_token=self.auth_token)
        try:
            project = gl.projects.create({'name': repo_name, 'visibility': "private"})
        except gitlab.exceptions.GitlabCreateError as e:
            raise self.RepoExistsError(
                f"Could not create repo {repo_name} at {self.url}, repo already exists: {str(e)}")

    def __project_id(self, project_name):
        gl = Gitlab(url=self.url, private_token=self.auth_token)
        projects = gl.projects.list(search=f"{project_name}")

        for project in projects:
            if project.name == project_name:
                return project.id

        raise self.RepoNotFoundError(f'Found {len(projects)} projects with name "{project_name}": '
                                     f'{[(project.name, project.id) for project in projects]}')

    def repo_exist(self, repo_name: str):
        try:
            project_id = self.__project_id(repo_name)
            return True
        except self.RepoNotFoundError:
            return False

    def __user_id(self, username):
        gl = Gitlab(url=self.url, private_token=self.auth_token)
        users = gl.users.list(search=username)

        if len(users) == 1:
            return users[0].id

        for user in users:
            if user.username == username:
                return user.id

        raise self.UserNotFoundError(f'Found {len(users)} projects with name "{username}": {users}')

    def add_collaborator(self, repo_name: str, username: str, permissions='developer'):
        access_level = gitlab.DEVELOPER_ACCESS if permissions == 'developer' else gitlab.REPORTER_ACCESS
        user_id = self.__user_id(username)
        project_id = self.__project_id(project_name=repo_name)

        gl = Gitlab(url=self.url, private_token=self.auth_token)

        project = gl.projects.get(project_id)

        project.members.create({'user_id': user_id, 'access_level': access_level})
        return True

    def delete_collaborator(self, repo_name: str, username: str):
        user_id = self.__user_id(username)
        project_id = self.__project_id(project_name=repo_name)

        gl = Gitlab(url=self.url, private_token=self.auth_token)

        project = gl.projects.get(project_id)
        project.members.delete(user_id)
        return True

    def get_collaborators(self, repo_name):
        gl = Gitlab(url=self.url, private_token=self.auth_token)
        project_id = self.__project_id(project_name=repo_name)
        project = gl.projects.get(project_id)
        users = project.members.list()
        return [user.username for user in users]

    def get_repo_url(self, repo_name: str):
        project_id = self.__project_id(project_name=repo_name)
        gl = Gitlab(url=self.url, private_token=self.auth_token)
        project = gl.projects.get(project_id)
        return project.http_url_to_repo

    def add_tag(self, repo_name: str, commit_sha: str, tag: str, tag_msg: str = None):
        project_id = self.__project_id(project_name=repo_name)
        gl = Gitlab(url=self.url, private_token=self.auth_token)
        project = gl.projects.get(project_id)
        tag = project.tags.create({'tag_name': tag, 'ref': commit_sha, 'message': tag_msg})

    def delete_tag(self, repo_name: str, tag: str):
        project_id = self.__project_id(project_name=repo_name)
        gl = Gitlab(url=self.url, private_token=self.auth_token)
        project = gl.projects.get(project_id)
        try:
            project.tags.delete(tag)
            return True
        except gitlab.exceptions.GitlabDeleteError:
            return False

    def delete_repo(self, repo_name: str):
        gl = Gitlab(url=self.url, private_token=self.auth_token)
        project_id = self.__project_id(project_name=repo_name)
        project = gl.projects.get(project_id)
        n_of_tags = len(project.tags.list())
        project.delete()
        return n_of_tags

    def clone(self, repo_name, repo_dst: Path):
        gl = Gitlab(url=self.url, private_token=self.auth_token)
        gl.auth()
        current_user = gl.user
        username = current_user.username

        https_link = f'https://{username}:{self.auth_token}@' + self.url[8:] + f"/{username}/{repo_name}.git"
        return git.Repo.clone_from(https_link, str(repo_dst))

    def get_commits_list(self, repo_name):
        """
        Gets list of commits, (pairs (commit_msg, commit_sha))
        """
        gl = Gitlab(url=self.url, private_token=self.auth_token)
        project_id = self.__project_id(project_name=repo_name)
        project = gl.projects.get(project_id)
        commits = project.commits.list()
        return [(commit.id, commit.message) for commit in commits]

    def get_tag_msg(self, repo_name, tag=None):
        """
        Gets commit message of commit with tag=[tag] or last commit
        """
        gl = Gitlab(url=self.url, private_token=self.auth_token)
        project_id = self.__project_id(project_name=repo_name)
        project = gl.projects.get(project_id)
        tags = project.tags.list()

        if tag:
            try:
                return [tag_item.message for tag_item in tags if tag_item.name == tag][0]

            except IndexError:
                return None
        return tags[0].message

    def tag_exists(self, repo_name: str, tag_name):
        if not self.repo_exist(repo_name):
            return False

        gl = Gitlab(url=self.url, private_token=self.auth_token)
        project_id = self.__project_id(project_name=repo_name)
        project = gl.projects.get(project_id)
        tags = project.tags.list()

        return any(tag.name == tag_name for tag in tags)


class GithubConnector(Connector):
    def __init__(self, auth_token):
        self.token = auth_token
        try:
            g = Github(self.token)
            user = g.get_user()
            self.username = user.login
        except GithubException:
            raise self.GitAuthenticationError("Could not authenticate to github.com")

    def __str__(self):
        return f"GithubConnector, github.com username: {self.username}, auth_token: {'****' if self.token else None}"

    def init_repo(self, repo_name: str):

        g = Github(self.token)
        user = g.get_user()
        repo = user.create_repo(f'{repo_name}', private=True)
        return repo.full_name

    def __get_repo(self, repo_name: str):
        g = Github(self.token)
        try:
            repo = g.get_repo(f'{self.username}/{repo_name}')
        except GithubException:
            raise self.RepoNotFoundError(f"Repo {repo_name} does not exist!")
        return repo

    def repo_exist(self, repo_name: str):
        try:
            self.__get_repo(repo_name)
        except self.RepoNotFoundError:
            return False
        return True

    def add_collaborator(self, repo_name: str, username: str, permissions='developer'):
        repo = self.__get_repo(repo_name)
        github_permissions = "push" if permissions == 'developer' else "pull"
        repo.add_to_collaborators(collaborator=username, permission=github_permissions)
        return True

    def delete_collaborator(self, repo_name: str, username: str):
        repo = self.__get_repo(repo_name)
        repo.remove_from_collaborators(username)
        return True

    def get_collaborators(self, repo_name):
        repo = self.__get_repo(repo_name)
        return [user.login for user in repo.get_collaborators()]

    def get_repo_url(self, repo_name: str):
        repo = self.__get_repo(repo_name)
        return repo.clone_url

    def add_tag(self, repo_name: str, commit_sha: str, tag: str, tag_msg: str = None):
        repo = self.__get_repo(repo_name)

        repo.create_git_tag_and_release(tag=tag, tag_message=tag_msg, release_name=tag, release_message=tag_msg,
                                        object=commit_sha, type='commit')

    def delete_tag(self, repo_name: str, tag: str):
        repo = self.__get_repo(repo_name)

        release_done, tag_done = False, False

        for release in repo.get_releases():
            if release.tag_name == tag:
                release.delete_release()
                release_done = True
                break

        for ref in repo.get_git_refs():
            if ref.ref == f'refs/tags/{tag}':
                ref.delete()
                tag_done = True
                break

        return release_done and tag_done

    def delete_repo(self, repo_name: str):
        repo = self.__get_repo(repo_name)
        n_of_tags = repo.get_tags().totalCount

        try:
            repo.delete()
        except GithubException:
            raise self.PermissionDenied(f'Authentication token does not have rights to delete repo {repo_name}')
        return n_of_tags

    def clone(self, repo_name, repo_dst: Path):

        https_link = f'https://{self.token}:x-oauth-basic@github.com/{self.username}/{repo_name}'
        return git.Repo.clone_from(https_link, str(repo_dst))

    def get_commits_list(self, repo_name):
        """
        Gets list of commits, (pairs (commit_msg, commit_sha))
        """
        repo = self.__get_repo(repo_name)
        commits = repo.get_commits()
        return [(commit.sha, commit.commit.message) for commit in commits]

    def get_tag_msg(self, repo_name, tag=None):
        """
        Gets tag/release message of release with tag=[tag] or last release
        """
        repo = self.__get_repo(repo_name)
        releases = repo.get_releases()

        if tag:
            try:
                return [release.body for release in releases if release.title == tag][0]

            except IndexError:
                return None
        return releases[0].body

    def tag_exists(self, repo_name: str, tag_name):
        if not self.repo_exist(repo_name):
            return False

        repo = self.__get_repo(repo_name)
        releases = repo.get_releases()

        return any(release.title == tag_name for release in releases)
