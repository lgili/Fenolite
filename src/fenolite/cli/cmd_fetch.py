# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite fetch NAME``: install one external tool of the table after checking its size and its SHA-256
(capability cli-contract, "Fetch command"; ADR-0007; change c0078).

The command plans one deferred write and obtains nothing itself: the dispatcher calls the source only with
``--confirm``, so ``--dry-run`` and the refusal of exit 4 open no connection and read no ``--from`` file.
It is the only command that downloads a tool, and it sends no design data.
"""

from __future__ import annotations

import argparse
import http.client
from collections.abc import Callable
from pathlib import Path

from fenolite.cli import fetch
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.core.tools import tool_path

KIND = "tool"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name", nargs="?", metavar="NAME", help="the tool to install (freerouting)")
    parser.add_argument("--from", dest="from_", metavar="FILE",
                        help="install this copy instead of downloading; checked the same way")  # fmt: skip
    parser.add_argument("--dir", dest="dir", metavar="DIR",
                        help="install into DIR instead of the tools folder (FENOLITE_TOOLS_DIR)")  # fmt: skip


def _row(name: str | None) -> fetch.FetchRow:
    table = fetch.rows()
    if name is None or name not in table:
        known = ", ".join(fetch.public_names()) or "none"
        said = "no tool was named" if name is None else f"unknown tool {name!r}"
        raise CliError("FEN-2001", said, hint=f"tools that can be fetched: {known}", where="NAME")
    return table[name]


def _destination(row: fetch.FetchRow, folder: str | None) -> Path:
    if folder:
        return Path(folder) / row.file
    try:
        return tool_path(row.name, row.file)
    except ValueError as exc:
        raise CliError(
            "FEN-2001", str(exc), hint="set it to an absolute folder, or pass --dir DIR", where="--dir"
        ) from exc


def _installed(row: fetch.FetchRow, path: Path) -> bool:
    """Whether ``path`` already holds the pinned bytes; a file of another size is not read."""
    try:
        return path.is_file() and path.stat().st_size == row.bytes and fetch.matches(row, path.read_bytes())
    except OSError:
        return False


def _source(row: fetch.FetchRow, given: Path | None) -> Callable[[], bytes]:
    """What the dispatcher calls with ``--confirm``: the file of ``--from``, the packaged file, or the one
    request of the command."""
    if given is not None:
        return lambda: fetch.read_file(row, given)
    if row.packaged:
        return lambda: fetch.read_package(row)

    def network() -> bytes:
        try:
            return fetch.download(row)
        except (OSError, ValueError, http.client.HTTPException) as exc:
            raise CliError("FEN-6003", f"download of {row.url} failed: {exc}", where=row.name) from exc

    return network


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    row = _row(args.name)
    destination = _destination(row, args.dir)
    target = ctx.cwd / destination
    given = (ctx.cwd / args.from_) if args.from_ else None
    installed = _installed(row, target)
    origin = "file" if given is not None else "package" if row.packaged else "network"
    result: dict[str, object] = {
        "name": row.name,
        "version": row.version,
        "file": row.file,
        "path": destination.as_posix(),
        "bytes": row.bytes,
        "sha256": row.sha256,
        "url": row.url,
        "licence": row.licence,
        "origin": origin,
        "installed": installed,
        "needs": list(row.needs),
        "env": {row.env: str(target)} if args.dir and row.env else {},
    }
    writes: tuple[PlannedWrite, ...] = ()
    if not installed:
        writes = (
            PlannedWrite(
                path=destination.as_posix(),
                data=b"",
                kind=KIND,
                source=_source(row, given),
                size=row.bytes,
                sha256=row.sha256,
            ),
        )
    return Result(result=result, writes=writes, depends=depends_on(ctx.cwd, given))


COMMAND = Command(
    name="fetch",
    help="download an external tool (freerouting) after --confirm, checked against its pinned SHA-256",
    mutates=True,
    register=_register,
    run=_run,
    example_args=("_selftest", "--dir", "tools", "--dry-run"),
    mutation_example_args=("_selftest", "--dir", "tools"),
)
