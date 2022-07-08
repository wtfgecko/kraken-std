""" Implements a MITM proxy server using the :mod:`proxy` (`proxy.py` on PyPI) module to inject the auth credentials
into Cargo and Git HTTP(S) requests. """

from __future__ import annotations

import base64
import contextlib
import json
import logging
import os
import subprocess as sp
import sys
from pathlib import Path
from typing import Iterator, Optional

from kraken.core.utils import not_none
from proxy.http.parser import HttpParser
from proxy.http.proxy.plugin import HttpProxyBasePlugin

logger = logging.getLogger(__name__)


class AuthInjector(HttpProxyBasePlugin):
    """This proxy.py plugin injects credentials according to the `INJECT_AUTH` environment variable."""

    # TODO (@NiklasRosenstein): Find a better way than environment variables to pass configuration to this plugin.

    _auth: dict[str, tuple[str, str]] | None = None

    @property
    def auth(self) -> dict[str, tuple[str, str]]:
        if self._auth is None:
            self._auth = json.loads(os.environ["INJECT_AUTH"])
        return self._auth

    def handle_client_request(self, request: HttpParser) -> Optional[HttpParser]:

        # NOTE (@NiklasRosenstein): This method is only called for requests in an HTTPS tunnel if TLS
        #       interception is enabled, which requires a self-signed CA-certificate.

        host = not_none(request.headers)[b"host"][1].partition(b":")[0].decode()
        # path = request.path.decode() if request.path else None

        # if path and ('http://' not in path or 'https://' not in path):
        #     # For the proxied HTTPS requests, it appears that we only get the path instead of the full URL in
        #     # the request path, so we make sure we
        #     new_url = f'https://{host}{path}'
        #     request.set_url(new_url.encode())

        if host in self.auth and not request.has_header(b"Authorization"):
            logger.info("injecting Authorization for %s request to %s", not_none(request.method).decode(), host)
            creds = self.auth[host]
            auth = base64.b64encode(f"{creds[0]}:{creds[1]}".encode())
            request.add_header(b"Authorization", b"Basic " + auth)

        return request


@contextlib.contextmanager
def mitm_auth_proxy(
    auth: dict[str, tuple[str, str]],
    certs_dir: Path,
    port: int = 8899,
) -> Iterator[tuple[str, Path]]:
    """Runs a MITM HTTPS proxy that injects credentials according to *auth* into requests."""

    certs_dir = Path(__file__).parent / "data" / "certs"
    key_file = certs_dir / "key.pem"
    cert_file = certs_dir / "cert.pem"

    command = [
        sys.executable,
        "-m",
        "proxy",
        "--plugins",
        __name__ + "." + AuthInjector.__name__,
        "--ca-key-file",
        str(key_file),
        "--ca-cert-file",
        str(cert_file),
        "--ca-signing-key",
        str(key_file),
        "--port",
        str(port),
    ]

    env = os.environ.copy()
    env["INJECT_AUTH"] = json.dumps(auth)

    if os.getenv("KRAKEN_CARGO_MITM_DEBUG") in ("1", "true"):
        stdout, stderr = None, None
    else:
        stdout, stderr = sp.DEVNULL, sp.DEVNULL

    logger.info("starting proxy server: %s", command)
    proc = sp.Popen(command, env=env, stdout=stdout, stderr=stderr)

    try:
        yield f"http://localhost:{port}", cert_file
    finally:
        logger.info("stopping proxy server")
        proc.terminate()
        proc.wait()
        if proc.returncode is None:
            proc.kill()
            proc.wait()
