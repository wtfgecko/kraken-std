from __future__ import annotations

import logging
from typing import Union, cast

from kraken.core import Project, Task, TaskResult

from kraken.std.python.environments import EnvironmentHandler

from .settings import python_settings

logger = logging.getLogger(__name__)


class InstallTask(Task):
    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.settings = python_settings(project)

    def is_up_to_date(self) -> bool:
        if self.settings.environment_handler and not self.settings.environment_handler.discover_environment():
            return False
        return True

    def execute(self) -> TaskResult:
        assert self.settings.environment_handler is not None
        return self.settings.environment_handler.install()


def install(project: Project | None = None, environment_handler: str | EnvironmentHandler | None = None) -> InstallTask:
    """Returns the install task for the project."""

    project = project or Project.current()
    name = "pythonInstall"
    task = cast(Union[InstallTask, None], project.tasks().get(name))
    if task is None:
        task = project.do(name, InstallTask, default=False)
    if environment_handler is not None:
        python_settings(project, environment_handler=environment_handler)
    return task
