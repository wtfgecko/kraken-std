from __future__ import annotations

import subprocess as sp
from typing import Optional

from kraken.core import Property, Task, TaskStatus


class CargoClippyTask(Task):
    """Runs `cargo clippy` for linting or applying suggestions."""

    fix: Property[bool] = Property.default(False)
    allow: Property[Optional[str]] = Property.default("staged")

    def execute(self) -> TaskStatus | None:
        command = ["cargo", "clippy"]
        if self.fix.get():
            command += ["--fix"]
            allow = self.allow.get()
            if allow == "staged":
                command += ["--allow-staged"]
            elif allow == "dirty":
                command += ["--allow-dirty"]
            elif allow is not None:
                raise ValueError(f"invalid allow: {allow!r}")
        return TaskStatus.from_exit_code(command, sp.call(command, cwd=self.project.directory))
