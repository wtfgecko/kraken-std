from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, List

from kraken.core import Project, Property, TaskResult

from .base_task import EnvironmentAwareDispatchTask


class IsortTask(EnvironmentAwareDispatchTask):
    check_only: Property[bool] = Property.config(default=False)
    config_file: Property[Path]
    additional_files: Property[List[Path]] = Property.config(default_factory=list)

    def get_execute_command(self) -> list[str] | TaskResult:
        command = ["isort", "src/"] + self.settings.get_tests_directory_as_args()
        command += [str(p) for p in self.additional_files.get()]
        if self.check_only.get():
            command += ["--check-only"]
        if self.config_file.is_filled():
            command += ["--settings-file", str(self.config_file.get())]
        return command


@dataclasses.dataclass
class IsortTasks:
    check: IsortTask
    format: IsortTask


def isort(project: Project | None = None, **kwargs: Any) -> IsortTasks:
    # TODO (@NiklasRosenstein): We may need to ensure an order to isort and block somehow, sometimes they yield
    #       slightly different results based on the order they run.
    project = project or Project.current()
    check_task = project.do("isortCheck", IsortTask, group="lint", **kwargs, check_only=True)
    format_task = project.do("isortFormat", IsortTask, group="fmt", default=False, **kwargs)
    return IsortTasks(check_task, format_task)
