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

publish_repo: str | None = None
if "CI" in os.environ:
    if os.environ["GITHUB_REF_TYPE"] == "tag":
        publish_repo = "pypi"
        as_version = git_version_to_python(git_describe(project.directory), True)
    elif os.environ["GITHUB_REF_TYPE"] == "branch" and os.environ["GITHUB_REF_NAME"] == "develop":
        publish_repo = "testpypi"
        as_version = os.environ["GITHUB_REF_NAME"]
    else:
        raise EnvironmentError(
            f"GITHUB_REF_TYPE={os.environ['GITHUB_REF_TYPE']}, GITHUB_REF_NAME={os.environ['GITHUB_REF_NAME']}"
        )
    build_task = build(as_version=as_version)
    publish(package_index=publish_repo, distributions=build_task.output_files)
else:
    build()
