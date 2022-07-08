import logging
import tempfile
import time
from pathlib import Path
from typing import Iterator

import httpx
import pytest
from kraken.core.project import Project
from kraken.core.utils import not_none
from kraken.testing import kraken_execute

from kraken.std.helm import helm_package, helm_push, helm_settings
from tests.utils.docker import DockerServiceManager, docker_service_manager  # noqa: F401

logger = logging.getLogger(__name__)

USER_NAME = "user"
USER_PASS = "user"
REGISTRY_PORT = 5000


@pytest.fixture
def oci_registry(docker_service_manager: DockerServiceManager) -> Iterator[str]:  # noqa: F811
    with tempfile.TemporaryDirectory() as tempdir:

        # Create a htpasswd file for the registry.
        logger.info("Generating htpasswd for OCI registry")
        htpasswd_content = not_none(
            docker_service_manager.run(
                "httpd:2",
                entrypoint="htpasswd",
                args=["-Bbn", USER_NAME, USER_PASS],
                capture_output=True,
            )
        )
        htpasswd = Path(tempdir) / "htpasswd"
        htpasswd.write_bytes(htpasswd_content)

        # Start the registry.
        logger.info("Starting OCI registry")
        docker_service_manager.run(
            "registry",
            detach=True,
            ports=[f"{REGISTRY_PORT}:5000"],
            volumes=[f"{htpasswd.absolute()}:/auth/htpasswd"],
            env={
                "REGISTRY_AUTH": "htpasswd",
                "REGISTRY_AUTH_HTPASSWD_REALM": "Registry Realm",
                "REGISTRY_AUTH_HTPASSWD_PATH": "/auth/htpasswd",
            },
        )

        time.sleep(0.5)
        yield f"localhost:{REGISTRY_PORT}"


def test__helm_push_to_oci_registry(kraken_project: Project, oci_registry: str) -> None:
    """This integration test publishes a Helm chart to a local registry and checks if after publishing it, the
    chart can be accessed via the registry."""

    helm_settings(kraken_project).add_auth(oci_registry, USER_NAME, USER_PASS, insecure=True)
    package = helm_package(chart_directory="data/example-chart")
    helm_push(chart_tarball=package.chart_tarball, registry=f"oci://{oci_registry}/example")
    kraken_execute(kraken_project.context, ":helmPush")
    response = httpx.get(f"http://{oci_registry}/v2/example/example-chart/tags/list", auth=(USER_NAME, USER_PASS))
    response.raise_for_status()
    tags = response.json()
    assert tags == {"name": "example/example-chart", "tags": ["0.1.0"]}
