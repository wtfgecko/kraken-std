from __future__ import annotations

import contextlib
import subprocess as sp
import tempfile
import textwrap
from pathlib import Path

import pytest
from kraken.core.project import Project
from kraken.testing import context, project  # noqa: F401

from kraken.std.docker.tasks import DockerBuildTask, KanikoBuildTask


@pytest.mark.parametrize("task_type", [KanikoBuildTask], ids=["kaniko"])
def test_secrets_mounted_and_not_in_final_image(
    project: Project,  # noqa: F811
    task_type: type[DockerBuildTask],
) -> None:
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

        task = task_type("buildDocker", project)
        task.build_context.set(Path(tempdir))
        task.dockerfile.set(dockerfile)
        task.secrets.set({secret_name: "Hello, World!"})
        task.cache.set(False)
        task.tags.set([tag])
        task.load.set(True)
        task.execute()

        exit_stack.callback(lambda: sp.check_call(["docker", "rmi", tag]))

        command = ["sh", "-c", f"find {secret_path} 2>/dev/null || true"]
        output = sp.check_output(["docker", "run", "--rm", tag] + command).decode().strip()
        assert output == ""
