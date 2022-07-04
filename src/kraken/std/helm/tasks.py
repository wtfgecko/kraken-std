from __future__ import annotations

import dataclasses
from pathlib import Path

from kraken.core.action import Action, ActionResult
from kraken.core.property import Property
from kraken.core.task import AnyTask, Task

from . import cliwrapper


@dataclasses.dataclass
class HelmPackageAction(Action):

    # Path to the Helm chart directory to package.
    chart_path: Path

    # Path to the packaged Helm chart. Only available after the action was executed.
    output_file: Property[Path] = Property()

    def __post_init__(self) -> None:
        super().__init__()

    def execute(self) -> ActionResult:
        status, output_file = cliwrapper.helm_package(self.chart_path, output_directory=self.task.get().build_directory)
        if status != 0 or not output_file:
            return ActionResult.FAILED
        self.output_file.set(output_file)
        return ActionResult.SUCCEEDED


def helm_package(
    name: str,
    chart_path: Path | str,
    dependencies: list[str | AnyTask] | None = None,
) -> Task[HelmPackageAction]:
    from kraken.api import project

    return project.do(
        name=name,
        action=HelmPackageAction(project.to_path(chart_path)),
        dependencies=dependencies or [],
    )
