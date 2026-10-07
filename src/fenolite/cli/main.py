# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``fenolite`` dispatcher: global flags, command discovery, errors, exit codes and the
mutation protocol. See ``docs/cli-contract.md``."""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import os
import random
import signal
import sys
import time
from collections.abc import Generator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn, TextIO, cast

from fenolite import __version__
from fenolite.cli import plans
from fenolite.cli import progress as progress_records
from fenolite.cli.api import Command, Context, PlannedWrite, Result, discover
from fenolite.cli.errors import CliError, ErrorInfo, from_exception
from fenolite.cli.exitcodes import ExitCode
from fenolite.cli.output import (
    CursorError,
    Envelope,
    Evidence,
    FieldNotFoundError,
    InputRef,
    OutputMode,
    Receipt,
    WrittenFile,
    make_receipt,
    page,
    parse_fields,
    project_fields,
    render_json,
    render_text,
    resolve_mode,
    write_error,
)
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.io import WriteError, atomic_write_all, sha256_bytes
from fenolite.core.state import state_dir

KICAD_TARGETS = (9, 10)
"""The values of ``--kicad-version``: the KiCad majors Fenolite writes for (``versions.TARGET_MAJORS``)."""
DEFAULT_KICAD_TARGET = 10
FORMATS = ("concise", "detailed")
"""The values of ``--format``."""
PAGED_ISSUES = "issues"
MUTATION_FLAGS = ("--dry-run", "--confirm", "--plan")
"""The flags of the mutation protocol, which every mutating command accepts."""


class Interrupted(KeyboardInterrupt):
    """SIGTERM or SIGINT reached ``fenolite``. Raised in the main thread, so that it passes through every
    tool call (which kills its process) and through a write in progress (which rolls back); the dispatcher
    turns it into ``FEN-1003``. A ``KeyboardInterrupt``, not an ``Exception``: no handler of a library
    error catches it, and code that lets Ctrl+C pass lets it pass."""


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
    group.add_argument("--limit", type=int, default=None if top_level else default, metavar="N",
                       help="keep N items of the command's main list (see 'page' in the result)")  # fmt: skip
    group.add_argument("--cursor", default=None if top_level else default, metavar="TOKEN",
                       help="continue a list from the 'next' of the page before")  # fmt: skip
    group.add_argument("--format", choices=FORMATS, default="detailed" if top_level else default,
                       help="concise keeps one issue per code, with counts (default detailed)")  # fmt: skip
    group.add_argument("--progress", action="store_true", default=False if top_level else default,
                       help="write progress records on stderr while the command runs")  # fmt: skip
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
            protocol.add_argument(
                "--plan",
                metavar="ID",
                default=None,
                help="with --confirm: write the reviewed plan of this id",
            )
        command.register(child)
    return parser


def global_flags() -> list[str]:
    """The long flags that every command accepts, in the order of ``--help``."""
    parser = argparse.ArgumentParser(add_help=False)
    _add_global_options(parser, top_level=True)
    return [option for action in parser._actions for option in action.option_strings]  # pyright: ignore[reportPrivateUsage]


def _timestamp(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CliError("FEN-2004", f"invalid --timestamp {value!r}") from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _context(args: argparse.Namespace, mode: OutputMode, err: TextIO) -> Context:
    seed: int | None = args.seed
    rng = random.Random(seed) if seed is not None else random.Random()
    ctx = Context(
        mode=mode,
        seed=seed,
        timestamp=_timestamp(args.timestamp),
        rng=rng,
        no_backup=bool(args.no_backup),
        cwd=Path.cwd(),
        kicad_target=int(args.kicad_version),
        allow_lossy=bool(args.allow_lossy),
        state=state_dir(),
    )
    if not args.progress:
        return ctx
    reporter = progress_records.StderrProgress(mode, err, str(args.command), progress_records.INTERVAL)
    reporter.start()
    return dataclasses.replace(ctx, progress=reporter)


def _quiet(ctx: Context) -> None:
    """End the progress records: what follows on stderr is the error object, alone on the last line."""
    close = getattr(ctx.progress, "close", None)
    if callable(close):
        close()


def _emit(envelope: Envelope, ctx: Context, out: TextIO, text: str | None = None) -> None:
    """Print the envelope. ``text`` (``Result.text``) is used by text mode only."""
    _quiet(ctx)
    out.write((render_json(envelope) if ctx.mode == "json" else render_text(envelope, text)) + "\n")


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


def _usage(message: str, where: str) -> CliError:
    return CliError("FEN-2001", message, where=where)


def _limit(command: Command, args: argparse.Namespace) -> int | None:
    """The page size in force: ``--limit``, else the command's default. Refused before the command runs:
    a limit below 1, ``--limit`` on a command without a paged list, and a cursor without a limit."""
    given: int | None = args.limit
    if given is not None and command.paged is None:
        raise _usage(f"{command.name} has no list to page; --limit does not apply", "--limit")
    if given is not None and given < 1:
        raise _usage("--limit is at least 1", "--limit")
    limit = given if given is not None else command.default_limit
    if args.cursor is not None and limit is None:
        raise _usage("--cursor needs a limit in force: pass --limit as on the page before", "--cursor")
    return limit


def _holder(result: dict[str, Any], path: str) -> tuple[dict[str, Any], str] | None:
    """The mapping that holds the list at the dotted ``path`` and its key, or ``None``."""
    node: dict[str, Any] = result
    parts = path.split(".")
    for part in parts[:-1]:
        inner: object = node.get(part)
        if not isinstance(inner, dict):
            return None
        node = cast(dict[str, Any], inner)
    return (node, parts[-1]) if isinstance(node.get(parts[-1]), list) else None


def _concise(issues: tuple[Issue, ...]) -> tuple[tuple[Issue, ...], list[dict[str, object]]]:
    """The first issue of each code in order, and per code its count and its counts by severity."""
    first: dict[str, Issue] = {}
    counts: dict[str, dict[str, int]] = {}
    for issue in issues:
        first.setdefault(issue.code, issue)
        by_severity = counts.setdefault(issue.code, {})
        by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1
    summary: list[dict[str, object]] = [
        {"code": code, "count": sum(counts[code].values()), "by_severity": dict(sorted(counts[code].items()))}
        for code in sorted(counts)
    ]
    return tuple(first.values()), summary


def _paged(command: Command, result: dict[str, Any], issues: tuple[Issue, ...], limit: int,
           cursor: str | None) -> tuple[dict[str, Any], tuple[Issue, ...]]:  # fmt: skip
    """``result`` and ``issues`` with the command's paged list cut to one page and ``result.page`` set.
    A ``total`` and a ``truncated`` beside the list are set to the whole length and to whether the page
    is not the whole list."""
    assert command.paged is not None
    try:
        for path in command.paged.split("|"):
            if path == PAGED_ISSUES:
                cut = page(issues, limit, cursor)
                issues = cast(tuple[Issue, ...], cut.items)
            else:
                found = _holder(result, path)
                if found is None:
                    continue
                holder, key = found
                cut = page(cast(list[Any], holder[key]), limit, cursor)
                result = _replaced(result, path, list(cut.items), cut)
            result["page"] = {
                "path": path, "limit": cut.limit, "offset": cut.offset, "total": cut.total, "next": cut.next,
            }  # fmt: skip
            return result, issues
    except CursorError as exc:
        raise _usage(str(exc), "--cursor") from exc
    if cursor is not None:
        raise _usage(f"{command.name} returned no list to continue", "--cursor")
    return result, issues


def _replaced(result: dict[str, Any], path: str, items: list[Any], cut: Any) -> dict[str, Any]:
    """A copy of ``result`` with the list at ``path`` replaced by ``items`` (the holders are copied)."""
    parts = path.split(".")
    out = dict(result)
    node = out
    for part in parts[:-1]:
        node[part] = dict(node[part])
        node = node[part]
    node[parts[-1]] = items
    if "total" in node:
        node["total"] = cut.total
    if "truncated" in node:
        node["truncated"] = len(items) < cut.total
    return out


def _payload(write: PlannedWrite) -> bytes:
    """The bytes of a planned write. A deferred write's source is called here, once, and what it returns
    must have the declared size and SHA-256 (cli-contract, "Deferred writes")."""
    if write.source is None:
        return write.data
    data = write.source()
    found = sha256_bytes(data)
    if len(data) != write.size or found != write.sha256:
        raise CliError(
            "FEN-3006",
            f"{write.path}: expected {write.size} bytes with SHA-256 {write.sha256}, "
            f"found {len(data)} bytes with SHA-256 {found}; nothing was written",
            where=write.path,
        )
    return data


def _rows(writes: Sequence[PlannedWrite], cwd: Path) -> list[dict[str, Any]]:
    """One row per planned write: what ``result.plan`` shows, and ``replaces``, the SHA-256 of the file
    it would replace (``None`` without one), which the plan id binds."""
    rows: list[dict[str, Any]] = []
    for w in writes:
        target = cwd / w.path
        rows.append(
            {
                "path": w.path,
                "kind": w.kind,
                "bytes": len(w.data) if w.size is None else w.size,
                "sha256": sha256_bytes(w.data) if w.sha256 is None else w.sha256,
                "overwrite": target.exists(),
                "replaces": plans.digest_of(target),
            }
        )
    return rows


def _shown(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{key: row[key] for key in ("path", "kind", "bytes", "sha256", "overwrite")} for row in rows]


def _digests(depends: Sequence[str], cwd: Path) -> list[tuple[str, str | None]]:
    return [(path, plans.digest_of(cwd / path)) for path in depends]


def _named(path: str) -> str:
    """How an error names a file: as given when relative to the working folder, else by its name."""
    return Path(path).name if Path(path).is_absolute() else path


def _stale(why: str, where: str) -> CliError:
    return CliError("FEN-4002", f"{why}; nothing was written", where=where)


def _replay(command: Command, staged: plans.StagedPlan, args: Mapping[str, Any], ctx: Context) -> Result:
    """The result of the staged plan, its writes holding the staged bytes, once nothing a review relied on
    has changed; ``FEN-4002`` names the first thing that has. The command is not called."""
    if staged.cwd != str(ctx.cwd):
        raise _stale(f"the plan {staged.id} was made in another working folder", "--plan")
    if staged.command != command.name:
        raise _stale(f"the plan {staged.id} was made by the command {staged.command!r}", "--plan")
    if staged.arguments != dict(args):
        keys = sorted(set(staged.arguments) | set(args))
        first = next(key for key in keys if staged.arguments.get(key) != args.get(key))
        raise _stale(
            f"the plan {staged.id} was made for another command line (the argument {first!r} differs)",
            "--plan",
        )
    for path, digest in staged.depends:
        if plans.digest_of(ctx.cwd / path) != digest:
            raise _stale(f"{_named(path)} changed after the plan {staged.id} was reviewed", _named(path))
    for row in staged.writes:
        found = plans.digest_of(ctx.cwd / str(row["path"]))
        if found != row["replaces"]:
            what = "exists now" if row["replaces"] is None else "changed" if found else "is gone"
            raise _stale(f"{row['path']} {what} after the plan {staged.id} was reviewed", str(row["path"]))
    try:
        writes = tuple(PlannedWrite(str(r["path"]), staged.data(r), str(r["kind"])) for r in staged.writes)
        reply = staged.reply
        issues = tuple(Issue(**issue) for issue in reply["issues"])
        evidence = Evidence(**reply["evidence"])
        given = None if reply["input"] is None else InputRef(**reply["input"])
        result = dict(reply["result"])
        write_on_error = bool(reply["write_on_error"])
    except (plans.DamagedPlan, KeyError, TypeError, ValueError) as exc:
        plans.remove(ctx.state, staged.id)
        raise _stale(f"the staged plan {staged.id} is damaged and was removed ({exc})", "--plan") from exc
    return Result(result, issues, evidence, given, writes, write_on_error=write_on_error)


def _load(ctx: Context, plan: str) -> plans.StagedPlan | None:
    try:
        return plans.load(ctx.state, plan)
    except plans.DamagedPlan as exc:
        plans.remove(ctx.state, plan)
        raise _stale(f"the staged plan {plan} is damaged and was removed ({exc})", "--plan") from exc


def _stage(
    command: Command,
    outcome: Result,
    args: Mapping[str, Any],
    ctx: Context,
    plan: str,
    rows: Sequence[Mapping[str, Any]],
    depends: Sequence[tuple[str, str | None]],
) -> Issue | None:
    """Keep the plan for ``--confirm --plan``; the warning ``plan.not-staged`` when it cannot be kept. A
    plan that holds a deferred write has no bytes before ``--confirm`` and is planned again instead."""
    if any(w.deferred for w in outcome.writes):
        return None
    try:
        plans.stage(
            ctx.state,
            plan,
            command=command.name,
            args=args,
            cwd=str(ctx.cwd),
            depends=depends,
            writes=[{k: v for k, v in row.items() if k != "overwrite"} for row in rows],
            payloads=[w.data for w in outcome.writes],
            reply={
                "result": outcome.result,
                "issues": outcome.issues,
                "evidence": outcome.evidence,
                "input": outcome.input,
                "write_on_error": outcome.write_on_error,
            },
        )
    except plans.StageError as exc:
        return Issue(
            "plan.not-staged",
            "warning",
            f"the plan {plan} was not staged: {exc}; --confirm --plan {plan} will run the command again "
            "and write only when the new plan has the same id",
            command.name,
        )
    return None


def _failed(command: Command, exc: Exception, ctx: Context, started: float, out: TextIO, err: TextIO,
            outcome: Result | None = None) -> int:  # fmt: skip
    """The reply of a command that raised: the envelope with ``ok`` false and one error object."""
    failure = exc if isinstance(exc, CliError) else from_exception(exc, command.name)
    shown = _refusal(exc) if outcome is None else outcome
    _emit(_envelope(command, shown, {}, ok=False, receipt=None, started=started), ctx, out)
    write_error(failure.info(), ctx.mode, err)
    return int(failure.exit_code)


def _dispatch(command: Command, args: argparse.Namespace, ctx: Context, started: float,
              out: TextIO, err: TextIO) -> int:  # fmt: skip
    try:
        return _perform(command, args, ctx, started, out, err)
    except KeyboardInterrupt:  # Interrupted, or a Ctrl+C where the handler is not installed
        _emit(_envelope(command, Result(), {}, ok=False, receipt=None, started=started), ctx, out)
        write_error(CliError("FEN-1003", where=command.name).info(), ctx.mode, err)
        return int(ExitCode.INTERNAL)


def _perform(command: Command, args: argparse.Namespace, ctx: Context, started: float,
             out: TextIO, err: TextIO) -> int:  # fmt: skip
    dry_run = bool(getattr(args, "dry_run", False))
    confirm = bool(getattr(args, "confirm", False))
    plan: str | None = getattr(args, "plan", None)
    if dry_run and confirm:
        raise CliError("FEN-2003")
    if plan is not None and not confirm:
        raise _usage("--plan writes a reviewed plan: pass it with --confirm", "--plan")
    fields = parse_fields(args.fields) if args.fields else []
    limit = _limit(command, args)
    arguments = plans.arguments(vars(args))

    staged: plans.StagedPlan | None = None
    try:
        staged = None if plan is None else _load(ctx, plan)
        if staged is not None:
            outcome = _replay(command, staged, arguments, ctx)
        else:
            outcome = command.run(args, ctx)
            if outcome.writes and not command.mutates:
                raise RuntimeError(f"command {command.name!r} returned writes but is not declared mutating")
    except Exception as exc:  # library errors keep their code; any other exception is a bug (FEN-1001)
        return _failed(command, exc, ctx, started, out, err, Result() if isinstance(exc, CliError) else None)

    n_errors = sum(1 for issue in outcome.issues if issue.severity == "error")
    # a command that reports an error plans, stages and writes nothing, `place --force` excepted
    writes = outcome.writes if not n_errors or outcome.write_on_error else ()
    rows = _rows(writes, ctx.cwd)
    plan_id: str | None = None
    if writes:
        depends = list(staged.depends) if staged is not None else _digests(outcome.depends, ctx.cwd)
        plan_id = plans.plan_id(command.name, arguments, str(ctx.cwd), depends, rows)
        if not confirm:
            warning = _stage(command, outcome, arguments, ctx, plan_id, rows, depends)
            if warning is not None:
                outcome = dataclasses.replace(outcome, issues=(*outcome.issues, warning))
    if plan is not None and plan_id != plan:  # not staged: planned again, and the new plan is another one
        made = "the command plans no write now" if plan_id is None else f"the plan made now is {plan_id}"
        return _failed(command, _stale(f"no staged plan has the id {plan}, and {made}", "--plan"),
                       ctx, started, out, err, Result())  # fmt: skip

    code = ExitCode.OK
    error: ErrorInfo | None = None
    receipt: Receipt | None = None
    result = dict(outcome.result)
    shown = outcome.issues  # ok, the exit code and the error come from the whole result, never from this
    if args.format == "concise":
        shown, result["issues_summary"] = _concise(shown)
    if limit is not None:
        result, shown = _paged(command, result, shown, limit, args.cursor)
    written = dict(result)  # what a confirmed write replies: no plan
    if writes:
        result["plan"] = _shown(rows)
        result["plan_id"] = plan_id
        if not confirm and not dry_run:
            code = ExitCode.CONFIRM_REQUIRED
            error = CliError(
                "FEN-4001",
                hint=f"review result.plan, then re-run with --confirm --plan {plan_id} to write exactly "
                "that plan (or with --confirm alone to plan and write in one run)",
                where=command.name,
            ).info()
    try:  # the plan is part of `result`, so --fields keeps it only when asked
        result = project_fields(result, fields) if fields else result
        if confirm:
            written = project_fields(written, fields) if fields else written
    except FieldNotFoundError as exc:
        raise CliError("FEN-2002", f"unknown field {exc.args[0]!r} in --fields") from exc

    shown_outcome = dataclasses.replace(outcome, issues=shown)
    if writes and confirm:
        try:  # every deferred write is resolved and checked before any file of the command is written
            payloads = [_payload(w) for w in writes]
        except Exception as exc:
            return _failed(command, exc, ctx, started, out, err, Result())
        try:
            done = atomic_write_all(
                [(ctx.cwd / w.path, data) for w, data in zip(writes, payloads, strict=True)],
                backup=not ctx.no_backup,
            )
        except WriteError as exc:  # everything was put back; under --plan the stage stays for the retry
            _emit(
                _envelope(command, shown_outcome, result, ok=False, receipt=None, started=started), ctx, out
            )
            where = _relative(exc.path, ctx.cwd)
            failure = CliError("FEN-1002", f"{where}: {exc.reason}; nothing was written", where=where)
            write_error(failure.info(), ctx.mode, err)
            return int(failure.exit_code)
        files = [WrittenFile(path=w.path, sha256=r.sha256) for w, r in zip(writes, done, strict=True)]
        backups = [w.path + ".bak" for w, r in zip(writes, done, strict=True) if r.backup_path is not None]
        receipt = make_receipt(files, backups, plan)
        result = written
        if plan_id is not None:
            plans.remove(ctx.state, plan_id)
        if outcome.written is not None:
            outcome.written()

    if code is ExitCode.OK and n_errors:
        code = ExitCode.FINDINGS
        error = CliError("FEN-5001", f"{n_errors} finding(s) of severity error", where=command.name).info()

    _emit(
        _envelope(command, shown_outcome, result, ok=code is ExitCode.OK, receipt=receipt, started=started),
        ctx,
        out,
        outcome.text,
    )
    if error is not None:
        write_error(error, ctx.mode, err)
    return int(code)


def _relative(path: Path, cwd: Path) -> str:
    """``path`` relative to the working folder in POSIX form, or its name when it lies outside."""
    try:
        return Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(cwd))).as_posix()
    except ValueError:
        return path.name


@contextlib.contextmanager
def _signals() -> Generator[None]:
    """While the command runs, SIGTERM and SIGINT raise :class:`Interrupted` in the main thread. After the
    first one both are ignored, so that the roll back and the error object are not cut by a second."""
    caught = [getattr(signal, name) for name in ("SIGINT", "SIGTERM") if hasattr(signal, name)]

    def stop(signum: int, _frame: object) -> None:
        for number in caught:
            with contextlib.suppress(ValueError, OSError):
                signal.signal(number, signal.SIG_IGN)
        raise Interrupted(signum)

    before: dict[int, Any] = {}
    for number in caught:
        try:
            before[number] = signal.signal(number, stop)
        except (ValueError, OSError):  # not the main thread: the caller keeps its own handlers
            continue
    try:
        yield
    finally:
        for number, handler in before.items():
            with contextlib.suppress(ValueError, OSError, TypeError):
                signal.signal(number, handler)


def main(argv: Sequence[str] | None = None) -> int:
    """Run ``fenolite`` with ``argv`` (defaults to ``sys.argv[1:]``) and return the exit code. Every
    non-zero exit leaves one error object on stderr and no traceback."""
    started = time.perf_counter()
    raw = list(sys.argv[1:] if argv is None else argv)
    out, err = sys.stdout, sys.stderr
    mode = resolve_mode(force_json="--json" in raw, force_text="--text" in raw, stream=out)
    ctx: Context | None = None
    failure: CliError
    with _signals():
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
            ctx = _context(args, mode, err)
            return _dispatch(commands[args.command], args, ctx, started, out, err)
        except CliError as exc:
            failure = exc
        except KeyboardInterrupt:  # Interrupted, or a Ctrl+C where the handler is not installed
            failure = CliError("FEN-1003", where="fenolite")
        except Exception as exc:  # never a traceback: an exception that no handler maps is FEN-1001
            failure = from_exception(exc, "fenolite")
        finally:
            if ctx is not None:
                _quiet(ctx)
        write_error(failure.info(), mode, err)
        return int(failure.exit_code)


__all__ = [
    "DEFAULT_KICAD_TARGET",
    "FORMATS",
    "KICAD_TARGETS",
    "MUTATION_FLAGS",
    "Interrupted",
    "build_parser",
    "global_flags",
    "main",
]
