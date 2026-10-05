# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Hidden ``_echo`` command: exercises every branch of the CLI contract for the consistency tests."""

from __future__ import annotations

import argparse
import uuid
from typing import Any

from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.output import Issue


def _register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--issue", action="append", choices=["error", "warning", "info"], default=[],
                        help="emit an issue of this severity (repeatable)")  # fmt: skip
    parser.add_argument("--issues", type=int, default=0, metavar="N", help="emit N numbered warnings first")
    parser.add_argument("--raise", dest="raise_", action="store_true", help="raise an internal exception")
    parser.add_argument("--write", metavar="PATH", help="plan a write of --content to PATH")
    parser.add_argument("--content", default="echo\n", help="content for --write")
    parser.add_argument("--gen-id", action="store_true", help="generate an id and a timestamp")


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if args.raise_:
        raise RuntimeError("requested failure (--raise)")
    severities: list[str] = args.issue
    numbered = tuple(
        Issue(
            code="echo.warning",
            severity="warning",
            message=f"requested issue {n + 1} of {args.issues}",
            where="_echo",
        )  # fmt: skip
        for n in range(args.issues)
    )
    issues = numbered + tuple(
        Issue(code=f"echo.{sev}", severity=sev, message=f"requested {sev} issue", where="_echo")  # type: ignore[arg-type]
        for sev in severities
    )
    result: dict[str, Any] = {"echo": {"issues": severities, "write": args.write}}
    if args.gen_id:
        result["id"] = str(uuid.UUID(int=ctx.rng.getrandbits(128), version=4))
        result["timestamp"] = ctx.timestamp.isoformat()
    writes: tuple[PlannedWrite, ...] = ()
    if args.write:
        writes = (PlannedWrite(path=args.write, data=str(args.content).encode("utf-8"), kind="text"),)
    return Result(result=result, issues=issues, writes=writes)


COMMAND = Command(
    name="_echo",
    help=None,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(),
    mutation_example_args=("--write", "echo.txt"),
    paged="issues",
)
