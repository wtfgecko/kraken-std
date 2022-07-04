#!/usr/bin/env -S kraken run -f

from kraken.api import ctx, project
from kraken.core.action.render_file import RenderFileAction

from kraken.std import docker

dockerfile = project.do(
    "dockerfile",
    RenderFileAction("FROM ubuntu:focal\nRUN echo Hello world\n", ctx.build_directory / "Dockerfile"),
)

docker.build(
    name="buildDocker",
    dockerfile=dockerfile.action.file,
    dependencies=[dockerfile],
    tags=["kraken-example"],
    load=True,
)
