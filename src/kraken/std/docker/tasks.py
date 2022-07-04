from __future__ import annotations

from pathlib import Path
from typing import Any

from kraken.core.action import Action, ActionResult
from kraken.core.project import Project
from kraken.core.task import AnyTask, Task, TaskCaptureMode

from .backend import DockerBackend, DockerBuildConfig, KanikoBackend

DEFAULT_BACKEND = "kaniko"

backends: dict[str, type[DockerBackend]] = {
    "kaniko": KanikoBackend,
}


class DockerBuildTask(Task["DockerBuildTask"], Action):

    config: DockerBuildConfig
    backend: DockerBackend
    backend_options: dict[str, Any]

    def __init__(
        self,
        name: str,
        project: Project,
        config: DockerBuildConfig,
        backend: DockerBackend,
        backend_options: dict[str, Any],
    ) -> None:
        super().__init__(name, project, self)
        self.config = config
        self.backend = backend
        self.backend_options = backend_options

    def execute(self) -> ActionResult:
        self.backend.build(self.config, self.backend_options)
        return ActionResult.SUCCEEDED


def docker_build(
    *,
    name: str,
    default: bool = True,
    dependencies: list[str | AnyTask] | None = None,
    build_context: Path | str | None = None,
    dockerfile: Path | str | None = None,
    auth: dict[str, tuple[str, str]] | None = None,
    build_args: dict[str, str] | None = None,
    secrets: dict[str, str] | None = None,
    cache_repo: str | None = None,
    cache: bool = True,
    tags: list[str] | None = None,
    push: bool = False,
    squash: bool = False,
    target: str | None = None,
    image_output_file: Path | str | None = None,
    load: bool = False,
    backend: str = DEFAULT_BACKEND,
    backend_options: dict[str, Any] | None = None,
) -> DockerBuildTask:
    """Create a new task in the current project that builds a Docker image and eventually pushes it.

    Args:
        name: The task name.
        default: Whether the task is built by default.
        build_context: The Docker build context. Defaults to the project root directory.
        dockerfile: The Dockerfile to use as input.
        auth: Credentials for reading/writing Docker images.
        build_args: Build arguments for the docker build.
        secrets: Secrets that are accessible under `/run/secrets`.
        cache_repo: A repository to write build caches to.
        cache: Read/write caches.
        tags: A list of image tags for the final image.
        push: Set to True to push images based on *tags*.
        squash: Squash the final image layer.
        target: Target stage to build in a multi-stage Dockerfile.
        image_output_file: Write the image to the given path as a tarball.
        load: Whether the produced image should be loaded into the Docker runtime.
        backend: The Docker build backend.
        backend_options: Additional options for the build backend.
    Returns:
        The created task.
    """

    from kraken.api import project

    if not build_context:
        build_context = project.directory
    build_context = project.directory / build_context

    task = DockerBuildTask(
        name=name,
        project=project,
        config=DockerBuildConfig(
            build_context=build_context,
            dockerfile=project.to_path(dockerfile),
            auth=auth or {},
            build_args=build_args or {},
            secrets=secrets or {},
            cache_repo=cache_repo,
            cache=cache,
            tags=tags or [],
            push=push,
            squash=squash,
            target=target,
            image_output_file=project.to_path(image_output_file),
            load=load,
        ),
        backend=backends[backend](),
        backend_options=backend_options or {},
    )
    task.default = default
    task.capture = TaskCaptureMode.NONE
    task.dependencies = project.resolve_tasks(dependencies or [])
    project.tasks.add(task)
    return task
