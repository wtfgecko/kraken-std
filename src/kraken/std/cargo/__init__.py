""" Provides tasks for Rust projects that build using Cargo. """

from __future__ import annotations

import base64
import contextlib
import dataclasses
import enum
import io
import logging
import re
import subprocess as sp
import time
import urllib.parse
from pathlib import Path
from typing import Iterator, List

import tomli
import tomli_w
from kraken.core import Project, Property, Task, TaskResult
from kraken.core.utils import atomic_file_swap, not_none

logger = logging.getLogger(__name__)
CARGO_CONFIG_TOML = Path(".cargo/config.toml")


@dataclasses.dataclass
class PublishTokenType(enum.Enum):
    """Desribes what kind of publish token the registry expects."""

    #: Prefix the password or api_key with `"Bearer "`. Example: Artifactory
    BEARER_TOKEN = enum.auto()

    #: Just take the password or api_key as the publish token as-is. Example: Cloudsmith
    API_KEY = enum.auto()


@dataclasses.dataclass
class Registry:
    """Represents a Cargo registrory."""

    #: Registry name.
    name: str

    #: The index URL.
    index_url: str

    #: The publish token. This may be a templated string that, if applicable, will be constructed from the
    #: :attr:`CargoProjectSettings.auth` credentials if a matching host was found according to *index_url*.
    #: The available variables are `${PASSWORD}` and `${BASIC}`.
    #: Artifactory will expected a `Bearer ${PASSWORD}` while Cloudsmith expects just `${PASSWORD}` (and
    #: `PASSWORD` should be the Cloudsmith API Key).
    publish_token: str

    def __post_init__(self) -> None:
        # Validate the registry name.
        assert re.match(r"^[a-zA-Z0-9_\-]+$", self.name), f"invalid registry name: {self.name!r}"

    def get_publish_token(self, auth: dict[str, tuple[str, str]]) -> str:
        """Replaces variables in the :attr:`publish_token` if necessary and returns it."""

        if not ("${PASSWORD}" in self.publish_token or "${BASIC}" in self.publish_token):
            return self.publish_token

        hostname = not_none(not_none(urllib.parse.urlparse(self.index_url)).hostname)
        if hostname not in auth:
            raise ValueError(
                f"host {hostname!r} has no auth configured in Kraken project settings "
                f"(required for registry {self.name!r})"
            )

        curr_auth = auth[hostname]
        password = curr_auth[1]
        basic = base64.b64encode(f"{curr_auth[0]}:{curr_auth[1]}".encode()).decode("ascii")
        return self.publish_token.replace("${PASSWORD}", password).replace("${BASIC}", basic)


@dataclasses.dataclass
class CargoProjectSettings:
    """Settings for Cargo tasks in a project."""

    #: A dictionary that maps host names to (username, password) tuples.
    auth: dict[str, tuple[str, str]] = dataclasses.field(default_factory=dict)

    #: A dictionary that maps registry index URLs.
    registries: dict[str, Registry] = dataclasses.field(default_factory=dict)

    def add_auth(self, host: str, username: str, password: str) -> CargoProjectSettings:
        self.auth[host] = (username, password)
        return self

    def add_registry(
        self, registry_name: str, index_url: str, publish_token: str = "${PASSWORD}"
    ) -> CargoProjectSettings:
        self.registries[registry_name] = Registry(registry_name, index_url, publish_token)
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


def _load_gitconfig(file: Path) -> dict[str, dict[str, str]]:
    import configparser

    parser = configparser.RawConfigParser()
    parser.read(file)
    result = dict(parser._sections)  # type: ignore[attr-defined]
    for k in result:
        result[k] = dict(parser._defaults, **result[k])  # type: ignore[attr-defined]
        result[k].pop("__name__", None)
    return result


def _dump_gitconfig(data: dict[str, dict[str, str]]) -> str:
    import configparser

    parser = configparser.RawConfigParser()
    for section, values in data.items():
        parser.add_section(section)
        for key, value in values.items():
            parser.set(section, key, value)
    fp = io.StringIO()
    parser.write(fp)
    return fp.getvalue()


