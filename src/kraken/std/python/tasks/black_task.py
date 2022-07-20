from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, List, Union

from kraken.core import Project, Property, TaskResult

from .base_task import EnvironmentAwareDispatchTask


class BlackTask(EnvironmentAwareDispatchTask):
    """A task to run the `black` formatter to either check for necessary changes or apply changes."""

    check_only: Property[bool] = Property.config(default=False)
    config_file: Property[Path]
    source_directories: Property[List[Union[str, Path]]] = Property.config(default_factory=lambda: ["src"])
    additional_args: Property[List[str]] = Property.config(default_factory=list)
    additional_files: Property[List[Path]] = Property.config(default_factory=list)

    def get_execute_command(self) -> list[str] | TaskResult:
        command = ["black"] + list(map(str, self.source_directories.get()))
        command += self.settings.get_tests_directory_as_args()
        command += [str(p) for p in self.additional_files.get()]
        if self.check_only.get():
            command += ["--check"]
        if self.config_file.is_filled():
            command += ["--config", str(self.config_file.get())]
        command += self.additional_args.get()
        return command


@dataclasses.dataclass
class BlackTasks:
    check: BlackTask
    format: BlackTask


def black(project: Project | None = None, **kwargs: Any) -> BlackTasks:
    """Creates two black tasks, one to check and another to format. The check task will be grouped under `"lint"`
    whereas the format task will be grouped under `"fmt"`."""

    project = project or Project.current()
    check_task = project.do("blackCheck", BlackTask, group="lint", **kwargs, check_only=True)
    format_task = project.do("blackFormat", BlackTask, group="fmt", default=False, **kwargs)
    return BlackTasks(check_task, format_task)
