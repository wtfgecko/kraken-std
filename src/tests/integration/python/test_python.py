import logging
import os
import shutil
import subprocess as sp
import sys
import tempfile
import unittest.mock
from pathlib import Path
from typing import Iterator

import pytest
from kraken.core import Context
from kraken.core.utils import not_none

from tests.utils.docker import DockerServiceManager

logger = logging.getLogger(__name__)
PYPISERVER_PORT = 23213
USER_NAME = "integration-test-user"
USER_PASS = "password-for-integration-test"


@pytest.fixture
def tempdir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as tempdir:
        yield Path(tempdir)


@pytest.fixture
def pypiserver(docker_service_manager: DockerServiceManager, tempdir: Path) -> str:

    # Create a htpasswd file for the registry.
    logger.info("Generating htpasswd for Pypiserver")
    htpasswd_content = not_none(
        docker_service_manager.run(
            "httpd:2",
            entrypoint="htpasswd",
            args=["-Bbn", USER_NAME, USER_PASS],
            capture_output=True,
        )
    )
    htpasswd = tempdir / "htpasswd"
    htpasswd.write_bytes(htpasswd_content)

    index_url = f"http://localhost:{PYPISERVER_PORT}/simple"
    docker_service_manager.run(
        "pypiserver/pypiserver:latest",
        ["--passwords", "/.htpasswd", "-a", "update"],
        ports=[f"{PYPISERVER_PORT}:8080"],
        volumes=[f"{htpasswd.absolute()}:/.htpasswd"],
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
    consumer_dir = project_dir + "-consumer"

    # Copy the projects to the temporary directory.
    shutil.copytree(Path(__file__).parent / "data" / project_dir, tempdir / project_dir)
    shutil.copytree(Path(__file__).parent / "data" / consumer_dir, tempdir / consumer_dir)

    # TODO (@NiklasRosenstein): Make sure Poetry installs the environment locally so it gets cleaned up
    #       with the temporary directory.

    logger.info("Loading and executing Kraken project (%s)", tempdir / project_dir)
    os.environ["LOCAL_PACKAGE_INDEX"] = pypiserver
    os.environ["LOCAL_USER"] = USER_NAME
    os.environ["LOCAL_PASSWORD"] = USER_PASS
    kraken_ctx.load_project(directory=tempdir / project_dir)
    kraken_ctx.execute([":lint", ":publish"])

    # Try to run the "consumer" project.
    logger.info("Loading and executing Kraken project (%s)", tempdir / consumer_dir)
    Context.__init__(kraken_ctx, kraken_ctx.build_directory)
    kraken_ctx.load_project(directory=tempdir / consumer_dir)
    kraken_ctx.execute([":pythonInstall"])
    # TODO (@NiklasRosenstein): Test importing the consumer project.
