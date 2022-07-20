# ::requirements kraken-std@.

from __future__ import annotations

import os

from kraken.api import project

from kraken.std.git import git_describe
from kraken.std.python import (
    black,
    build,
    flake8,
    git_version_to_python,
    install,
    isort,
    mypy,
    publish,
    pytest,
    python_settings,
)

black()
flake8()
isort()
mypy()
pytest(ignore_dirs=["src/tests/integration"])
pytest(name="pytestIntegration", tests_dir="src/tests/integration")
install()

settings = python_settings()
settings.add_package_index(
    "pypi",
    credentials=(os.environ["PYPI_USER"], os.environ["PYPI_PASSWORD"]) if "PYPI_USER" in os.environ else None,
)
settings.add_package_index(
    "testpypi",
    credentials=(os.environ["TESTPYPI_USER"], os.environ["TESTPYPI_PASSWORD"])
    if "TESTPYPI_USER" in os.environ
    else None,
)

if "CI" in os.environ:
    if os.environ["GITHUB_REF_TYPE"] == "tag":
        # TODO (@NiklasRosenstein): It would be nice to add a test that checks if the version in the package
        #       is consistent (ie. run `slap release --validate <tag>`).
        is_release = True
        as_version = os.environ["GITHUB_REF_NAME"]
    elif os.environ["GITHUB_REF_TYPE"] == "branch" and os.environ["GITHUB_REF_NAME"] == "develop":
        is_release = False
        as_version = git_version_to_python(git_describe(project.directory), False)
    else:
        raise EnvironmentError(
            f"GITHUB_REF_TYPE={os.environ['GITHUB_REF_TYPE']}, GITHUB_REF_NAME={os.environ['GITHUB_REF_NAME']}"
        )
else:
    is_release = False
    as_version = None

build_task = build(as_version=as_version)
testpypi = publish(name="publishToTestPypi", package_index="testpypi", distributions=build_task.output_files)
if is_release:
    publish(name="publishToPypi", package_index="pypi", distributions=build_task.output_files, after=[testpypi])
