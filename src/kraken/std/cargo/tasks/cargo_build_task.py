import subprocess as sp
from typing import List

from kraken.core import Project, Property, Task, TaskStatus


class CargoBuildTask(Task):
    """This task runs `cargo build` using the specified parameters. It will respect the authentication
    credentials configured in :attr:`CargoProjectSettings.auth`."""

    args: Property[List[str]]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.args.set([])

    def execute(self) -> TaskStatus:
        command = ["cargo", "build"] + self.args.get()
        self.logger.info("%s", command)
        result = sp.call(command, cwd=self.project.directory)
        return TaskStatus.from_exit_code(command, result)
