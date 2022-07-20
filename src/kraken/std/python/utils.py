from __future__ import annotations

from ..git import GitVersion


def git_version_to_python(value: str | GitVersion, include_sha: bool) -> str:
    """Converts a Git version to a Python version.

    :param value: The Git version to convert.
    :param sha: Include the SHA of the commit distance if it exists.
    """

    version = GitVersion.parse(value) if isinstance(value, str) else value
    final_version = f"{version.major}.{version.minor}.{version.patch}"
    if version.distance:
        final_version += f".dev{version.distance.value}"
    if version.distance and include_sha:
        final_version += f"+g{version.distance.sha}"
    return final_version
