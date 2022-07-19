from __future__ import annotations

import base64
import contextlib
import json
import shlex
import tempfile
from pathlib import Path

from kraken.core.project import Project
from kraken.core.property import Property
from kraken.core.task import TaskResult
from kraken.core.utils import flatten

from . import DockerBuildTask
from .dockerapi import docker_load, docker_run


class KanikoBuildTask(DockerBuildTask):
    """An implementation for building Docker images with Kaniko."""

    kaniko_image: Property[str]
    kaniko_context: Property[str]
    kaniko_cache_copy_layers: Property[bool]
    kaniko_snapshot_mode: Property[str]
    kaniko_secrets_mount_dir: Property[str]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.kaniko_image.set("gcr.io/kaniko-project/executor:debug")
        self.kaniko_context.set("/workspace")
        self.kaniko_cache_copy_layers.set(True)
        self.kaniko_snapshot_mode.set("redo")
        self.kaniko_secrets_mount_dir.set("/run/secrets")

    def finalize(self) -> None:
        if self.cache.get() and not self.push.get() and not self.cache_repo.get():
            self.logger.warning(
                "Disabling cache in Kaniko build %s because it must be combined with push or cache_repo",
                self,
            )
            self.cache.set(False)
        cache_repo = self.cache_repo.get_or(None)
        if cache_repo and ":" in cache_repo:
            raise ValueError(f"Kaniko --cache-repo argument cannot contain `:` (got: {cache_repo!r})")
        return super().finalize()

    def _render_auth_file(self) -> str:
        """Renders the JSON configuration that will be written to `/kaniko/.docker/config.json`."""
        return json.dumps(
            {
                "auths": {
                    index: {"auth": base64.b64encode(f"{username}:{password}".encode("ascii")).decode("ascii")}
                    for index, (username, password) in self.auth.get().items()
                }
            },
            indent=2,
        )

    def _render_main_script(self, executor_command: list[str]) -> str:
        """Renders the shell script that will be executed in the Kaniko container."""

        docker_config = self._render_auth_file()

        script = []
        script += [
            "mkdir -p /kaniko/.docker",
            "cat << EOF > /kaniko/.docker/config.json",
            docker_config,
            "EOF",
        ]

        if self.secrets:
            script += [f"mkdir -p {shlex.quote(self.kaniko_secrets_mount_dir.get())}"]
            for secret, value in self.secrets.get().items():
                script += [
                    f"echo {shlex.quote(value)} > {shlex.quote(self.kaniko_secrets_mount_dir.get() + '/' + secret)}"
                ]

        script += [" ".join(map(shlex.quote, executor_command))]
        return "\n".join(script)

    def _get_kaniko_executor_command(self, dockerfile: str | None, tar_path: str | None) -> list[str]:
        if tar_path and not self.tags:
            raise ValueError("Need at least one destination (tag) when exporting to an image tarball")
        executor_command = ["/kaniko/executor"]
        executor_command += flatten(("--build-arg", f"{key}={value}") for key, value in self.build_args.get().items())
        cache_repo = self.cache_repo.get()
        if cache_repo:
            executor_command += ["--cache-repo", cache_repo]
        if self.cache.get_or(False):
            executor_command += ["--cache=true"]
        executor_command += flatten(("--destination", destination) for destination in self.tags.get())
        if dockerfile:
            executor_command += ["--dockerfile", dockerfile]
        if not self.push.get():
            executor_command += ["--no-push"]
        executor_command += ["--snapshotMode", self.kaniko_snapshot_mode.get()]
        if self.squash.get():
            executor_command += ["--single-snapshot"]
        if self.kaniko_cache_copy_layers.get():
            executor_command += ["--cache-copy-layers"]
        target = self.target.get()
        if target:
            executor_command += ["--target", target]
        if tar_path:
            executor_command += ["--tarPath", tar_path]
        executor_command += ["--context", self.kaniko_context.get()]
        return executor_command

    def _build(
        self,
        exit_stack: contextlib.ExitStack,
    ) -> None:
        volumes = [f"{self.build_context.get().absolute()}:{self.kaniko_context.get()}"]

        # If the Dockerfile is not relative to the build context, we need to mount it explicitly.
        in_container_dockerfile: str | None = None
        if self.dockerfile.is_filled():
            try:
                in_container_dockerfile = str(
                    self.dockerfile.get().absolute().relative_to(self.build_context.get().absolute())
                )
            except ValueError:
                in_container_dockerfile = "/kaniko/Dockerfile"
                volumes += [f"{self.dockerfile.get().absolute()}:{in_container_dockerfile}"]

        # If the image needs to be loaded into the Docker daemon after building, we need to always
        # export it to a file.
        image_output_file = self.image_output_file.get_or(None)
        if self.load.get() and not image_output_file:
            tempdir = exit_stack.enter_context(tempfile.TemporaryDirectory())
            image_output_file = Path(tempdir) / "image.tgz"

        # Construct the tar path for inside the container.
        tar_path: str | None = None
        if image_output_file:
            volumes += [f"{image_output_file.parent.absolute()}:/kaniko/out"]
            tar_path = f"/kaniko/out/{image_output_file.name}"

        executor_command = self._get_kaniko_executor_command(in_container_dockerfile, tar_path)

        script = self._render_main_script(executor_command)

        result = docker_run(
            image=self.kaniko_image.get(),
            args=["sh", "-c", script],
            entrypoint="",
            remove=True,
            volumes=volumes,
            workdir=self.kaniko_context.get(),
            platform=self.platform.get_or(None),
        )

        if result != 0:
            raise Exception(f"Kaniko build failed with exit code {result}")

        if self.load.get():
            assert image_output_file is not None, "image_output_file is expected to be set when config.load == True"
            result = docker_load(image_output_file)
            if result != 0:
                raise Exception(f"Docker load failed with exit code {result}")

    def execute(self) -> TaskResult:
        with contextlib.ExitStack() as exit_stack:
            self._build(exit_stack)
        return TaskResult.SUCCEEDED
