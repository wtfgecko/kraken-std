import subprocess as sp
from typing import List, Optional

from kraken.core import Project, Property, Task, TaskStatus


class CargoBuildTask(Task):
    """This task runs `cargo build` using the specified parameters. It will respect the authentication
    credentials configured in :attr:`CargoProjectSettings.auth`."""

    args: Property[List[str]]
    incremental: Property[Optional[bool]] = Property.default(None)

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.args.set([])

    def execute(self) -> TaskStatus:
        command = ["cargo", "build"]
        incremental = self.incremental.get()
        if incremental is not None:
            command.append(f"--incremental={str(bool(incremental)).lower()}")
        command += self.args.get()
        self.logger.info("%s", command)
        result = sp.call(command, cwd=self.project.directory)
        return TaskStatus.from_exit_code(command, result)
