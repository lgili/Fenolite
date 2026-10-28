# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite mcp``: the MCP server on standard input and output (capability cli-contract, "MCP command";
capability mcp-server; ``docs/mcp.md``).

While it serves, standard output belongs to the protocol: the command leaves through ``SystemExit`` when its
input ends, so that the dispatcher writes no envelope after the last message. ``--list`` serves nothing and
returns, as an ordinary envelope, the versions, tools and resources the server would offer.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, BinaryIO, cast

from fenolite import __version__
from fenolite.cli.api import Command, Context, Result, discover
from fenolite.cli.errors import CliError
from fenolite.mcp.backend import FenoliteBackend
from fenolite.mcp.protocol import LEGACY, MODERN, Server
from fenolite.mcp.tools import INSTRUCTIONS

HELP = "serve Fenolite's commands as tools to an MCP client on standard input and output"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/mcp.md."
    parser.add_argument(
        "--root", metavar="DIR", default=".", help="the folder every call runs in and writes under"
    )
    parser.add_argument("--read-only", action="store_true", help="list only the commands that write nothing")
    parser.add_argument("--tools", metavar="NAME,...", default=None, help="list only these commands")
    parser.add_argument("--timeout", type=float, default=600.0, metavar="SECONDS", help="stop a longer call")
    parser.add_argument("--list", action="store_true", help="return the tools and resources; serve nothing")
    parser.add_argument(
        "--allow-edit",
        action="store_true",
        help="also serve fenolite_edit: a client that edits a design script and builds it runs code as you",
    )


def _backend(args: argparse.Namespace) -> FenoliteBackend:
    root = Path(str(args.root))
    if not root.is_dir():
        raise CliError("FEN-2001", f"--root: {args.root!r} is not a folder", where="--root")
    if not args.timeout > 0:
        raise CliError(
            "FEN-2001", f"--timeout: expected seconds above 0, got {args.timeout:g}", where="--timeout"
        )
    only = (
        None if args.tools is None else [name.strip() for name in str(args.tools).split(",") if name.strip()]
    )
    try:
        return FenoliteBackend(
            discover(),
            root=root,
            timeout=float(args.timeout),
            read_only=bool(args.read_only),
            only=only,
            allow_edit=bool(args.allow_edit),
        )
    except KeyError as exc:
        name = str(exc.args[0])
        raise CliError(
            "FEN-2001", f"--tools: no command {name!r} is served", where="--tools",
            hint="name public commands of 'fenolite capabilities', but mcp and skill",
        ) from None  # fmt: skip


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    backend = _backend(args)
    if args.list:
        result: dict[str, Any] = {
            "versions": [MODERN, *LEGACY],
            "root": str(backend.root),
            "tools": [d["name"] for d in backend.tools()],
            "resources": [r["uri"] for r in backend.resources()],
        }
        return Result(result=result)
    out = cast("BinaryIO", sys.stdout.buffer)
    server = Server(backend, name="fenolite", version=__version__, instructions=INSTRUCTIONS, out=out)
    raise SystemExit(server.serve(cast("BinaryIO", sys.stdin.buffer)))


COMMAND = Command(
    name="mcp",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    example_args=("--list", "--read-only"),
    discovery=(("protocol_versions", (MODERN, *LEGACY)),),
)
