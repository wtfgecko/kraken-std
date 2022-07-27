import logging
import subprocess as sp
from pathlib import Path
from typing import List

from kraken.core import Property, Task, TaskStatus

from ..config import CargoRegistry

logger = logging.getLogger(__name__)


class CargoPublishTask(Task):
    """Publish a Cargo crate."""

    #: Path to the Cargo configuration file (defaults to `.cargo/config.toml`).
    cargo_config_file: Property[Path] = Property.default(".cargo/config.toml")

    #: The registry to publish the package to.
    registry: Property[CargoRegistry]

    #: Additional arguments for the call to `cargo publish`.
    additional_args: Property[List[str]] = Property.default_factory(list)

    def execute(self) -> TaskStatus:
        registry = self.registry.get()
        if registry.publish_token is None:
            print(f'error: registry {registry.alias!r} missing a "publish_token"')
            return TaskStatus.failed()

        logger.info("Publishing crate to registry '%s' (%s)", registry.alias, registry.index)

        command = ["cargo", "publish", "--registry", registry.alias, "--token", registry.publish_token]
        command += self.additional_args.get()

        safe_command = command[:]
        safe_command[command.index(registry.publish_token)] = "[MASKED]"
        self.logger.info("%s", safe_command)

        result = sp.call(command, cwd=self.project.directory)
        return TaskStatus.from_exit_code(safe_command, result)
