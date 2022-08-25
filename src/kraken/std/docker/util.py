from __future__ import annotations

import base64
import json
from typing import Mapping


def render_docker_auth(auth: Mapping[str, tuple[str, str]], indent: int | None = None) -> str:
    """Generates a Docker auth config as JSON."""

    return json.dumps(
        {
            "auths": {
                index: {"auth": base64.b64encode(f"{username}:{password}".encode("ascii")).decode("ascii")}
                for index, (username, password) in auth.items()
            }
        },
        indent=indent,
    )


def update_run_commands(dockerfile_content: str, prefix: str, suffix: str = "") -> str:
    """Prepends a prefix string to all `RUN` commands in a Dockerfile."""

    lines = dockerfile_content.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("RUN "):
            line = "RUN " + prefix + line[4:] + suffix
            lines[idx] = line
    return "\n".join(lines)
