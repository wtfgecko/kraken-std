from __future__ import annotations

import contextlib
import logging
import subprocess as sp
from typing import Iterator

import pytest
from kraken.core.utils import flatten

logger = logging.getLogger(__name__)


class DockerServiceManager:
    """Helper for integration tests to start Docker services."""

    def __init__(self, exit_stack: contextlib.ExitStack) -> None:
        self._exit_stack = exit_stack

    def _stop_container(self, container_id: str) -> None:
        sp.call(["docker", "stop", container_id])

    def run(
        self,
        image: str,
        args: list[str] | None = None,
        detach: bool = False,
        ports: list[str] | None = None,
        volumes: list[str] | None = None,
        platform: str | None = None,
        env: dict[str, str] | None = None,
        entrypoint: str | None = None,
        capture_output: bool = False,
    ) -> bytes | None:
        command = ["docker", "run", "--rm"]
        if detach:
            command += ["-d"]
        if entrypoint:
            command += ["--entrypoint", entrypoint]
        command += flatten(["-p", p] for p in ports or [])
        command += flatten(["-v", v] for v in volumes or [])
        command += flatten(["--env", f"{k}={v}"] for k, v in (env or {}).items())
        if platform:
            command += ["--platform", platform]
        command += [image]
        command += args or []
        if detach:
            container_id = sp.check_output(command).decode().strip()
            logger.info('started detached container with id "%s" from command %s', container_id, command)
            self._exit_stack.callback(self._stop_container, container_id)
            logs_proc = sp.Popen(["docker", "logs", "-f", container_id])

            def _stop_logs_proc() -> None:
                logs_proc.terminate()
                logs_proc.wait()

            self._exit_stack.callback(_stop_logs_proc)
        elif capture_output:
            return sp.check_output(command)
        else:
            sp.check_call(command)

        return None


@pytest.fixture
def docker_service_manager() -> Iterator[DockerServiceManager]:
    with contextlib.ExitStack() as stack:
        yield DockerServiceManager(stack)
