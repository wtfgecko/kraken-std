from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from kraken.core import Project, Property, Task
from kraken.core.utils import import_class

__version__ = "0.1.0"
__all__ = ["build", "DockerBuildTask"]

DEFAULT_BUILD_BACKEND = "native"
BUILD_BACKENDS = {
    "buildx": f"{__name__}.buildx.BuildxBuildTask",
    "kaniko": f"{__name__}.kaniko.KanikoBuildTask",
    "native": f"{__name__}.native.NativeBuildTask",
}


class DockerBuildTask(Task):
    """Base class for tasks that build Docker images. Subclasses implement converting the task properties into
    the invokation for a Docker build backend."""

    build_context: Property[Path]
    dockerfile: Property[Path]
    auth: Property[Dict[str, Tuple[str, str]]]
    platform: Property[str]
    build_args: Property[Dict[str, str]]
    secrets: Property[Dict[str, str]]
    cache_repo: Property[Optional[str]]
    cache: Property[bool]
    tags: Property[List[str]]
    push: Property[bool]
    squash: Property[bool]
    target: Property[Optional[str]]
    image_output_file: Property[Optional[Path]]
    load: Property[bool]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.build_context.set(project.directory)
        self.auth.setdefault({})
        self.build_args.setdefault({})
        self.secrets.setdefault({})
        self.cache_repo.setdefault(None)
        self.cache.set(True)
        self.tags.setdefault([])
        self.push.set(False)
        self.squash.set(False)
        self.target.setdefault(None)
        self.image_output_file.setdefault(None)
        self.load.setdefault(False)


def build_docker_image(
    *,
    name: str = "buildDocker",
    backend: str = DEFAULT_BUILD_BACKEND,
    project: Project | None = None,
    **kwds: Any,
) -> DockerBuildTask:
    """Create a new task in the current project that builds a Docker image and eventually pushes it."""

    task_class = import_class(BUILD_BACKENDS[backend], DockerBuildTask)  # type: ignore[misc]
    return (project or Project.current()).do(name, task_class, **kwds)
