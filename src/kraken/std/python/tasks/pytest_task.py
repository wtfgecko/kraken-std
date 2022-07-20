from __future__ import annotations

from pathlib import Path
from typing import Any, List

from kraken.core import Project, Property, TaskResult
from kraken.core.utils import flatten

from .base_task import EnvironmentAwareDispatchTask

# TODO (@NiklasRosenstein): Pytest coverage support


class PytestTask(EnvironmentAwareDispatchTask):
    tests_dir: Property[Path]
    ignore_dirs: Property[List[Path]] = Property.config(default_factory=list)
    allow_no_tests: Property[bool] = Property.config(default=False)

    def is_skippable(self) -> bool:
        return self.allow_no_tests.get() and self.tests_dir.is_empty() and not self.settings.get_tests_directory()

    def get_execute_command(self) -> list[str] | TaskResult:
        tests_dir = self.tests_dir.get_or(None)
        tests_dir = tests_dir or self.settings.get_tests_directory()
        if not tests_dir:
            print("error: no test directory configured and none could be detected")
            return TaskResult.FAILED
        command = ["pytest", "-vv", str(self.project.directory / tests_dir)]
        command += flatten(["--ignore", str(self.project.directory / path)] for path in self.ignore_dirs.get())
        return command

    def handle_exit_code(self, code: int) -> TaskResult:
        if code == 5 and self.allow_no_tests.get():
            # Pytest returns exit code 5 if no tests were run.
            return TaskResult.SUCCEEDED
        return TaskResult.from_exit_code(code)


def pytest(*, name: str = "pytest", project: Project | None = None, **kwargs: Any) -> PytestTask:
    project = project or Project.current()
    return project.do(name, PytestTask, group="test", **kwargs)
