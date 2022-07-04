import contextlib
import subprocess as sp
import tempfile
import textwrap
from pathlib import Path

from kraken.std.docker.backend import KanikoBackend, DockerBackend, DockerBuildConfig


import pytest


@pytest.mark.parametrize("backend", [KanikoBackend()], ids=["kaniko"])
def test_secrets_mounted_and_not_in_final_image(backend: DockerBackend) -> None:
    """Tests that secret file mounts work as expected, i.e. they can be read from `/run/secrets` and they
    do not make it into the final image."""

    secret_name = "MY_SECRET"
    secret_path = f"/run/secrets/{secret_name}"

    dockerfile_content = textwrap.dedent(
        f"""
        FROM alpine:latest
        RUN cat {secret_path}
        """
    )

    with tempfile.TemporaryDirectory() as tempdir, contextlib.ExitStack() as exit_stack:
        assert Path(tempdir).is_dir()

        dockerfile = Path(tempdir) / "Dockerfile"
        dockerfile.write_text(dockerfile_content)

        tag = "kraken-std/tests-ete/test_secrets_mounted_and_not_in_final_image:latest"
        config = DockerBuildConfig(
            build_context=Path(tempdir),
            dockerfile=dockerfile,
            secrets={secret_name: "Hello, World!"},
            cache=False,
            tags=[tag],
            load=True,
        )

        backend.build(config, {})
        exit_stack.callback(lambda: sp.check_call(["docker", "rmi", tag]))

        command = ["sh", "-c", f"find {secret_path} 2>/dev/null || true"]
        output = sp.check_output(["docker", "run", "--rm", tag] + command).decode().strip()
        assert output == ""
