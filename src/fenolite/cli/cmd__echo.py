# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Hidden ``_echo`` command: exercises every branch of the CLI contract for the consistency tests."""

from __future__ import annotations

import argparse
import time
import uuid
from typing import Any

from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.output import Issue
from fenolite.core.io import sha256_bytes

DEFERRED = b"deferred echo\n"
"""The bytes of a ``--defer`` write; ``--defer-bad`` declares their size and digest and returns others."""
DEFER_CALLS: list[str] = []
"""The path of each deferred source that was called, in order: the suites count them."""


def _register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--issue", action="append", choices=["error", "warning", "info"], default=[],
                        help="emit an issue of this severity (repeatable)")  # fmt: skip
    parser.add_argument("--issues", type=int, default=0, metavar="N", help="emit N numbered warnings first")
    parser.add_argument("--raise", dest="raise_", action="store_true", help="raise an internal exception")
    parser.add_argument("--write", metavar="PATH", action="append", default=None,
                        help="plan a write of --content to PATH (repeatable)")  # fmt: skip
    parser.add_argument("--content", default="echo\n", help="content for --write")
    parser.add_argument("--gen-id", action="store_true", help="generate an id and a timestamp")
    parser.add_argument("--steps", type=int, default=0, metavar="N", help="report N units of work first")
    parser.add_argument("--sleep", type=float, default=0.0, metavar="S", help="seconds each unit takes")
    parser.add_argument("--defer", metavar="PATH", help="plan a deferred write of fixed bytes to PATH")
    parser.add_argument("--defer-bad", metavar="PATH", dest="defer_bad",
                        help="plan a deferred write whose source returns other bytes")  # fmt: skip
    parser.add_argument("--text-body", metavar="TEXT", help="set Result.text, the command's own text")


def _deferred(path: str, payload: bytes) -> PlannedWrite:
    """A deferred write that declares the size and the digest of ``DEFERRED`` and returns ``payload``."""

    def source() -> bytes:
        DEFER_CALLS.append(path)
        return payload

    return PlannedWrite(
        path=path, data=b"", kind="text", source=source, size=len(DEFERRED), sha256=sha256_bytes(DEFERRED)
    )


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    for n in range(args.steps):  # before --raise, so that a failure can follow progress records
        ctx.progress.step(f"step-{n + 1}", index=n + 1, total=args.steps)
        time.sleep(args.sleep)
        ctx.progress.done(f"step-{n + 1}")
    if args.raise_:
        raise RuntimeError("requested failure (--raise)")
    paths: list[str] = list(args.write or [])
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
    # one path is shown as it was before the flag became repeatable
    result: dict[str, Any] = {
        "echo": {"issues": severities, "write": paths[0] if len(paths) == 1 else paths or None}
    }
    if args.gen_id:
        result["id"] = str(uuid.UUID(int=ctx.rng.getrandbits(128), version=4))
        result["timestamp"] = ctx.timestamp.isoformat()
    data = str(args.content).encode("utf-8")
    writes: tuple[PlannedWrite, ...] = tuple(
        PlannedWrite(path=path, data=data, kind="text") for path in paths
    )
    if args.defer:
        writes += (_deferred(args.defer, DEFERRED),)
    if args.defer_bad:
        writes += (_deferred(args.defer_bad, DEFERRED[::-1]),)
    return Result(result=result, issues=issues, writes=writes, text=args.text_body)


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
