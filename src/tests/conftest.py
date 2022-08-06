import contextlib
import tempfile
from pathlib import Path
from typing import Iterator

import pytest

from tests.utils.docker import DockerServiceManager


@pytest.fixture
def docker_service_manager() -> Iterator[DockerServiceManager]:
    with contextlib.ExitStack() as stack:
        yield DockerServiceManager(stack)


@pytest.fixture
def tempdir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as tempdir:
        yield Path(tempdir)
