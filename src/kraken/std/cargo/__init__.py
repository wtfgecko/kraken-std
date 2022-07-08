from __future__ import annotations

import contextlib
import dataclasses
import logging
import os
import subprocess as sp
from pathlib import Path
from typing import Iterator

import tomli
import tomli_w
from kraken.core.project import Project
from kraken.core.property import Property
from kraken.core.task import Task, TaskResult, task_factory
from kraken.core.utils import atomic_file_swap

logger = logging.getLogger(__name__)
CARGO_CONFIG_TOML = Path(".cargo/config.toml")


@dataclasses.dataclass
class CargoProjectSettings:
    """Settings for Cargo tasks in a project."""

    #: A dictionary that maps host names to (username, password) tuples.
    auth: dict[str, tuple[str, str]] = dataclasses.field(default_factory=dict)

    def add_auth(self, host: str, username: str, password: str) -> CargoProjectSettings:
        self.auth[host] = (username, password)
        return self


def cargo_settings(project: Project | None = None) -> CargoProjectSettings:
    """Creates or gets the cargo project settings for the current project or the given one."""

    if project is None:
        from kraken.api import project as _project

        project = _project

    settings = project.find_metadata(CargoProjectSettings)
    if settings is None:
        settings = CargoProjectSettings()
        project.metadata.append(settings)

    return settings


class CargoBuildTask(Task):
    """This task runs `cargo build` using the specified parameters. It will respect the authentication
    credentials configured in :attr:`CargoProjectSettings.auth`."""

    args: Property[list[str]]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.args.set([])

    @contextlib.contextmanager
    def _update_cargo_config(self, proxy: str, cainfo: str, file: Path) -> Iterator[None]:
        """Temporarily updates the Cargo configuration."""

        if file.is_file():
            config = tomli.loads(file.read_text())
        else:
            config = {}

        http = config.setdefault("http", {})
        http["proxy"] = proxy
        http["cainfo"] = cainfo

        logger.info("injecting proxy/cainfo config into %s", file)

        with atomic_file_swap(file, "w", always_revert=True) as fp:
            fp.write(tomli_w.dumps(config))
            fp.close()
            yield

    def _execute(self, exit_stack: contextlib.ExitStack) -> TaskResult:
        settings = cargo_settings(self.project)
        env = os.environ.copy()

        # Until github.com/rust-lang/cargo#10592 is working and merged, we need to inject the credentials using a
        # man-in-the-middle proxy server.
        if settings.auth:
            from kraken.std.cargo.mitm import mitm_auth_proxy

            proxy_url, cert_file = exit_stack.enter_context(
                mitm_auth_proxy(
                    settings.auth,
                    self.project.context.build_directory / "cargo_mitm_root_ca",
                )
            )

            exit_stack.enter_context(
                self._update_cargo_config(
                    proxy_url,
                    str(cert_file.absolute()),
                    file=self.project.directory / CARGO_CONFIG_TOML,
                )
            )

            # Make sure the proxy server has some time to start up.
            import time

            time.sleep(1)

            env["http_proxy"] = proxy_url
            env["https_proxy"] = proxy_url
            env["GIT_SSL_NO_VERIFY"] = "1"

        command = ["cargo", "build"] + self.args.get()

        logger.info("running cargo build command: %s", command)
        result = sp.call(command, env=env)
        return TaskResult.SUCCEEDED if result == 0 else TaskResult.FAILED

    def execute(self) -> TaskResult:
        with contextlib.ExitStack() as exit_stack:
            return self._execute(exit_stack)
        assert False


cargo_build = task_factory(CargoBuildTask, capture=False)
