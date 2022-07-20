from __future__ import annotations

import dataclasses
import logging
from pathlib import Path

from kraken.core import Project

from .buildsystem import PythonBuildSystem, detect_build_system

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class PythonIndex:
    url: str
    credentials: tuple[str, str] | None
    is_package_source: bool


@dataclasses.dataclass
class PythonSettings:
    """Project-global settings for Python tasks."""

    project: Project
    build_system: PythonBuildSystem | None = None
    source_directory: Path = Path("src")
    tests_directory: Path | None = None
    package_indexes: dict[str, PythonIndex] = dataclasses.field(default_factory=dict)

    def get_tests_directory(self) -> Path | None:
        """Returns :attr:`tests_directory` if it is set. If not, it will look for the following directories and
        return the first that exists: `test/`, `tests/`, `src/test/`, `src/tests/`. The determined path will be
        relative to the project directory."""

        if self.tests_directory:
            return self.tests_directory
        for test_dir in map(Path, ["test", "tests", "src/test", "src/tests"]):
            if (self.project.directory / test_dir).is_dir():
                return test_dir
        return None

    def get_tests_directory_as_args(self) -> list[str]:
        """Returns a list with a single item that is the test directory, or an empty list. This is convenient
        when constructing command-line arguments where you want to pass the test directory if it exists."""

        test_dir = self.get_tests_directory()
        return [] if test_dir is None else [str(test_dir)]

    def add_package_index(
        self,
        alias: str,
        url: str,
        credentials: tuple[str, str] | None,
        is_package_source: bool = True,
    ) -> None:
        """Adds an index to consume Python packages from or publish packages to.

        :param alias: An alias for the package index.
        :param url: The URL of the package index (without the trailing `/simple` bit).
        :param credentials: Optional credentials to read from the index.
        :param is_package_source: If set to `False`, the index will not be used to source packages from, but
            can be used to publish to.
        """

        self.package_indexes[alias] = PythonIndex(url, credentials, is_package_source)


def python_settings(
    project: Project | None = None,
    build_system: PythonBuildSystem | None = None,
    source_directory: str | Path | None = None,
    tests_directory: str | Path | None = None,
) -> PythonSettings:
    """Read the Python settings for the given or current project and optionally update attributes.

    :param project: The project to get the settings for. If not specified, the current project will be used.
    :environment_handler: If specified, set the :attr:`PythonSettings.environment_handler`. If a string is specified,
        the following values are currently supported: `"poetry"`.
    :param source_directory: The source directory. Defaults to `"src"`.
    :param tests_directory: The tests directory. Automatically determined if left empty.
    """

    project = project or Project.current()
    settings = project.find_metadata(PythonSettings)
    if settings is None:
        settings = PythonSettings(project)
        project.metadata.append(settings)

    if build_system is None and settings.build_system is None:
        # Autodetect the environment handler.
        build_system = detect_build_system(project.directory)
        if build_system:
            logger.info("Detected Python build system %r for %s", type(build_system).__name__, project)

    if build_system is not None:
        if settings.build_system:
            logger.warning(
                "overwriting existing PythonSettings.environment_handler=%r with %r",
                settings.build_system,
                build_system,
            )
        settings.build_system = build_system

    if source_directory is not None:
        settings.source_directory = Path(source_directory)

    if tests_directory is not None:
        settings.tests_directory = Path(tests_directory)

    return settings
