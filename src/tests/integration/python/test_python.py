import logging
import os
import shutil
import subprocess as sp
import sys
import tempfile
import unittest.mock
from pathlib import Path

import pytest
from kraken.core import Context

from tests.utils.docker import DockerServiceManager

logger = logging.getLogger(__name__)
PYPISERVER_PORT = 23213


@pytest.fixture
def tempdir() -> Path:
    with tempfile.TemporaryDirectory() as tempdir:
        return Path(tempdir)


@pytest.fixture
def pypiserver(docker_service_manager: DockerServiceManager) -> str:
    index_url = f"http://localhost:{PYPISERVER_PORT}/simple"
    docker_service_manager.run(
        "pypiserver/pypiserver:latest",
        ["-P", ".", "-a", "."],
        ports=[f"{PYPISERVER_PORT}:8080"],
        detach=True,
        probe=("GET", index_url),
    )
    logger.info("Started local Pypiserver at %s", index_url)
    return index_url


@pytest.mark.parametrize("project_dir", ["poetry-project", "slap-project"])
@unittest.mock.patch.dict(os.environ, {})
def test__python_project_install_lint_and_publish(
    project_dir: str,
    kraken_ctx: Context,
    tempdir: Path,
    pypiserver: str,
) -> None:
    # Copy the project to the temporary directory.
    shutil.copytree(Path(__file__).parent / "data" / project_dir, tempdir / project_dir)

    # TODO (@NiklasRosenstein): Make sure Poetry installs the environment locally so it gets cleaned up
    #       with the temporary directory.

    logger.info("Loading and executing Kraken project (%s)", tempdir / project_dir)
    os.environ["LOCAL_PACKAGE_INDEX"] = pypiserver
    kraken_ctx.load_project(directory=tempdir / project_dir)
    kraken_ctx.execute([":lint", ":publish"])

    # Make sure we can install the package with Pip now. (Package name is the same as the project dir)
    venv_dir = tempdir / "venv"
    logger.info("Creating virtual environment (%s)", venv_dir)
    command = [sys.executable, "-m", "venv", str(venv_dir)]
    sp.check_call(command)
    logger.info("Installing package %r from local Pypiserver into virtual environment", project_dir)
    # TODO (@NiklasRosenstein): Different path on Windows
    command = [str(venv_dir / "bin" / "pip"), "install", "--index-url", pypiserver, project_dir]
    sp.check_call(command)
