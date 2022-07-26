from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import tomli
import tomli_w
from kraken.core import Property, Task, TaskRelationship

from kraken.std.generic.render_file_task import RenderFileTask

from ..config import CargoRegistry


class CargoSyncConfigTask(RenderFileTask):
    """This task updates the `.cargo/config.toml` file to inject configuration values."""

    # Override the default value of the :attr:`RenderFileTask.file`.
    file: Property[Path] = Property.default(".cargo/config.toml")

    #: If enabled, the configuration file will be replaced rather than updated.
    replace: Property[bool] = Property.config(default=False)

    #: The registries to insert into the configuration.
    registries: Property[List[CargoRegistry]] = Property.config(default_factory=list)

    #: Tasks that are dependant on this task.
    for_tasks: Property[List[Task]] = Property.default_factory(list)

    # RenderFileTask

    def get_file_contents(self, file: Path) -> str | bytes:
        content = tomli.loads(file.read_text()) if not self.replace.get() and file.exists() else {}
        for registry in self.registries.get():
            content.setdefault("registries", {})[registry.alias] = {"index": registry.index}
        lines = []
        if self.replace.get():
            lines.append("# This file is managed by Kraken. Manual edits to this file will be overwritten.")
        else:
            lines.append(
                "# This file is partially managed by Kraken. Comments and manually added "
                "repositories are not preserved."
            )
        lines.append(tomli_w.dumps(content))
        return "\n".join(lines)

    # Task

    def get_relationships(self) -> Iterable[TaskRelationship]:
        yield from super().get_relationships()
        for task in self.for_tasks.get():
            yield TaskRelationship(task, True, True)
