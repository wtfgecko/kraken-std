from __future__ import annotations

import abc
import dataclasses
import logging
import os
import subprocess as sp
from pathlib import Path
from typing import Iterable

from kraken.core import Project, Task, TaskRelationship, TaskResult

from .environments import ENVIRONMENT_HANDLERS, EnvironmentHandler

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class PythonSettings:
    """Project-global settings for Python tasks."""

    project: Project
    environment_handler: EnvironmentHandler | None = None
    source_directory: Path = Path("src")
    tests_directory: Path | None = None

    def get_tests_directory(self) -> Path | None:
        """Returns :attr:`tests_directory` if it is set. If not, it will look for the following directories and
        return the first that exists: `test/`, `tests/`, `src/test/`, `src/tests/`. The determined path will be
        relative to the project directory."""

        if self.tests_directory:
            return self.tests_directory
        for test_dir in map(Path, ["test", "tests", "src/test", "src/tests"]):
            if (self.project.directory / test_dir).is_dir():
                return test_dir
        return None

    def get_tests_directory_as_args(self) -> list[str]:
        """Returns a list with a single item that is the test directory, or an empty list. This is convenient
        when constructing command-line arguments where you want to pass the test directory if it exists."""

        test_dir = self.get_tests_directory()
        return [] if test_dir is None else [str(test_dir)]


def python_settings(
    project: Project | None = None,
    environment_handler: str | EnvironmentHandler | None = None,
    source_directory: str | Path | None = None,
    tests_directory: str | Path | None = None,
) -> PythonSettings:
    """Read the Python settings for the given or current project and optionally update attributes.

    :param project: The project to get the settings for. If not specified, the current project will be used.
    :environment_handler: If specified, set the :attr:`PythonSettings.environment_handler`. If a string is specified,
        the following values are currently supported: `"poetry"`.
    :param source_directory: The source directory. Defaults to `"src"`.
    :param tests_directory: The tests directory. Automatically determined if left empty.
    """

    project = project or Project.current()
    settings = project.find_metadata(PythonSettings)
    if settings is None:
        settings = PythonSettings(project)
        project.metadata.append(settings)

    if environment_handler is None and settings.environment_handler is None:
        # Autodetect the environment handler.
        for handler_name, handler in ENVIRONMENT_HANDLERS.items():
            environment_handler = handler.detect(project.directory)
            if environment_handler is not None:
                logger.info("Detected environment handler for %s = %r", project, handler_name)
                break

    if environment_handler is not None:
        if isinstance(environment_handler, str):
            environment_handler = ENVIRONMENT_HANDLERS[environment_handler](project.directory)
        assert isinstance(environment_handler, EnvironmentHandler), repr(environment_handler)
        if settings.environment_handler:
            logger.warning(
                "overwriting existing PythonSettings.environment_handler=%r with %r",
                settings.environment_handler,
                environment_handler,
            )
        settings.environment_handler = environment_handler

    if source_directory is not None:
        settings.source_directory = Path(source_directory)

    if tests_directory is not None:
        settings.tests_directory = Path(tests_directory)

    return settings


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

    def execute(self) -> TaskResult:
        settings = python_settings(self.project)
        command = self.get_execute_command()
        if isinstance(command, TaskResult):
            return command
        env = os.environ.copy()
        if settings.environment_handler:
            settings.environment_handler.activate(env)
        logger.info("%s", command)
        result = sp.call(command, cwd=self.project.directory, env=env)
        return self.handle_exit_code(result)
