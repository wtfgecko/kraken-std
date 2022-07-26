""" Tools for Git versioned projects. """

from __future__ import annotations

from .tasks.gitignore_sync_task import GitignoreSyncTask
from .version import GitVersion, git_describe

__all__ = [
    "git_describe",
    "GitVersion",
    "GitignoreSyncTask",
]
