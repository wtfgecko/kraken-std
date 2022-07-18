# Cargo

  [Rust]: https://www.rust-lang.org/
  [Cargo]: https://doc.rust-lang.org/cargo/
  [rust-lang/cargo#10592]: https://github.com/rust-lang/cargo/pull/10592

Build [Rust][] projects with [Cargo][].

__Features__

* Inject HTTP(S) Basic-auth credentials into Git clone and Cargo download requests in `cargo build` for
  compatibility with private registries (workaround until [rust-lang/cargo#10592][] is working and merged).

__Quickstart__

```py
# .kraken.py
from kraken.api import project
from kraken.std.cargo import CargoBuildTask, CargoPublishTask, cargo_settings

settings = cargo_settings()
settings.add_auth("example.jfrog.io", "me@example.org", "<API_TOKEN>")
settings.add_registry(
    "private-repo",
    "https://example.jfrog.io/artifactory/git/default-cargo-local.git",
    publish_token="Bearer ${PASSWORD}",
)

project.do("cargoBuild", CargoBuldTask)
project.do("cargoPublish", CargoPublishTask, registry="private-repo")
```

> __Note__
>
> * The registry URL configured in the Kraken build script is currently written only temporarily into the
>   `.cargo/config.toml` configuration file. In a future version, we may permanently write it into the file to keep
>   it synchronized or instead pick up the configured registries by reading the configuration file instead.

__Integration tests__

The `cargo_publish()` and `cargo_build()` tasks are continuously integration tested against JFrog Artifactory
and Cloudsmith.

## API Documentation

@pydoc kraken.std.cargo.CargoProjectSettings

@pydoc kraken.std.cargo.cargo_settings

@pydoc kraken.std.cargo.CargoBuildTask

@pydoc kraken.std.cargo.CargoPublishTask
