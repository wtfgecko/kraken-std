""" Abstraction for Docker build engines. """

from __future__ import annotations

import abc
import base64
import contextlib
import dataclasses
import json
import logging
import shlex
import tempfile
from pathlib import Path
from typing import Any

from kraken.core.utils import flatten

from .cliwrapper import docker_load, docker_run

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class DockerBuildConfig:

    # Build context directory.
    build_context: Path

    # Dockerfile to use.
    dockerfile: Path | None = None

    # Log into the given registries with the username/password combination.
    auth: dict[str, tuple[str, str]] = dataclasses.field(default_factory=dict)

    # Arguments to pass via --build-args.
    build_args: dict[str, str] = dataclasses.field(default_factory=dict)

    # Secret files that can be accessed under `/run/secrets`.
    secrets: dict[str, str] = dataclasses.field(default_factory=dict)

    # A destination for remote caches. Note that this may not be supported by all backends.
    cache_repo: str | None = None

    # Whether to use caching. Enabled by default.
    cache: bool = True

    # A list of tags for the resulting image.
    tags: list[str] = dataclasses.field(default_factory=list)

    # Whether the resulting image should be pushed (using the given :attr:`tags`).
    push: bool = False

    # Squash the final image.
    squash: bool = False

    # The target stage to build in a multi-stage Dockerfile.
    target: str | None = None

    # Save the image to the given file after build as a tarball.
    image_output_file: Path | None = None

    # Load the image into the Docker daemon after building.
    load: bool = False


class DockerBackend(abc.ABC):
    """Backend for docker builds."""

    @abc.abstractmethod
    def build(self, config: DockerBuildConfig, additional_settings: dict[str, Any]) -> None:
        ...


class KanikoBackend(DockerBackend):
    """Build backend for Kaniko."""

    @dataclasses.dataclass
    class KanikoConfig:
        image: str = "gcr.io/kaniko-project/executor:debug"
        context: str = "/workspace"
        cache_copy_layers: bool = True
        snapshot_mode: str = "redo"
        secrets_mount_dir: str = "/run/secrets"

    def _render_auth_file(self, auth: dict[str, tuple[str, str]]) -> str:
        """Renders the JSON configuration that will be written to `/kaniko/.docker/config.json`."""
        return json.dumps(
            {
                "auths": {
                    index: {"auth": base64.b64encode(f"{username}:{password}".encode("ascii")).decode("ascii")}
                    for index, (username, password) in auth.items()
                }
            },
            indent=2,
        )

    def _render_main_script(
        self,
        auth: dict[str, tuple[str, str]],
        secrets: dict[str, str],
        secrets_mount_dir: str,
        executor_command: list[str],
    ) -> str:
        """Renders the shell script that will be executed in the Kaniko container."""

        docker_config = self._render_auth_file(auth)

        script = []
        script += [
            "mkdir -p /kaniko/.docker",
            "cat << EOF > /kaniko/.docker/config.json",
            docker_config,
            "EOF",
        ]

        if secrets:
            script += [f"mkdir -p {shlex.quote(secrets_mount_dir)}"]
            for secret, value in secrets.items():
                script += [f"echo {shlex.quote(value)} > {shlex.quote(secrets_mount_dir + '/' + secret)}"]

        script += [" ".join(map(shlex.quote, executor_command))]
        return "\n".join(script)

    def _get_kaniko_executor_command(
        self,
        build_args: dict[str, str],
        cache_repo: str | None,
        cache: bool,
        destination: list[str],
        dockerfile: str | None,
        push: bool,
        snapshot_mode: str | None,
        single_snapshot: bool,
        target: str | None,
        tar_path: str | None,
        context: str,
    ) -> list[str]:
        if cache and not push and not cache_repo:
            logger.warning("Disabling cache in Kaniko build because it must be combined with push or cache_repo")
            cache = False
        if not destination and tar_path:
            raise ValueError("Need at least one destination (tag) when exporting to an image tarball")
        executor_command = ["/kaniko/executor"]
        executor_command += flatten(("--build-arg", f"{key}={value}") for key, value in build_args.items())
        if cache_repo:
            executor_command += ["--cache-repo", cache_repo]
        if cache:
            executor_command += ["--cache=true"]
        executor_command += flatten(("--destination", destination) for destination in destination)
        if dockerfile:
            executor_command += ["--dockerfile", dockerfile]
        if not push:
            executor_command += ["--no-push"]
        if snapshot_mode:
            executor_command += ["--snapshotMode", snapshot_mode]
        if single_snapshot:
            executor_command += ["--single-snapshot"]
        if target:
            executor_command += ["--target", target]
        if tar_path:
            executor_command += ["--tarPath", tar_path]
        executor_command += ["--context", context]
        return executor_command

    def _build(
        self,
        config: DockerBuildConfig,
        additional_settings: dict[str, Any],
        exit_stack: contextlib.ExitStack,
    ) -> None:
        kaniko_config = self.KanikoConfig(**additional_settings)

        volumes = [f"{config.build_context.absolute()}:{kaniko_config.context}"]

        # If the Dockerfile is not relative to the build context, we need to mount it explicitly.
        dockerfile: str | None = None
        if config.dockerfile:
            try:
                dockerfile = str(config.dockerfile.absolute().relative_to(config.build_context.absolute()))
            except ValueError:
                dockerfile = "/kaniko/Dockerfile"
                volumes += [f"{config.dockerfile.absolute()}:{dockerfile}"]

        # If the image needs to be loaded into the Docker daemon after building, we need to always
        # export it to a file.
        image_output_file = config.image_output_file
        if config.load and not image_output_file:
            tempdir = exit_stack.enter_context(tempfile.TemporaryDirectory())
            image_output_file = Path(tempdir) / "image.tgz"

        # Construct the tar path for inside the container.
        tar_path: str | None = None
        if image_output_file:
            volumes += [f"{image_output_file.parent.absolute()}:/kaniko/out"]
            tar_path = f"/kaniko/out/{image_output_file.name}"

        executor_command = self._get_kaniko_executor_command(
            build_args=config.build_args,
            cache_repo=config.cache_repo,
            cache=config.cache,
            destination=config.tags,
            dockerfile=dockerfile,
            push=config.push,
            single_snapshot=config.squash,
            snapshot_mode=kaniko_config.snapshot_mode,
            target=config.target,
            tar_path=tar_path,
            context=kaniko_config.context,
        )

        script = self._render_main_script(
            config.auth, config.secrets, kaniko_config.secrets_mount_dir, executor_command
        )

        result = docker_run(
            image=kaniko_config.image,
            args=["sh", "-c", script],
            entrypoint="",
            remove=True,
            volumes=volumes,
            workdir=kaniko_config.context,
        )

        if result != 0:
            raise Exception(f"Kaniko build failed with exit code {result}")

        if config.load:
            assert image_output_file is not None, "image_output_file is expected to be set when config.load == True"
            result = docker_load(image_output_file)
            if result != 0:
                raise Exception(f"Docker load failed with exit code {result}")

    def build(self, config: DockerBuildConfig, additional_settings: dict[str, Any]) -> None:
        with contextlib.ExitStack() as exit_stack:
            self._build(config, additional_settings, exit_stack)
