""" Implements Slap as a Python build system for kraken-std. """

from __future__ import annotations

import logging
import os
import subprocess as sp
import tempfile
from pathlib import Path

from kraken.core.utils import NotSet

from . import ManagedEnvironment, PythonBuildSystem

logger = logging.getLogger(__name__)


class SlapPythonBuildSystem(PythonBuildSystem):
    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory

    def supports_managed_environments(self) -> bool:
        return True

    def get_managed_environment(self) -> ManagedEnvironment:
        return SlapManagedEnvironment(self.project_directory)

    def build(self, output_directory: Path, as_version: str | None = None) -> list[Path]:
        if as_version is not None:
            # TODO (@NiklasRosenstein): We should find a way to revert the changes to the worktree
            #       that this command does.
            command = ["slap", "release", as_version]
            logger.info("%s", command)
            sp.check_call(command, cwd=self.project_directory)

        with tempfile.TemporaryDirectory() as tempdir:
            command = ["slap", "publish", "--dry", "-b", tempdir]
            sp.check_call(command, cwd=self.project_directory)
            src_files = list(Path(tempdir).iterdir())
            dst_files = [output_directory / path.name for path in src_files]
            for src, dst in zip(src_files, dst_files):
                src.rename(dst)
        return dst_files


class SlapManagedEnvironment(ManagedEnvironment):
    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory
        self._env_path: Path | None | NotSet = NotSet.Value

    def exists(self) -> bool:
        try:
            self.get_path()
            return True
        except RuntimeError:
            return False

    def get_path(self) -> Path:
        if self._env_path is NotSet.Value:
            # Slap assumes the currently active environment, so do we.
            path = os.getenv("VIRTUAL_ENV")
            if path is not None:
                return Path(path)
            command = ["slap", "venv", "-p"]
            try:
                self._env_path = Path(
                    sp.check_output(command, cwd=self.project_directory, stderr=sp.DEVNULL).decode().strip()
                )
            except sp.CalledProcessError as exc:
                if exc.returncode != 1:
                    raise
                self._env_path = None
        if self._env_path is None:
            raise RuntimeError("managed environment does not exist")
        return self._env_path

    def install(self) -> None:
        # Ensure that an environment exists.
        command = ["slap", "venv", "-ac"]
        logger.info("%s", command)
        sp.check_call(command, cwd=self.project_directory)

        # Install into the environment.
        command = ["slap", "install", "--link"]
        logger.info("%s", command)
        sp.check_call(command, cwd=self.project_directory)
