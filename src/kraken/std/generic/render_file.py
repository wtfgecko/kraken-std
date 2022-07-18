from __future__ import annotations

from pathlib import Path
from typing import Callable, Union

from kraken.core import Project, Property, Task, TaskResult

DEFAULT_ENCODING = "utf-8"


class RenderFileTask(Task):
    content: Property[Union[str, Callable[[], str]]]
    file: Property[Path]
    encoding: Property[str]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.encoding.setdefault(DEFAULT_ENCODING)

    def _get_content(self) -> str:
        content = self.content.get()
        if callable(content):
            content = content()
        return content

    def finalize(self) -> None:
        # Materialize content that is to be rendered.
        content = self._get_content()
        self.content.setfinal(content)
        return super().finalize()

    def is_up_to_date(self) -> bool:
        content = self._get_content()
        return self.file.get().is_file() and self.file.get().read_text(self.encoding.get()) == content

    def execute(self) -> TaskResult:
        content = self._get_content()
        self.file.get().parent.mkdir(exist_ok=True)
        encoded = content.encode(self.encoding.get())
        print(f"write {self.file} ({len(encoded)} bytes)")
        self.file.get().write_bytes(encoded)
        return TaskResult.SUCCEEDED
