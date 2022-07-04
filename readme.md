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
import os
from kraken.std import docker

docker.build(
    dockerfile="docker/release.Dockerfile",
    secrets={
        "USERNAME": os.environ["USERNAME"],
        "PASSWORD": os.environ["PASSWORD"],
    },
    tags=["my-project:latest"],
    push_to_registry=["example.jfrog.io/docker-release"],
    backend="kaniko",
)
```
