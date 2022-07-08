from kraken.api import ctx

from kraken.std.docker import build_docker_image
from kraken.std.generic.render_file import render_file

dockerfile = render_file(
    name="dockerfile",
    content="FROM ubuntu:focal\nRUN echo Hello world\n",
    file=ctx.build_directory / "Dockerfile",
)

build_docker_image(
    name="buildDocker",
    dockerfile=dockerfile.file,
    tags=["kraken-example"],
    load=True,
)
