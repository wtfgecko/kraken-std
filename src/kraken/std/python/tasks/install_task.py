from __future__ import annotations

import logging
from typing import Optional, Union, cast

from kraken.core import Project, Property, Supplier, Task, TaskResult

from ..buildsystem import PythonBuildSystem
from ..settings import python_settings

logger = logging.getLogger(__name__)


class InstallTask(Task):
    build_system: Property[Optional[PythonBuildSystem]]

    def is_skippable(self) -> bool:
        build_system = self.build_system.get()
        if build_system:
            return not build_system.supports_managed_environments()
        return True

    def is_up_to_date(self) -> bool:
        build_system = self.build_system.get()
        if build_system:
            managed_environment = build_system.get_managed_environment()
            return managed_environment.exists()
        return True

    def execute(self) -> TaskResult:
        build_system = self.build_system.get()
        if not build_system:
            logger.error("no build system configured")
            return TaskResult.FAILED
        managed_environment = build_system.get_managed_environment()
        managed_environment.install()
        return TaskResult.SUCCEEDED


def install(project: Project | None = None) -> InstallTask:
    """Get or create the `pythonInstall` task for the given project.

    The install task relies on the build system configured in the Python project settings."""

    name = "pythonInstall"

    project = project or Project.current()
    task = cast(Union[InstallTask, None], project.tasks().get(name))
    if task is None:
        task = project.do(name, InstallTask, default=False)
        task.build_system.set(Supplier.of_callable(lambda: python_settings(project).build_system))

    return task
