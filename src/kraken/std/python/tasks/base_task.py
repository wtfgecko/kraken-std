from __future__ import annotations

import abc
import logging
import os
import subprocess as sp
from typing import Iterable, MutableMapping

from kraken.core import Project, Task, TaskRelationship, TaskResult

from kraken.std.python.buildsystem import ManagedEnvironment

from ..settings import python_settings

logger = logging.getLogger(__name__)


class EnvironmentAwareDispatchTask(Task):
    """Base class for tasks that run a subcommand. The command ensures that the command is aware of the
    environment configured in the project settings."""

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.settings = python_settings(project)

    def get_relationships(self) -> Iterable[TaskRelationship]:
        # If a pythonInstall task exists, we may need it.
        install_task = self.project.tasks().get("pythonInstall")
        if install_task:
            yield TaskRelationship(install_task, True, False)
        yield from super().get_relationships()

    @abc.abstractmethod
    def get_execute_command(self) -> list[str] | TaskResult:
        pass

    def handle_exit_code(self, code: int) -> TaskResult:
        return TaskResult.from_exit_code(code)

    def activate_managed_environment(self, pyenv: ManagedEnvironment, envvar: MutableMapping[str, str]) -> None:
        if not pyenv.exists():
            logger.warning("Managed environment (%s) does not exist", pyenv)
            return

        env_path = pyenv.get_path()
        logger.info("Activating managed environment (%s)", env_path)
        bin_dir = env_path / ("Scripts" if os.name == "nt" else "bin")
        envvar["VIRTUAL_ENV"] = str(env_path)
        envvar["PATH"] = os.pathsep.join([str(bin_dir), envvar["PATH"]])

    def execute(self) -> TaskResult:
        command = self.get_execute_command()
        if isinstance(command, TaskResult):
            return command
        env = os.environ.copy()
        if self.settings.build_system and self.settings.build_system.supports_managed_environments():
            self.activate_managed_environment(self.settings.build_system.get_managed_environment(), env)
        logger.info("%s", command)
        result = sp.call(command, cwd=self.project.directory, env=env)
        return self.handle_exit_code(result)
