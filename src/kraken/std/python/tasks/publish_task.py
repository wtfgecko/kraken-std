from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from kraken.core import Project, Property, Task, TaskResult
from twine.commands.upload import upload as twine_upload
from twine.settings import Settings as TwineSettings

from ..settings import python_settings


class PublishTask(Task):
    """Publishes Python distributions to one or more indexes using :mod:`twine`."""

    index_url: Property[str]
    index_credentials: Property[Optional[tuple[str, str]]] = Property.config(default=None)
    distributions: Property[List[Path]]

    def execute(self) -> TaskResult:
        credentials = self.index_credentials.get()
        settings = TwineSettings(
            repository_url=self.index_url.get(),
            username=credentials[0] if credentials else None,
            password=credentials[1] if credentials else None,
        )
        twine_upload(settings, list(map(str, self.distributions.get())))
        return TaskResult.SUCCEEDED


def publish(
    *,
    package_index: str,
    distributions: list[Path] | Property[List[Path]],
    name: str = "publishPython",
    group: str | None = "publish",
    default: bool = False,
    project: Project | None = None,
) -> PublishTask:
    """Create a publish task for the specified registry."""

    project = project or Project.current()
    settings = python_settings(project)
    if package_index not in settings.package_indexes:
        raise ValueError(f"package index {package_index!r} is not defined")

    index = settings.package_indexes[package_index]
    return project.do(
        name,
        PublishTask,
        default=default,
        group=group,
        index_url=index.url,
        index_credentials=index.credentials,
        distributions=distributions,
    )
