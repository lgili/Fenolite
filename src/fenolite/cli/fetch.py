# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The table of external tools that ``fenolite fetch`` installs, and how their bytes are obtained
(capability cli-contract, "Fetch command"; ADR-0007; change c0078).

``download`` is the only code of Fenolite that opens a network connection for a tool. It is called by the
dispatcher, through a deferred write, and therefore only with ``--confirm``. It sends the address of the
row and one ``User-Agent`` header: no parameter, no identifier and no design data. What it returns is
checked against the row's size and SHA-256 before anything is written.
"""

from __future__ import annotations

import http.client
import tomllib
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from importlib import resources
from pathlib import Path
from typing import IO, Any, cast

from fenolite import __version__
from fenolite.cli.errors import CliError
from fenolite.core.io import sha256_bytes

TABLE = "fetch.toml"
PACKAGE_URL = "package:"
"""The address of a row whose file is packaged with Fenolite, beside the table."""
HIDDEN_PREFIX = "_"
TIMEOUT_S = 60
SCHEME = "https://"
KEYS = ("name", "version", "file", "bytes", "sha256", "url", "licence", "source", "env", "needs")


@dataclass(frozen=True, slots=True)
class FetchRow:
    """One tool of the table: what is installed, from where, and what its bytes must be."""

    name: str
    version: str
    file: str
    bytes: int
    sha256: str
    url: str
    licence: str
    source: str
    """The id of ``docs/evidence/sources.md`` that records the address; empty for a hidden row."""
    env: str
    """The variable a user may set to the file instead; empty when the tool has none."""
    needs: tuple[str, ...]
    """What the tool needs and this command does not install."""

    @property
    def hidden(self) -> bool:
        return self.name.startswith(HIDDEN_PREFIX)

    @property
    def packaged(self) -> bool:
        return self.url == PACKAGE_URL


def _row(table: Mapping[str, Any]) -> FetchRow:
    missing = [key for key in KEYS if key not in table]
    if missing or set(table) - set(KEYS):
        raise ValueError(f"{TABLE}: a row holds exactly the keys {', '.join(KEYS)}")
    return FetchRow(
        name=str(table["name"]),
        version=str(table["version"]),
        file=str(table["file"]),
        bytes=int(table["bytes"]),
        sha256=str(table["sha256"]),
        url=str(table["url"]),
        licence=str(table["licence"]),
        source=str(table["source"]),
        env=str(table["env"]),
        needs=tuple(str(item) for item in cast(list[object], table["needs"])),
    )


@cache
def rows() -> Mapping[str, FetchRow]:
    """Every row of the table by name, the hidden ones included, in the table's order."""
    text = resources.files("fenolite.cli").joinpath("data", TABLE).read_text(encoding="utf-8")
    found: dict[str, FetchRow] = {}
    for table in cast(list[dict[str, Any]], tomllib.loads(text).get("tool", [])):
        row = _row(table)
        if row.name in found:
            raise ValueError(f"{TABLE}: the row {row.name!r} is given twice")
        found[row.name] = row
    return found


def public_names() -> tuple[str, ...]:
    """The names a hint or a page may show, sorted."""
    return tuple(sorted(name for name, row in rows().items() if not row.hidden))


def matches(row: FetchRow, data: bytes) -> bool:
    """Whether ``data`` has the size and the SHA-256 of ``row``."""
    return len(data) == row.bytes and sha256_bytes(data) == row.sha256


class _HttpsOnly(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to an ``https`` address."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: http.client.HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        if not newurl.lower().startswith(SCHEME):
            raise urllib.error.URLError(f"redirect to an address that is not https refused: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener() -> urllib.request.OpenerDirector:
    """The opener of ``urllib.request`` with its usual handlers (the proxies of the environment, verified
    TLS) and the redirect rule above."""
    return urllib.request.build_opener(_HttpsOnly)


def download(row: FetchRow) -> bytes:
    """The bytes at the row's address, at most ``row.bytes + 1`` of them. One request, with the header
    ``User-Agent: fenolite/<version>`` and a timeout of 60 s; no retry. A failure raises ``OSError`` (as
    ``urllib`` does) or ``ValueError``; the caller turns it into ``FEN-6003``."""
    if not row.url.lower().startswith(SCHEME) or "?" in row.url:
        raise ValueError(f"the address of {row.name!r} is not a plain https address: {row.url}")
    request = urllib.request.Request(row.url, headers={"User-Agent": f"fenolite/{__version__}"})
    with _opener().open(request, timeout=TIMEOUT_S) as response:
        return cast(bytes, response.read(row.bytes + 1))


def read_package(row: FetchRow) -> bytes:
    """The bytes of a packaged row: the file ``row.file`` beside the table."""
    return resources.files("fenolite.cli").joinpath("data", row.file).read_bytes()


def read_file(row: FetchRow, path: Path) -> bytes:
    """The bytes of a copy the user already has, at most ``row.bytes + 1`` of them. A missing or
    unreadable file is ``FEN-3001``."""
    try:
        with path.open("rb") as handle:
            return handle.read(row.bytes + 1)
    except OSError as exc:
        raise CliError("FEN-3001", f"cannot read {path}: {exc.strerror or exc}", where=str(path)) from exc


__all__ = [
    "PACKAGE_URL",
    "TIMEOUT_S",
    "FetchRow",
    "download",
    "matches",
    "public_names",
    "read_file",
    "read_package",
    "rows",
]
