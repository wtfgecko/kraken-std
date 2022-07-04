# kraken-std

The Kraken standard library.

__Features__

* [Docker](#docker)

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
from kraken.std import docker

docker.build(
    name="buildDocker",
    dockerfile=dockerfile.action.file,
    dependencies=[dockerfile],
    tags=["kraken-example"],
    load=True,
)
```
