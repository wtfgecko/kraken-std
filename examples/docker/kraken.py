from kraken.api import ctx

from kraken.std import docker
from kraken.std.generic.render_file import render_file

dockerfile = render_file(
    name="dockerfile",
    content="FROM ubuntu:focal\nRUN echo Hello world\n",
    file=ctx.build_directory / "Dockerfile",
)

docker.build(
    name="buildDocker",
    dockerfile=dockerfile.action.get().file,
    dependencies=[dockerfile],
    tags=["kraken-example"],
    load=True,
)
