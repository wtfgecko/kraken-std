from __future__ import annotations

import abc
import logging
import os
import subprocess as sp
from pathlib import Path
from typing import MutableMapping

from kraken.core.task import TaskResult

logger = logging.getLogger(__name__)


class EnvironmentHandler(abc.ABC):
    """Interface for dealing with a Python virtual environment."""

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory
        self._environment_dir: Path | None = None

    @abc.abstractmethod
    def discover_environment(cls) -> Path | None:
        """Discover the Python environment in use for the given project directory."""
        raise NotImplementedError

    def activate(self, environ: MutableMapping[str, str]) -> None:
        """Activate the environment by updating environment variables in *environ*."""

        if self._environment_dir is None:
            self._environment_dir = self.discover_environment()
            if not self._environment_dir:
                logger.warning(
                    "Unable to detect environment for project directory (%s) [%s]",
                    self.project_directory,
                    type(self).__name__,
                )
                return

        logger.info("Activating Poetry environment (%s)", self._environment_dir)
        bin_dir = self._environment_dir / ("Scripts" if os.name == "nt" else "bin")
        environ["VIRTUAL_ENV"] = str(self._environment_dir)
        environ["PATH"] = os.pathsep.join([str(bin_dir), environ["PATH"]])

    @abc.abstractmethod
    def install(self) -> TaskResult:
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def detect(cls, project_directory: Path) -> EnvironmentHandler | None:
        raise NotImplementedError


class SlapEnvironmentHandler(EnvironmentHandler):
    """This handler should be used if you use the Slap CLI for your Python project."""

    def discover_environment(self) -> Path | None:
        path = os.getenv("VIRTUAL_ENV")
        if path is not None:
            return Path(path)
        command = ["slap", "venv", "-p"]
        try:
            return Path(sp.check_output(command, cwd=self.project_directory, stderr=sp.DEVNULL).decode().strip())
        except sp.CalledProcessError as exc:
            if exc.returncode == 1:
                return None
            raise

    def install(self) -> TaskResult:
        # Ensure that an environment exists.
        command = ["slap", "venv", "-ac"]
        logger.info("%s", command)
        result = TaskResult.from_exit_code(sp.call(command, cwd=self.project_directory))
        if result == TaskResult.FAILED:
            return result

        # Install into the environment.
        command = ["slap", "install", "--link"]
        logger.info("%s", command)
        return TaskResult.from_exit_code(sp.call(command, cwd=self.project_directory))

    @classmethod
    def detect(cls, project_directory: Path) -> EnvironmentHandler | None:
        pyproject_toml = project_directory / "pyproject.toml"
        if pyproject_toml.is_file() and "[tool.slap]" in pyproject_toml.read_text():
            return SlapEnvironmentHandler(project_directory)
        return None


class PoetryEnvironmentHandler(EnvironmentHandler):
    """This handler activates the current Poetry environment, if available."""

    def discover_environment(self) -> Path | None:
        command = ["poetry", "env", "info", "-p"]
        try:
            return Path(sp.check_output(command, cwd=self.project_directory).decode().strip())
        except sp.CalledProcessError as exc:
            if exc.returncode == 1:
                return None
            raise

    def install(self) -> TaskResult:
        command = ["poetry", "install"]
        logger.info("%s", command)
        return TaskResult.from_exit_code(sp.call(command, cwd=self.project_directory))

    @classmethod
    def detect(cls, project_directory: Path) -> EnvironmentHandler | None:
        pyproject_toml = project_directory / "pyproject.toml"
        if pyproject_toml.is_file() and "poetry-core" in pyproject_toml.read_text():
            return PoetryEnvironmentHandler(project_directory)
        return None


# NOTE (@NiklasRosenstein): The order here determines the order in which the detection is run in python_settings().
ENVIRONMENT_HANDLERS: dict[str, type[EnvironmentHandler]] = {
    "slap": SlapEnvironmentHandler,
    "poetry": PoetryEnvironmentHandler,
}
