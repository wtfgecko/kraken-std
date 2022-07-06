from __future__ import annotations

from typing import Any

from kraken.core.project import Project
from kraken.core.task import task_factory

from .tasks import DockerBuildTask, KanikoBuildTask

__version__ = "0.1.0"
__all__ = ["build", "DockerBuildTask"]


DEFAULT_BUILD_BACKEND = "kaniko"
BUILD_BACKENDS = {"kaniko": KanikoBuildTask}


def build_docker_image(
    *,
    name: str = "buildDocker",
    default: bool = False,
    backend: str = DEFAULT_BUILD_BACKEND,
    project: Project | None = None,
    **kwds: Any,
) -> DockerBuildTask:
    """Create a new task in the current project that builds a Docker image and eventually pushes it."""

    factory = task_factory(BUILD_BACKENDS[backend], capture=False)
    return factory(name=name, default=default, project=project, **kwds)
