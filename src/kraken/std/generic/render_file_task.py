from __future__ import annotations

from pathlib import Path

from kraken.core import Project, Property, Task, TaskStatus

DEFAULT_ENCODING = "utf-8"


class RenderFileTask(Task):
    file: Property[Path]
    encoding: Property[str]
    content: Property[str]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.encoding.setdefault(DEFAULT_ENCODING)
        self._content_cache: bytes | None = None

    def get_file_contents(self, file: Path) -> str | bytes:
        return self.content.get()

    def finalize(self) -> None:
        self.file.set(self.file.value.map(lambda p: self.project.directory / p))
        super().finalize()

    def prepare(self) -> TaskStatus | None:
        file = self.file.get()

        # Materialize the file contents.
        content = self.get_file_contents(file)
        if isinstance(content, str):
            self._content_cache = content.encode(self.encoding.get())
        else:
            self._content_cache = content

        # Check if we would be updating the file.
        if file.is_file() and file.read_bytes() == self._content_cache:
            return TaskStatus.up_to_date()

        return TaskStatus.pending()

    def execute(self) -> TaskStatus:
        assert self._content_cache is not None
        file = self.file.get()
        file.parent.mkdir(exist_ok=True)
        file.write_bytes(self._content_cache)
        return TaskStatus.succeeded(f"write {len(self._content_cache)} bytes to {file}")
