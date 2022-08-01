from __future__ import annotations

import contextlib
import logging
import time
from pathlib import Path
from typing import Iterator, List
from urllib.parse import urlparse

import tomli
import tomli_w
from kraken.core import BackgroundTask, Property
from kraken.core.utils import atomic_file_swap, not_none

from kraken.std.cargo.config import CargoRegistry
from kraken.std.git.config import dump_gitconfig, load_gitconfig

logger = logging.getLogger(__name__)


class CargoAuthProxyTask(BackgroundTask):
    """This task starts a local proxy server that injects HTTP basic authentication credentials in HTTP(S) requests
    to a Cargo repository to work around Cargo's current inability to interface with private repositories."""

    #: The Cargo config file to update.
    cargo_config_file: Property[Path] = Property.default(".cargo/config.toml")

    #: A list of the Cargo registries for which to inject credentials for based on matching paths.
    registries: Property[List[CargoRegistry]]

    #: The proxy port.
    proxy_port: Property[int] = Property.default(8899)

    #: The URL of the proxy. This property is only valid and accessible for tasks that immediately directly depend
    #: on this task and will be invalidated at the task teardown.
    proxy_url: Property[str] = Property.output()

    #: The path to the certificate file that needs to be trusted in order to talk to the proxy over HTTPS.
    proxy_cert_file: Property[Path] = Property.output()

    @contextlib.contextmanager
    def _inject_config(self) -> Iterator[None]:
        """Injects the proxy URL and cert file into the Cargo and Git configuration."""

        # TODO (@NiklasRosenstein): Can we get away without temporarily modifying the GLOBAL Git config?

        cargo_config_toml = self.project.directory / self.cargo_config_file.get()
        cargo_config = tomli.loads(cargo_config_toml.read_text()) if cargo_config_toml.is_file() else {}

        git_config_file = Path("~/.gitconfig").expanduser()
        git_config = load_gitconfig(git_config_file) if git_config_file.is_file() else {}

        with contextlib.ExitStack() as exit_stack:
            # Temporarily update the Cargo configuration file to inject the HTTP(S) proxy and CA info.
            cargo_http = cargo_config.setdefault("http", {})
            cargo_http["proxy"] = self.proxy_url.get()
            cargo_http["cainfo"] = str(self.proxy_cert_file.get().absolute())
            logger.info("updating %s", cargo_config_toml)
            fp = exit_stack.enter_context(
                atomic_file_swap(cargo_config_toml, "w", always_revert=True, create_dirs=True)
            )
            fp.write(tomli_w.dumps(cargo_config))
            fp.close()

            # Temporarily update the Git configuration file to inject the HTTP(S) proxy and CA info.
            git_http = git_config.setdefault("http", {})
            git_http["proxy"] = self.proxy_url.get()
            git_http["sslCAInfo"] = str(self.proxy_cert_file.get().absolute())
            logger.info("updating %s", git_config_file)
            fp = exit_stack.enter_context(atomic_file_swap(git_config_file, "w", always_revert=True, create_dirs=True))
            fp.write(dump_gitconfig(git_config))
            fp.close()

            yield

    # Task

    def start_background_task(self, exit_stack: contextlib.ExitStack) -> None:
        from ..mitm import mitm_auth_proxy

        auth: dict[str, tuple[str, str]] = {}
        for registry in self.registries.get():
            if not registry.read_credentials:
                continue
            host = not_none(urlparse(registry.index).hostname)
            auth[host] = registry.read_credentials

        proxy_url, cert_file = exit_stack.enter_context(mitm_auth_proxy(auth=auth, port=self.proxy_port.get()))
        self.proxy_url.set(proxy_url)
        exit_stack.callback(lambda: self.proxy_url.clear())
        self.proxy_cert_file.set(cert_file)
        exit_stack.callback(lambda: self.proxy_cert_file.clear())
        time.sleep(1)  # Give the proxy some time to start up.

        exit_stack.enter_context(self._inject_config())
