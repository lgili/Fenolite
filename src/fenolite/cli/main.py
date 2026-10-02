# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``fenolite`` dispatcher: global flags, command discovery, errors, exit codes and the
mutation protocol. See ``docs/cli-contract.md``."""

from __future__ import annotations

import argparse
import random
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, TextIO, cast

from fenolite import __version__
from fenolite.cli.api import Command, Context, Result, discover
from fenolite.cli.errors import CliError, ErrorInfo, from_exception
from fenolite.cli.exitcodes import ExitCode
from fenolite.cli.output import (
    Envelope,
    FieldNotFoundError,
    OutputMode,
    Receipt,
    WrittenFile,
    parse_fields,
    project_fields,
    render_json,
    render_text,
    resolve_mode,
    write_error,
)
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.io import atomic_write, sha256_bytes

KICAD_TARGETS = (9, 10)
"""The values of ``--kicad-version``: the KiCad majors Fenolite writes for (``versions.TARGET_MAJORS``)."""
DEFAULT_KICAD_TARGET = 10


class _Parser(argparse.ArgumentParser):
    """argparse that raises typed usage errors instead of printing and exiting."""

    def error(self, message: str) -> NoReturn:
        raise CliError("FEN-2001", message, hint=f"run '{self.prog} --help'")


def _add_global_options(parser: argparse.ArgumentParser, *, top_level: bool) -> None:
    default: object = argparse.SUPPRESS
    group = parser.add_argument_group("output and determinism")
    group.add_argument("--json", action="store_true", default=False if top_level else default,
                       help="force JSON output")  # fmt: skip
    group.add_argument("--text", action="store_true", default=False if top_level else default,
                       help="force human-readable output")  # fmt: skip
    group.add_argument("--fields", default=None if top_level else default, metavar="A,B.C",
                       help="keep only these dotted paths of 'result'")  # fmt: skip
    group.add_argument("--seed", type=int, default=None if top_level else default,
                       help="seed for generated ids (reproducible output)")  # fmt: skip
    group.add_argument("--timestamp", default=None if top_level else default, metavar="ISO8601",
                       help="fixed timestamp for generated dates")  # fmt: skip
    group.add_argument("--no-backup", action="store_true", default=False if top_level else default,
                       help="do not keep .bak copies of overwritten files")  # fmt: skip
    kicad = parser.add_argument_group("KiCad output")
    kicad.add_argument("--kicad-version", type=int, choices=KICAD_TARGETS, dest="kicad_version",
                       default=DEFAULT_KICAD_TARGET if top_level else default, metavar="{9,10}",
                       help="KiCad major that written files target (default 10)")  # fmt: skip
    kicad.add_argument("--allow-lossy", action="store_true", default=False if top_level else default,
                       help="drop content the target KiCad version cannot read, with a warning")  # fmt: skip


def build_parser(commands: dict[str, Command]) -> argparse.ArgumentParser:
    parser = _Parser(prog="fenolite", description="Headless, agent-first PCB design automation.")
    parser.add_argument("--version", action="version", version=f"fenolite {__version__}")
    _add_global_options(parser, top_level=True)
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", parser_class=_Parser)
    for command in sorted(commands.values(), key=lambda c: c.name):
        if command.help is None:  # hidden: not listed in --help
            child = sub.add_parser(command.name)
        else:
            child = sub.add_parser(command.name, help=command.help, description=command.help)
        _add_global_options(child, top_level=False)
        if command.mutates:
            protocol = child.add_argument_group("writing files")
            protocol.add_argument("--dry-run", action="store_true", help="show the plan; write nothing")
            protocol.add_argument("--confirm", action="store_true", help="perform the writes")
        command.register(child)
    return parser


def _timestamp(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CliError("FEN-2004", f"invalid --timestamp {value!r}") from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _context(args: argparse.Namespace, mode: OutputMode) -> Context:
    seed: int | None = args.seed
    rng = random.Random(seed) if seed is not None else random.Random()
    return Context(
        mode=mode,
        seed=seed,
        timestamp=_timestamp(args.timestamp),
        rng=rng,
        no_backup=bool(args.no_backup),
        cwd=Path.cwd(),
        kicad_target=int(args.kicad_version),
        allow_lossy=bool(args.allow_lossy),
    )


def _emit(envelope: Envelope, mode: OutputMode, out: TextIO) -> None:
    out.write((render_json(envelope) if mode == "json" else render_text(envelope)) + "\n")


def _envelope(command: Command, outcome: Result, result: dict[str, object], *, ok: bool,
              receipt: Receipt | None, started: float) -> Envelope:  # fmt: skip
    return Envelope(
        ok=ok,
        command=command.name,
        schema=command.schema,
        input=outcome.input,
        result=dict(result),
        issues=outcome.issues,
        evidence=outcome.evidence,
        receipt=receipt,
        elapsed_ms=max(0, round((time.perf_counter() - started) * 1000)),
    )


def _refusal(exc: Exception) -> Result:
    """A refusal's own issues for the envelope (a ``FenoliteError`` whose ``issues`` holds ``Issue``s)."""
    found: object = getattr(exc, "issues", None) if isinstance(exc, FenoliteError) else None
    if not isinstance(found, (list, tuple)):
        return Result()
    items = tuple(cast(Sequence[object], found))
    if items and all(isinstance(i, Issue) for i in items):
        return Result(issues=cast(tuple[Issue, ...], items))
    return Result()


