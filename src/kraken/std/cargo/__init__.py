""" Provides tasks for Rust projects that build using Cargo. """

from __future__ import annotations

from typing import Sequence

from kraken.core import Project, Supplier
from typing_extensions import Literal

from .config import CargoProject, CargoRegistry
from .tasks.cargo_auth_proxy_task import CargoAuthProxyTask
from .tasks.cargo_build_task import CargoBuildTask
from .tasks.cargo_bump_version_task import CargoBumpVersionTask
from .tasks.cargo_fmt_task import CargoFmtTask
from .tasks.cargo_publish_task import CargoPublishTask
from .tasks.cargo_sync_config_task import CargoSyncConfigTask

__all__ = [
    "CargoBuildTask",
    "CargoPublishTask",
    "CargoSyncConfigTask",
    "CargoAuthProxyTask",
    "CargoBumpVersionTask",
    "CargoProject",
    "CargoRegistry",
    "cargo_registry",
    "cargo_auth_proxy",
    "cargo_sync_config",
    "cargo_fmt",
    "cargo_build",
    "cargo_publish",
]

CARGO_SYNC_CONFIG_TASK_NAME = "cargoSyncConfig"
CARGO_AUTH_PROXY_TASK_NAME = "cargoAuthProxy"


def cargo_registry(
    alias: str,
    index: str,
    read_credentials: tuple[str, str] | None = None,
    publish_token: str | None = None,
    project: Project | None = None,
) -> None:
    """Adds a Cargo registry to the project. The registry must be synced to disk into the `.cargo/config.toml`
    configuration file. You need to make sure to add a sync task using :func:`cargo_sync_config` if you manage
    your Cargo registries with this function. Can be called multiple times.

    :param alias: The registry alias.
    :param index: The registry index URL (usually an HTTPS URL that ends in `.git`).
    :param read_credentials: Username/password to read from the registry (only for private registries).
    :param publish_token: The token to use with `cargo publish`.

    !!! note Artifactory

        It appears that for Artifactory, the *publish_token* must be of the form `Bearer <TOKEN>` where the token
        is a token generated manually via the JFrog UI. It cannot be an API key.
    """

    cargo = CargoProject.get_or_create(project)
    cargo.add_registry(alias, index, read_credentials, publish_token)


def cargo_auth_proxy(*, project: Project | None = None) -> CargoAuthProxyTask:
    """Creates a background task that the :func:`cargo_build` and :func:`cargo_publish` tasks will depend on to
    inject the read credentials for private registries into HTTPS requests made by Cargo. This is only needed when
    private registries are used."""

    project = project or Project.current()
    cargo = CargoProject.get_or_create(project)
    task = project.do(
        CARGO_AUTH_PROXY_TASK_NAME,
        CargoAuthProxyTask,
        False,
        registries=Supplier.of_callable(lambda: list(cargo.registries.values())),
    )
    task.add_relationship(f":{CARGO_SYNC_CONFIG_TASK_NAME}?")
    return task


def cargo_sync_config(
    *,
    name: str = "cargoSyncConfig",
    project: Project | None = None,
    replace: bool = False,
) -> CargoSyncConfigTask:
    """Creates a task that the :func:`cargo_build` and :func:`cargo_publish` tasks will depend on to synchronize
    the `.cargo/config.toml` configuration file, ensuring that the Cargo registries configured with the
    :func:`cargo_registry` function are present and up to date."""

    project = project or Project.current()
    cargo = CargoProject.get_or_create(project)
    return project.do(
        CARGO_SYNC_CONFIG_TASK_NAME,
        CargoSyncConfigTask,
        True,
        group="fmt",
        registries=Supplier.of_callable(lambda: list(cargo.registries.values())),
        replace=replace,
    )


def cargo_fmt(*, project: Project | None = None) -> None:
    project = project or Project.current()
    project.do("cargoFmt", CargoFmtTask, False, group="fmt")
    project.do("cargoFmtCheck", CargoFmtTask, True, group="lint", check=True)


def cargo_build(
    mode: Literal["debug", "release"],
    *,
    name: str | None = None,
    project: Project | None = None,
) -> CargoBuildTask:
    """Creates a task that runs `cargo build`.

    :param mode: Whether to create a task that runs the debug or release build.
    :param name: The name of the task. If not specified, defaults to `:cargoBuild{mode.capitalied()}`."""

    assert mode in ("debug", "release"), repr(mode)
    project = project or Project.current()
    task = project.do(
        f"cargoBuild{mode.capitalize()}" if name is None else name,
        CargoBuildTask,
        False,
        group="build",
        args=["--release"] if mode == "release" else [],
    )
    task.add_relationship(f":{CARGO_AUTH_PROXY_TASK_NAME}?")
    task.add_relationship(f":{CARGO_SYNC_CONFIG_TASK_NAME}?")
    return task


def cargo_publish(
    registry: str,
    additional_args: Sequence[str] = (),
    version: str | None = None,
    *,
    name: str = "cargoPublish",
    project: Project | None = None,
) -> CargoPublishTask:
    """Creates a task that publishes the create to the specified *registry*.

    :param registry: The alias of the registry to publish to.
    :param version: The version number to publish. If specified, a cargo bump task will be added. If a version
        number to bump to is specified, the `--allow-dirty` option is automatically passed to Cargo.
    """

    project = project or Project.current()
    cargo = CargoProject.get_or_create(project)

    additional_args = list(additional_args)
    if version is not None and "--allow-dirty" not in additional_args:
        additional_args.append("--allow-dirty")

    task = project.do(
        name,
        CargoPublishTask,
        False,
        group="publish",
        registry=Supplier.of_callable(lambda: cargo.registries[registry]),
        additional_args=additional_args,
    )
    task.add_relationship(f":{CARGO_AUTH_PROXY_TASK_NAME}?")
    task.add_relationship(f":{CARGO_SYNC_CONFIG_TASK_NAME}?")

    if version is not None:
        bump_task = project.do(
            f"{name}/bump",
            CargoBumpVersionTask,
            False,
            version=version,
            revert=True,
        )
        task.add_relationship(bump_task)

    return task
