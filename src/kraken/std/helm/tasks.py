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
    """Packages a Helm chart."""

    # The path to the directory that contains the Helm chart. A relative path is treated relative to
    # the project directory. This property must be set.
    chart_directory: Property[Path]

    # This property specifies the path to the output Helm chart tarball. It can be specified, when the
    # task is created if an explicit output location is desired, otherwise the property will be set
    # when the task was executed and the default output location is in the build directory.
    chart_tarball: Property[Path] = output()

    def execute(self) -> TaskResult:
        chart_directory = self.project.directory / self.chart_directory.get()
        if self.chart_tarball.is_filled():
            status, output_file = helmapi.helm_package(chart_directory, output_file=self.chart_tarball.get())
        else:
            output_directory = self.project.build_directory / "helm" / self.name
            status, output_file = helmapi.helm_package(chart_directory, output_directory=output_directory)
            if output_file:
                self.chart_tarball.set(output_file)
        if status != 0 or not output_file:
            return TaskResult.FAILED
        return TaskResult.SUCCEEDED


class HelmPushTask(Task):
    """Pushes a Helm chart to a Helm registry.

    !!! warning

        The current implementation uses a manual authenticated HTTP `POST` call to the :attr:`chart_url`. The
        chart URL is derived as a concatenation of the :attr:`registry_url` and the :attr:`chart_name` or
        the :attr:`chart_tarball` base name.

        In a future version, we may also support invoking the `helm push` command.
    """

    # The path to the Helm chart package file.
    chart_tarball: Property[Path]

    # The base URL to push the Helm chart file to. This can currently be omitted if :attr:`chart_url` is specified.
    registry_url: Property[str]

    # The filename of the Helm chart under the :attr:`registry_url`. This can be omitted if the :attr:`chart_url`
    # is specified explicitly, otherwise it will be used to construct the URL. If it is not set, it will fall back
    # to the base name of the :attr:`chart_tarball`.
    chart_name: Property[str]

    # The username and password to use.
    username: Property[str]
    password: Property[str]

    # The final constructed chart URL that the chart will be published under.
    chart_url: Property[str] = output()

    def finalize(self) -> None:
        self.chart_name.setdefault(Supplier.of_callable((lambda: self.chart_tarball.get().name), [self.chart_tarball]))
        self.chart_url.setdefault(
            Supplier.of_callable(
                (lambda: urllib.parse.urljoin(self.registry_url.get() + "/", self.chart_name.get())),
                [self.registry_url, self.chart_name],
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
