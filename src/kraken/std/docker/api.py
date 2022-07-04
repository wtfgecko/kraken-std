from __future__ import annotations

from pathlib import Path

from kraken.core.action import Action, ActionResult
from kraken.core.task import AnyTask

# from .backend import DockerBackend, KanikoBackend


class DockerBuildAction(Action):
    def execute(self) -> ActionResult:
        return ActionResult.SUCCEEDED


def docker_build(
    name: str,
    default: bool = True,
    build_context: Path | str | None = None,
    dockerfile: Path | None = None,
    auth: dict[str, tuple[str, str]] | None = None,
    build_args: dict[str, str] | None = None,
    secrets: dict[str, str] | None = None,
    cache_repo: str | None = None,
    cache: bool = True,
    tags: list[str] | None = None,
    push: bool = False,
    squash: bool = False,
    target: str | None = None,
    image_output_file: Path | None = None,
) -> AnyTask:

    from kraken.api import project

    if not build_context:
        build_context = project.directory
    build_context = project.directory / build_context

    return project.do(name, DockerBuildAction(), default=default)
