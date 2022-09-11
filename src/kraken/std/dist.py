"""Create distributions (archives) from build artifacts and resources."""

from __future__ import annotations

import abc
import logging
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Sequence, Union, cast

from kraken.core import Project, Property, Task
from termcolor import colored
from typing_extensions import Literal

from .descriptors.resource import BinaryArtifact, Resource

logger = logging.getLogger(__name__)


class DistributionTask(Task):
    """Create an archive from a set of files and resources."""

    #: The output filename. If a string is specified, that string is treated relative
    #: to the project output directory. A Path object is treated relative to the project
    #: directory. Unless the :attr:`archive_type` property is set, the suffix will determine
    #: the type of archive that is created.
    output_file: Property[Union[str, Path]]

    #: The type of archive that will be created. Can be zip, tgz and tar.
    archive_type: Property[str]

    #: Prefix to add to all files added to the distribution.
    prefix: Property[str]

    #: A list of resources to include.
    resources: Property[list[Resource]] = Property.default_factory(list)

    # Task

    def execute(self) -> None:
        output_file = self.output_file.get()
        if isinstance(output_file, str):
            output_file = self.project.build_directory / output_file
        else:
            output_file = self.project.directory / output_file

        archive_type = self.archive_type.get_or(None)
        if archive_type is None:
            archive_type = output_file.suffix.lstrip(".")
            archive_type = {"tgz": "tar.gz", "txz": "tar.xz", "tbz2": "tar.bz2"}.get(archive_type, archive_type)
        assert isinstance(archive_type, str)

        print("Writing archive", colored(str(output_file), "yellow"))
        with wopen_archive(output_file, archive_type) as archive:
            for resource in self.resources.get():
                if isinstance(resource, BinaryArtifact):
                    arcname = resource.path.name
                else:
                    arcname = str(resource.path)
                print("  +", colored(arcname, "green"), f"({resource.path})" if arcname != str(resource.path) else "")
                archive.add_path(arcname, self.project.directory / resource.path)


def wopen_archive(path: Path, type_: str) -> ArchiveWriter:
    """Open an archive at *path* for writing. The *type_* indicates what type of archive will be created.
    Accepted values for *type_* are `zip`, `tar`, `tar.gz`, `tar.bz2` and `tar.xz`."""

    if type_.startswith("tar."):
        return TarArchiveWriter(path, cast(Any, type_.partition(".")[-1]))
    elif type_ == "tar":
        return TarArchiveWriter(path, "")
    elif type_ == "zip":
        return ZipArchiveWriter(path)
    else:
        raise ValueError(f"unsupported archive type: {type_!r}")


class ArchiveWriter(abc.ABC):
    """Base class to write an archive file."""

    @abc.abstractmethod
    def add_file(self, arcname: str, path: Path) -> None:
        """Add a file to the archive."""

    @abc.abstractmethod
    def close(self) -> None:
        pass

    def add_path(self, arcname: str, path: Path) -> None:
        """Recursively add the contents of all files under *path*."""

        if path.is_dir():
            for item in path.iterdir():
                self.add_path(arcname + "/" + item.name, item)
        else:
            self.add_file(arcname, path)

    def __enter__(self) -> ArchiveWriter:
        return self

    def __exit__(self, *a: Any) -> None:
        self.close()


class TarArchiveWriter(ArchiveWriter):
    def __init__(self, path: Path, type_: Literal["", "gz", "bz2", "xz"]) -> None:
        self._archive = tarfile.open(path, mode="w:" + type_)

    def close(self) -> None:
        self._archive.close()

    def add_file(self, arcname: str, path: Path) -> None:
        self._archive.add(path, arcname, recursive=False)


class ZipArchiveWriter(ArchiveWriter):
    def __init__(self, path: Path) -> None:
        self._archive = zipfile.ZipFile(path, "w")

    def close(self) -> None:
        self._archive.close()

    def add_file(self, arcname: str, path: Path) -> None:
        self._archive.write(path, arcname)


def dist(
    *,
    name: str,
    dependencies: Sequence[str | Task],
    output_file: str | Path,
    archive_type: str | None = None,
    prefix: str | None = None,
    project: Project | None = None,
) -> DistributionTask:
    """Create a task that produces a distribution from the resources provided by the tasks specified with *include*.

    :param name: The name of the task.
    :param dependencies: A list of tasks or task selectors (resolved relative to the *project*) that provide the
        resources that should be included in the generated archive.
    :param output_file: The output filename to write to. If a string is specified, it will be treated relative to the
        project build directory. If a path object is specified, it will be treated relative to the project directory.
    :param archive_type: The type of archive to create (e.g. `zip`, `tar`, `tar.gz`, `tar.bz2` or `tar.xz`). If left
        empty, the archive type is derived from the *output_filename* suffix.
    :param project: The project to create the task for.
    """

    project = project or Project.current()
    return project.do(
        name,
        DistributionTask,
        resources=project.resolve_tasks(dependencies).select(Resource).supplier(),
        output_file=output_file,
        archive_type=archive_type,
        prefix=prefix,
    )
