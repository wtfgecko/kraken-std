from __future__ import annotations

from pathlib import Path
from typing import Callable, Union

from kraken.core import Project, Property, Task, TaskStatus

DEFAULT_ENCODING = "utf-8"


class RenderFileTask(Task):
    content: Property[Union[str, Callable[[], str]]]
    file: Property[Path]
    encoding: Property[str]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.encoding.setdefault(DEFAULT_ENCODING)
        self._content_cache: str | None = None

    def _get_content(self) -> str:
        if self._content_cache is None:
            content = self.content.get()
            if callable(content):
                content = content()
            self._content_cache = content
        return self._content_cache

    def prepare(self) -> TaskStatus | None:
        content = self._get_content()
        if self.file.get().is_file() and self.file.get().read_text(self.encoding.get()) == content:
            return TaskStatus.up_to_date("content has not changed")
        return TaskStatus.pending()

    def execute(self) -> None:
        content = self._get_content()
        self.file.get().parent.mkdir(exist_ok=True)
        encoded = content.encode(self.encoding.get())
        print(f"write {self.file.get()} ({len(encoded)} bytes)")
        self.file.get().write_bytes(encoded)
