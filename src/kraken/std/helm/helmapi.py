from __future__ import annotations

import contextlib
import shutil
import subprocess as sp
import tempfile
from pathlib import Path


def helm_package(
    chart_path: Path,
    output_file: Path | None = None,
    output_directory: Path | None = None,
    app_version: str | None = None,
    version: str | None = None,
) -> tuple[int, Path | None]:
    """Package a Helm chart."""

    if output_file is not None and output_directory is not None:
        raise ValueError("output_file and output_directory cannot both be set")

    with contextlib.ExitStack() as exit_stack:
        command = ["helm", "package", str(chart_path)]

        tempdir: Path | None = None
        if output_directory is None or output_file is not None:
            # We build into a temporary directory first.
            tempdir = Path(exit_stack.enter_context(tempfile.TemporaryDirectory()))
            command += ["--destination", str(tempdir)]
        else:
            command += ["--destination", str(output_directory)]
        if app_version:
            command += ["--appVersion", app_version]
        if version:
            command += ["--version", version]

        result = sp.call(command)
        if result != 0:
            return result, None

        if output_file:
            assert tempdir is not None
            output_file.parent.mkdir(exist_ok=True, parents=True)
            if output_file.exists():
                output_file.unlink()
            chart_file = next(Path(tempdir).iterdir())
            shutil.move(str(chart_file), output_file)
        else:
            assert output_directory is not None
            chart_file = next(output_directory.iterdir())

        return 0, chart_file

    assert False


def helm_registry_login(registry: str, username: str, password: str, insecure: bool = False) -> int:
    """Log into a Helm registry."""

    command = ["helm", "registry", "login", registry, "-u", username, "--password-stdin"]
    if insecure:
        command += ["--insecure"]
    return sp.run(command, input=f"{password}\n".encode()).returncode


def helm_push(chart_tarball: Path, remote: str) -> int:
    """Push a Helm chart to a remote."""

    command = ["helm", "push", str(chart_tarball), remote]
    return sp.call(command)
