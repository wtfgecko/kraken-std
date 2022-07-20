from __future__ import annotations

from pathlib import Path
from typing import Any, List

from kraken.core import Project, Property, TaskResult

from .base_task import EnvironmentAwareDispatchTask


class Flake8Task(EnvironmentAwareDispatchTask):
    config_file: Property[Path]
    additional_args: Property[List[str]] = Property.config(default_factory=list)

    def get_execute_command(self) -> list[str] | TaskResult:
        command = ["flake8", "src/"] + self.settings.get_tests_directory_as_args()
        if self.config_file.is_filled():
            command += ["--config", str(self.config_file.get())]
        command += self.additional_args.get()
        return command


def flake8(project: Project | None = None, **kwargs: Any) -> Flake8Task:
    project = project or Project.current()
    return project.do("flake8", Flake8Task, group="lint", **kwargs)
