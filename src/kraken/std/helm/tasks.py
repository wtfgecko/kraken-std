from __future__ import annotations

import urllib.parse
from pathlib import Path

import httpx
from kraken.core.property import Property, output
from kraken.core.supplier import Supplier
from kraken.core.task import Task, TaskResult, task_factory

from . import helmapi

# from kraken.core.utils import not_none


class HelmPackageTask(Task):

    # Path to the Helm chart directory to package.
    chart_path: Property[Path]

    # Path to the packaged Helm chart. Only available after the action was executed.
    output_file: Property[Path] = output()

    def execute(self) -> TaskResult:
        output_directory = self.project.build_directory / "helm"
        status, output_file = helmapi.helm_package(self.chart_path.get(), output_directory=output_directory)
        if status != 0 or not output_file:
            return TaskResult.FAILED
        self.output_file.set(output_file)
        return TaskResult.SUCCEEDED


class HelmPushTask(Task):

    # Path to the packaged chart file to publish.
    chart_tarball: Property[Path]

    # The Helm registry URL to push to.
    registry_url: Property[str]

    # The filename of the chart in the registry. If omitted, the name of the :attr:`chart_tarball` is used.
    chart_name: Property[str]

    # The username and password to use.
    username: Property[str]
    password: Property[str]

    # The final constructed chart URL that the chart will be published under.
    chart_url: Property[str] = output()

    def finalize(self) -> None:
        self.chart_url.set(
            Supplier.of_callable(
                lambda: urllib.parse.urljoin(
                    self.registry_url.get() + "/", self.chart_name.get_or(self.chart_tarball.get().name)
                )
            )
        )
        return super().finalize()

    def execute(self) -> TaskResult:
        # NOTE (@NiklasRosenstein): This is currently geared to pushing to Artifactory Helm repositories.
        #       We could make it use "helm registry login" and "helm push" instead.

        # if self.username.is_filled() and self.password.is_filled():
        #     # TODO (@NiklasRosenstein): Check if authentication is actually needed.
        #     host = not_none(urllib.parse.urlparse(self.registry_url.get()).hostname)
        #     result = helmapi.helm_registry_login(host, self.username.get(), self.password.get())
        #     if result != 0:
        #         return TaskResult.FAILED

        # result = helmapi.helm_push(self.chart_tarball.get(), self.registry_url.get())
        # if result != 0:
        #     return TaskResult.FAILED

        # return TaskResult.SUCCEEDED

        auth: tuple[str, str] | None = None
        if self.username.is_filled() and self.password.is_filled():
            auth = (self.username.get(), self.password.get())

        response = httpx.put(self.chart_url.get(), content=self.chart_tarball.get().read_bytes(), auth=auth)
        response.raise_for_status()
        print("Published to", self.chart_url.get())

        return TaskResult.SUCCEEDED


helm_package = task_factory(HelmPackageTask)
helm_push = task_factory(HelmPushTask, default=False, capture=False)