def _dispatch(command: Command, args: argparse.Namespace, ctx: Context, started: float,
              out: TextIO, err: TextIO) -> int:  # fmt: skip
    dry_run = bool(getattr(args, "dry_run", False))
    confirm = bool(getattr(args, "confirm", False))
    if dry_run and confirm:
        raise CliError("FEN-2003")
    fields = parse_fields(args.fields) if args.fields else []

    try:
        outcome = command.run(args, ctx)
        if outcome.writes and not command.mutates:
            raise RuntimeError(f"command {command.name!r} returned writes but is not declared mutating")
    except CliError as exc:
        _emit(_envelope(command, Result(), {}, ok=False, receipt=None, started=started), ctx.mode, out)
        write_error(exc.info(), ctx.mode, err)
        return int(exc.exit_code)
    except Exception as exc:  # library errors keep their code; any other exception is a bug (FEN-1001)
        _emit(_envelope(command, _refusal(exc), {}, ok=False, receipt=None, started=started), ctx.mode, out)
        failure = from_exception(exc, command.name)
        write_error(failure.info(), ctx.mode, err)
        return int(failure.exit_code)

    code = ExitCode.OK
    error: ErrorInfo | None = None
    receipt: Receipt | None = None
    result = dict(outcome.result)
    if outcome.writes and (dry_run or not confirm):
        result["plan"] = [
            {"path": w.path, "kind": w.kind, "bytes": len(w.data), "sha256": sha256_bytes(w.data),
             "overwrite": (ctx.cwd / w.path).exists()}
            for w in outcome.writes
        ]  # fmt: skip
        if not dry_run:
            code = ExitCode.CONFIRM_REQUIRED
            error = CliError("FEN-4001", where=command.name).info()
    try:  # the plan is part of `result`, so --fields keeps it only when asked
        result = project_fields(result, fields) if fields else result
    except FieldNotFoundError as exc:
        raise CliError("FEN-2002", f"unknown field {exc.args[0]!r} in --fields") from exc

    if outcome.writes and confirm and not dry_run:
        written: list[WrittenFile] = []
        backups: list[str] = []
        for w in outcome.writes:
            receipt_io = atomic_write(ctx.cwd / w.path, w.data, backup=not ctx.no_backup)
            written.append(WrittenFile(path=w.path, sha256=receipt_io.sha256))
            if receipt_io.backup_path is not None:
                backups.append(w.path + ".bak")
        receipt = Receipt(written=tuple(written), backup=tuple(backups))

    n_errors = sum(1 for issue in outcome.issues if issue.severity == "error")
    if code is ExitCode.OK and n_errors:
        code = ExitCode.FINDINGS
        error = CliError("FEN-5001", f"{n_errors} finding(s) of severity error", where=command.name).info()

    _emit(
        _envelope(command, outcome, result, ok=code is ExitCode.OK, receipt=receipt, started=started),
        ctx.mode,
        out,
    )
    if error is not None:
        write_error(error, ctx.mode, err)
    return int(code)


def main(argv: Sequence[str] | None = None) -> int:
    """Run ``fenolite`` with ``argv`` (defaults to ``sys.argv[1:]``) and return the exit code."""
    started = time.perf_counter()
    raw = list(sys.argv[1:] if argv is None else argv)
    out, err = sys.stdout, sys.stderr
    mode = resolve_mode(force_json="--json" in raw, force_text="--text" in raw, stream=out)
    try:
        commands = discover()
        parser = build_parser(commands)
        try:
            args = parser.parse_args(raw)
        except SystemExit as exc:  # --help / --version print and exit 0
            return exc.code if isinstance(exc.code, int) else 0
        if args.json and args.text:
            raise CliError("FEN-2001", "--json and --text are mutually exclusive")
        if args.command is None:
            parser.print_help(out)
            return int(ExitCode.OK)
        ctx = _context(args, mode)
        return _dispatch(commands[args.command], args, ctx, started, out, err)
    except CliError as exc:
        write_error(exc.info(), mode, err)
        return int(exc.exit_code)


__all__ = ["DEFAULT_KICAD_TARGET", "KICAD_TARGETS", "build_parser", "main"]
