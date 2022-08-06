from __future__ import annotations

from pathlib import Path

from kraken.core import Project, Property, Supplier, Task, TaskStatus
from termcolor import colored

DEFAULT_ENCODING = "utf-8"


class RenderFileTask(Task):
    """A base class for tasks that produce a single file. You can either pass the :attr:`content` property for the
    file contents or implement a subclass that overrides the :meth:`get_file_contents` method.

    By default, the task will create a separate task on :meth:`finalize` that checks if the contents of the generated
    file are up to date, and error if not. This task is registered to the default `"lint"` group."""

    description = 'Create or update "%(file)s".'
    file: Property[Path]
    encoding: Property[str]
    content: Property[str]

    def __init__(self, name: str, project: Project) -> None:
        super().__init__(name, project)
        self.encoding.setdefault(DEFAULT_ENCODING)
        self._content_cache: bytes | None = None

    def make_check_task(
        self,
        name: str | None = None,
        group: str = "lint",
        default: bool = False,
        description: str | None = None,
    ) -> CheckFileContentsTask:
        task = self.project.do(
            name or (self.name + ".check"),
            CheckFileContentsTask,
            default=default,
            group=group,
            # Intentionally break automatic dependency recognition, the two tasks need to be independent.
            file=Supplier.of_callable(lambda: self.file.get()),
            content=Supplier.of_callable(lambda: self.__get_file_contents_cached()),
            update_task=self.path,
        )
        task.description = description or 'Check if "%(file)s" is up to date.'
        # Ensure that the render task comes before the check task if both were to run in the same build.
        task.add_relationship(self, strict=False)
        return task

    def get_file_contents(self, file: Path) -> str | bytes:
        """Can be overwritten by subclasses. THe default implementation returns the :attr:`content` property value."""
        return self.content.get()

    def __get_file_contents_cached(self) -> bytes:
        file = self.file.get()
        # Materialize the file contents.
        content = self.get_file_contents(file)
        if isinstance(content, str):
            self._content_cache = content.encode(self.encoding.get())
        else:
            self._content_cache = content
        return self._content_cache

    # Task

    def finalize(self) -> None:
        self.file.setmap(lambda path: self.project.directory / path)
        super().finalize()

    def prepare(self) -> TaskStatus | None:
        file = self.file.get()

        # Check if we would be updating the file.
        if file.is_file() and file.read_bytes() == self.__get_file_contents_cached():
            return TaskStatus.up_to_date()

        return TaskStatus.pending()

    def execute(self) -> TaskStatus:
        file = self.file.get()
        file.parent.mkdir(exist_ok=True)
        file.write_bytes(self.__get_file_contents_cached())
        return TaskStatus.succeeded(f"write {len(self.__get_file_contents_cached())} bytes to {file}")


class CheckFileContentsTask(Task):
    file: Property[Path]
    content: Property[bytes]
    update_task: Property[str]

    def execute(self) -> TaskStatus | None:
        file = self.file.get()
        try:
            file = file.relative_to(Path.cwd())
        except ValueError:
            pass
        file_fmt = colored(str(file), "yellow", attrs=["bold"])
        uptask = colored(self.update_task.get(), "blue", attrs=["bold"])
        if not file.exists():
            return TaskStatus.failed(f'file "{file_fmt}" does not exist, run {uptask} to generate it')
        if not file.is_file():
            return TaskStatus.failed(f'"{file}" is not a file')
        if file.read_bytes() != self.content.get():
            return TaskStatus.failed(f'file "{file_fmt}" is not up to date, run {uptask} to update it')
        return None
