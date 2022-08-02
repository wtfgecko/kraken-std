import contextlib
from pathlib import Path
from typing import Collection, Iterator

from kraken.core.utils import atomic_file_swap


def prepend_secret_mounts(dockerfile_content: str, build_secrets: Collection[str]) -> str:
    """Prepends the `--mount=type=secret,id=...` instructions to make the given *build_secrets* available at each
    `RUN` step of the dockerfile. Returns the updated dockerfile contents."""

    mount_string = " ".join(f"--mount=type=secret,id={sec}" for sec in build_secrets) + " "
    lines = dockerfile_content.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("RUN "):
            line = "RUN " + mount_string + line[4:]
            lines[idx] = line

    return "\n".join(lines)


@contextlib.contextmanager
def prepend_secret_mounts_to_file(dockerfile: Path, build_secrets: Collection[str]) -> Iterator[None]:
    dockerfile_content = dockerfile.read_text()
    with atomic_file_swap(dockerfile, "w", always_revert=True) as fp:
        fp.write(prepend_secret_mounts(dockerfile_content, build_secrets))
        fp.close()
        yield
