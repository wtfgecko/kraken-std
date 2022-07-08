# kraken-std

[![Python application](https://github.com/kraken-build/kraken-std/actions/workflows/python-package.yml/badge.svg)](https://github.com/kraken-build/kraken-std/actions/workflows/python-package.yml)
[![PyPI version](https://badge.fury.io/py/kraken-std.svg)](https://badge.fury.io/py/kraken-std)

The Kraken standard library.

__Features__

* [Cargo](#cargo)
* [Docker](#docker)
* [Helm](#helm)

---

## Cargo

  [Rust]: https://www.rust-lang.org/
  [Cargo]: https://doc.rust-lang.org/cargo/
  [rust-lang/cargo#10592]: https://github.com/rust-lang/cargo/pull/10592

Build [Rust][] projects with [Cargo][].

__Features__

* Inject HTTP(S) Basic-auth credentials into Git clone and Cargo download requests in `cargo build` for
  compatibility with private registries (workaround until [rust-lang/cargo#10592][] is working and merged).

__Quickstart__

```py
# kraken.build.py
from kraken.std.cargo import cargo_build, cargo_settings

cargo_settings().add_auth("example.jfrog.io", "me@example.org", "api_token")

cargo_build()
```

---

## Docker

  [Kaniko]: https://github.com/GoogleContainerTools/kaniko
  [Buildx]: https://docs.docker.com/buildx/working-with-buildx/

Build and publish Docker images.

__Supported backends__

* [ ] Native Docker
* [ ] [Buildx][]
* [x] [Kaniko][]

__Quickstart__

```py
# kraken.build.py
from kraken.std.docker import build_docker_image

build_docker_image(
    name="buildDocker",
    dockerfile="docker/release.Dockerfile",
    tags=["kraken-example"],
    load=True,
)
```

---

## Helm

  [Helm]: https://helm.sh/

Package and publish [Helm][] charts to OCI or HTTP(S) registries.

__Quickstart__

```py
# kraken.build.py
from kraken.std.helm import helm_push, helm_package, helm_settings

helm_settings().add_auth("example.jfrog.io", "me@example.org", "api_token")
package = helm_package(chart_path="./my-helm-chart")
helm_push(chart_tarball=package.chart_tarball, registry="example.jfrog.io/helm-local", tag)
```
