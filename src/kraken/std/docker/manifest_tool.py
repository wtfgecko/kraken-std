import platform
import shutil
import subprocess as sp
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import List

import httpx
from kraken.core import Project, Property, Task, TaskResult

RELEASE_URL = (
    "https://github.com/estesp/manifest-tool/releases/download/v{VERSION}/binaries-manifest-tool-{VERSION}.tar.gz"
)

# TODO (@NiklasRosenstein): Use existing manifest tool if it exists.
# TODO (@NiklasRosenstein): Ensure manifest-tool has credentials to push to the target


class ManifestToolPushTask(Task):
    """A task that uses `manifest-tool` to combine multiple container images from different platforms into a single
    multi-platform manifest.

    For more information on `manifest-tool`, check out the GitHub repository:

    https://github.com/estesp/manifest-tool/
    """

    #: The Docker platforms to create the manifest for.
    platforms: Property[List[str]]

    #: A Docker image tag that should contain the variables `OS`, `ARCH` and `VARIANT`.
    template: Property[str]

    #: The image ID to push the Docker image to.
    target: Property[str]

    #: Prefer the local version of the tool if available. Default is `true`.
    manifest_tool_local: Property[bool]

    #: The tool version to use. The appropriate release will be downloaded from Github.
    manifest_tool_version: Property[str]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.manifest_tool_local.set(True)
        self.manifest_tool_version.set("2.0.4")

    def fetch_manifest_tool(self) -> Path:
        """Fetches the manifest tool binary that is appropriate for the current platform."""

        if self.manifest_tool_local.get():
            path = shutil.which("manifest-tool")
            if path is not None:
                self.logger.info("using %s", path)
                return Path(path)

        version = self.manifest_tool_version.get()
        manifest_tool_dir = self.project.context.build_directory / ".downloads" / f"manifest-tool-{version}"
        if not manifest_tool_dir.is_dir():
            download_url = RELEASE_URL.format(VERSION=version)
            self.logger.info("downloading manifest-tool release v%s (%s) ...", version, download_url)
            with httpx.stream(
                "GET", download_url, follow_redirects=True
            ) as fp, tempfile.TemporaryDirectory() as tempdir:
                fp.raise_for_status()
                archive = Path(tempdir) / download_url.rpartition("/")[-1]
                with archive.open("wb") as dst:
                    for chunk in fp.iter_bytes():
                        dst.write(chunk)
                with tarfile.open(archive, mode="r:gz") as tf:
                    tf.extractall(manifest_tool_dir)

        filename = f"manifest-tool-{sys.platform}-{platform.machine()}"
        binary = manifest_tool_dir / filename
        if not binary.is_file():
            raise RuntimeError("unable to construct valid path to binary for downloaded manifest-tool release")

        self.logger.info("using %s", binary)
        return binary

    def execute(self) -> TaskResult:
        binary = self.fetch_manifest_tool()
        command = [
            str(binary),
            "push",
            "from-args",
            "--platforms",
            ",".join(self.platforms.get()),
            "--template",
            self.template.get(),
            "--target",
            self.target.get(),
        ]
        self.logger.info("%s", command)
        result = sp.call(command)
        if result != 0:
            return TaskResult.FAILED
        return TaskResult.SUCCEEDED