@contextlib.contextmanager
def _cargo_inject_settings(project_dir: Path, certs_dir: Path, settings: CargoProjectSettings) -> Iterator[None]:
    """This context manager injects the HTTP basic authentication headers using an MITM proxy and informs Cargo
    and Git of the HTTP(s) proxy and the self-signed certificates.

    Args:
        project_dir: The directory that contains the Cargo project.
        settings: The project settings that contain the credentials.
    """

    if not settings.auth:
        return

    from kraken.std.cargo.mitm import mitm_auth_proxy

    cargo_config_toml = project_dir / ".cargo" / "config.toml"
    cargo_config = tomli.loads(cargo_config_toml.read_text()) if cargo_config_toml.is_file() else {}

    git_config_file = Path("~/.gitconfig").expanduser()
    git_config = _load_gitconfig(git_config_file) if git_config_file.is_file() else {}

    with contextlib.ExitStack() as exit_stack:

        # Start an HTTP(S) proxy that we can direct Cargo and Git to. We need to give the proxy a little
        # time to come up.
        proxy_url, cert_file = exit_stack.enter_context(mitm_auth_proxy(settings.auth, certs_dir))
        time.sleep(0.5)

        # Temporarily update the Cargo configuration file to inject the HTTP(S) proxy and CA info.
        cargo_registries = cargo_config.setdefault("registries", {})
        for registry in settings.registries.values():
            cargo_registries[registry.name] = {"index": registry.index_url}
        cargo_http = cargo_config.setdefault("http", {})
        cargo_http["proxy"] = proxy_url
        cargo_http["cainfo"] = str(cert_file.absolute())
        logger.info("updating %s", cargo_config_toml)
        fp = exit_stack.enter_context(atomic_file_swap(cargo_config_toml, "w", always_revert=True, create_dirs=True))
        fp.write(tomli_w.dumps(cargo_config))
        fp.close()

        # Temporarily update the Git configuration file to inject the HTTP(S) proxy and CA info.
        git_http = git_config.setdefault("http", {})
        git_http["proxy"] = proxy_url
        git_http["sslCAInfo"] = str(cert_file.absolute())
        logger.info("updating %s", git_config_file)
        fp = exit_stack.enter_context(atomic_file_swap(git_config_file, "w", always_revert=True, create_dirs=True))
        fp.write(_dump_gitconfig(git_config))
        fp.close()

        yield


@contextlib.contextmanager
def _cargo_inject_project_settings(project: Project) -> Iterator[None]:
    settings = cargo_settings(project)
    with _cargo_inject_settings(project.directory, project.context.build_directory / ".mitm-certs", settings):
        yield


class CargoBuildTask(Task):
    """This task runs `cargo build` using the specified parameters. It will respect the authentication
    credentials configured in :attr:`CargoProjectSettings.auth`."""

    args: Property[List[str]]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.args.set([])

    def execute(self) -> TaskResult:
        with _cargo_inject_project_settings(self.project):
            command = ["cargo", "build"] + self.args.get()
            self.logger.info("%s", command)
            result = sp.call(command, cwd=self.project.directory)
            return TaskResult.SUCCEEDED if result == 0 else TaskResult.FAILED


class CargoPublishTask(Task):
    """Publish a Cargo crate."""

    #: The name of the Cargo registry configured in `.cargo/config.yoml` under `[registries]` to publish
    #: the package to.
    registry: Property[str]

    #: Pass the `--allow-dirty` flag to `cargo publish`. This is usually discouraged.
    allow_dirty: Property[bool]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.allow_dirty.set(False)

    def execute(self) -> TaskResult:
        settings = cargo_settings(self.project)
        if self.registry.get() not in settings.registries:
            raise ValueError(f"registry {self.registry.get()!r} is not configured in Kraken project settings")
        registry = settings.registries[self.registry.get()]
        publish_token = registry.get_publish_token(settings.auth)

        with _cargo_inject_project_settings(self.project):
            command = ["cargo", "publish", "--registry", registry.name, "--token", publish_token]
            if self.allow_dirty.get():
                command += ["--allow-dirty"]
            self.logger.info("%s", command)
            result = sp.call(command, cwd=self.project.directory)
            return TaskResult.SUCCEEDED if result == 0 else TaskResult.FAILED
