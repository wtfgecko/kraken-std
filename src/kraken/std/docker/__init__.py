from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from kraken.core.project import Project
from kraken.core.property import Property
from kraken.core.task import Task, task_factory
from kraken.core.utils import import_class

__version__ = "0.1.0"
__all__ = ["build", "DockerBuildTask"]

DEFAULT_BUILD_BACKEND = "kaniko"
BUILD_BACKENDS = {
    "kaniko": f"{__name__}.kaniko.KanikoBuildTask",
    "buildx": f"{__name__}.buildx.BuildxBuildTask",
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
    default: bool = False,
    backend: str = DEFAULT_BUILD_BACKEND,
    project: Project | None = None,
    **kwds: Any,
) -> DockerBuildTask:
    """Create a new task in the current project that builds a Docker image and eventually pushes it."""

    task_class = import_class(BUILD_BACKENDS[backend], DockerBuildTask)  # type: ignore[misc]
    factory = task_factory(task_class, capture=False)
    return factory(name=name, default=default, project=project, **kwds)
