# kraken-std

[![Python application](https://github.com/kraken-build/kraken-std/actions/workflows/python-package.yml/badge.svg)](https://github.com/kraken-build/kraken-std/actions/workflows/python-package.yml)
[![PyPI version](https://badge.fury.io/py/kraken-std.svg)](https://badge.fury.io/py/kraken-std)

The Kraken standard library.

---

## Development

### Integration testing

Integration tests are located in `src/tests/integration`. The following tools need to be available to run the
integration tests:

* Cargo (to test Cargo building and publishing) *The Cargo integration tests run against Artifactory and Cloudsmith
and requires credentials to temporarily create a new Cargo repository (available in CI).*
* Docker (used to setup services that we run integration tests against)
* Helm (to test Helm packaging and publishing)
* Poetry (to test Python publishing and installing)
* [Slap](https://github.com/python-slap/slap-cli) (to test Python publishing and installing)

__Test a single integration test__

    ```
    PYTEST_FLAGS="--log-cli-level DEBUG -s -k <test_filter>" kraken run pytestIntegration -v
    ```
