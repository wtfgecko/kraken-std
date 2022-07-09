"""This test is an end-to-end test to publish and consume crates from Artifactory/Cloudsmith. It performs the
following steps:

* Create a temporary Cargo repository in Artifactory/Cloudsmith
* Publish the `data/hello-world-lib` using the :func:`cargo_publish()` task
* Consume the just published library in `data/hello-world-app` using the :func:`cargo_build()` task

Without injecting the HTTP basic authentication credentials into the Cargo publish and build steps, we
expect the publish and/or build step to fail.

The test runs in a new temporary `CARGO_HOME` directory to ensure that Cargo has to freshly fetch the
Artifactory/Cloudsmith repository Git index every time.

!!! note

    This integration tests requires live remote repository credentials with enough permissions to create and delete
    repositories and to create a new user with access to the repository. If we get setting up an actual Artifactory
    or Cloudsmith instance within the tests, it would be very nice, but until then we need to inject these credentials
    in CI via an environment variable. Unless the environment variable is present, the test will be skipped.
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import logging
import os
import tempfile
import time
import unittest.mock
import urllib.parse
import uuid
from pathlib import Path
from typing import Iterator

import pytest
from kraken.core.utils import not_none
from kraken.testing import kraken_ctx, kraken_execute, kraken_project

from kraken.std.cargo import cargo_build, cargo_publish, cargo_settings

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class CargoRepositoryWithAuth:
    name: str
    index_url: str
    user: str
    password: str


@contextlib.contextmanager
def create_cargo_repository_in_artifactory(artifactory: dict[str, str]) -> Iterator[CargoRepositoryWithAuth]:
    """Sets up a Cargo repository in Artifactory."""

    import requests
    from pyartifactory.models.repository import LocalRepository, PackageTypeEnum
    from pyartifactory.objects import Artifactory

    client = Artifactory(artifactory["url"], (artifactory["user"], artifactory["password"]))
    repository_name = f"kraken-integration-test-cargo-{str(uuid.uuid4())[:7]}"

    # Create a new Artifactory Cargo repository.
    logger.info("Creating Cargo repository %r in Artifactory %r", repository_name, artifactory["url"])
    local_repo = LocalRepository(
        key=repository_name,
        packageType=PackageTypeEnum.cargo,
        propertySets=["artifactory"],
        repoLayoutRef="cargo-default",
    )
    try:
        client.repositories.create_repo(local_repo)
    except requests.exceptions.HTTPError as exc:
        logger.error("Encountered an HTTPError while creating repository. body=%s", exc.response.text)
        raise
    logger.info("Cargo repository %r created", repository_name)

    try:
        index_url = f"{artifactory['url']}/git/{repository_name}.git"
        logger.info("Expected Cargo index URL is %r", index_url)
        yield CargoRepositoryWithAuth(repository_name, index_url, artifactory["user"], artifactory["password"])
    finally:
        assert artifactory is not None
        logger.info("Deleting Cargo repository %r from Artifactory %r", repository_name, artifactory["url"])
        client.repositories.delete(repository_name)


@contextlib.contextmanager
def create_cargo_repository_in_cloudsmith(cloudsmith: dict[str, str]) -> Iterator[CargoRepositoryWithAuth]:
    """Sets up a Cargo repository in Cloudsmith."""

    from cloudsmith_api import ApiClient, Configuration, ReposApi, ReposCreate  # type: ignore[import]

    config = Configuration()
    config.api_key["X-Api-Key"] = cloudsmith["api_key"]
    client = ApiClient(config)
    repos = ReposApi(client)

    repository_name = f"kraken-integration-test-cargo-{str(uuid.uuid4())[:7]}"

    logger.info("Creating Cloudsmith repository %r", repository_name)
    data = ReposCreate(
        description="temporary integration test repository",
        name=repository_name,
        repository_type_str="private",
    )
    response = repos.repos_create(cloudsmith["owner"], data=data)
    logger.info("Cloudsmith repository %r created.", repository_name)

    index_url = f"{response.cdn_url}/cargo/index.git"
    try:
        yield CargoRepositoryWithAuth(repository_name, index_url, cloudsmith["user"], cloudsmith["api_key"])
    finally:
        logger.info("Deleting Cloudsmith repository %r", repository_name)
        repos.repos_delete(cloudsmith["owner"], identifier=repository_name)


def publish_lib_and_build_app(repository: CargoRepositoryWithAuth) -> None:

    data_dir = Path(__file__).parent / "data"
    repository_host = not_none(not_none(urllib.parse.urlparse(repository.index_url)).hostname)
    registry_id = "private-repo"

    with tempfile.TemporaryDirectory() as tempdir, unittest.mock.patch.dict(
        os.environ,
        {"CARGO_HOME": tempdir},
    ):

        # Build the library and publish it to Artifactory.
        logger.info(
            "Publishing data/hello-world-lib to Cargo repository %r (%r)",
            repository.name,
            repository.index_url,
        )
        with kraken_project(kraken_ctx()) as project1:
            project1.directory = data_dir / "hello-world-lib"
            settings = cargo_settings(project1)
            settings.add_auth(repository_host, repository.user, repository.password)
            settings.add_registry(registry_id, repository.index_url)
            cargo_publish(project=project1, registry=registry_id, allow_dirty=True)
            kraken_execute(project1.context, ":cargoPublish")

        logger.info("Giving repository time to index (20s) ...")
        time.sleep(20)

        # Compile the application, expecting that it can consume from the freshly published library.
        logger.info(
            "Building data/hello-world-app which consumes hello-world-lib from Cargo repository %r (%r)",
            repository.name,
            repository.index_url,
        )
        with kraken_project(kraken_ctx()) as project2:
            project2.directory = data_dir / "hello-world-app"
            settings = cargo_settings(project2)
            settings.add_auth(repository_host, repository.user, repository.password)
            settings.add_registry(registry_id, repository.index_url)
            cargo_build(project=project2)
            kraken_execute(project2.context, ":cargoBuild")


ARTIFACTORY_VAR = "ARTIFACTORY_INTEGRATION_TEST_CREDENTIALS"
CLOUDSMITH_VAR = "CLOUDSMITH_INTEGRATION_TEST_CREDENTIALS"


@pytest.mark.skipif(ARTIFACTORY_VAR not in os.environ, reason=f"{ARTIFACTORY_VAR} is not set")
@pytest.mark.xfail(reason="Artifactory appears to have an issue correctly initializing a Cargo repository")
def test__artifactory_cargo_publish_and_consume() -> None:
    credentials = json.loads(os.environ[ARTIFACTORY_VAR])
    with create_cargo_repository_in_artifactory(credentials) as repository:
        publish_lib_and_build_app(repository)


@pytest.mark.skipif(CLOUDSMITH_VAR not in os.environ, reason=f"{CLOUDSMITH_VAR} is not set")
def test__cloudsmith_cargo_publish_and_consume() -> None:
    credentials = json.loads(os.environ[CLOUDSMITH_VAR])
    with create_cargo_repository_in_cloudsmith(credentials) as repository:
        publish_lib_and_build_app(repository)
