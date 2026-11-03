# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite pick PATH``: the picks of a design's query parts, their candidates, their update, and
supplier proposals (change c0254; ``docs/cli-contract.md``, "pick"; ``docs/picking.md``).

Without ``--update``, ``--update-all`` or ``--propose`` the command is read-only: it lists every query part
with its lock entry and state (``ok``, ``new``, ``stale``, ``row-changed``, ``row-missing``, ``no-match``),
exit 5 when a state is an error. ``--candidates COMPONENT`` ranks the rows of one part. ``--update`` and
``--update-all`` re-resolve lock entries against the current catalog and plan one write of the design lock,
under the mutation protocol. ``--propose`` writes ``UNVERIFIED`` rows under ``devices/proposed/`` and never
the lock. No subprocess runs, and without ``--supplier`` no network connection is opened.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from fenolite.cli._examples import EXAMPLE_PICKS
from fenolite.cli._lock import lock_location, plan_lock, with_lock
from fenolite.cli._picks import picking, query_parts
from fenolite.cli._script import DesignScriptError, run_design_script
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.partquery import PartQuery
from fenolite.dsl import DslError
from fenolite.pick import EVIDENCE
from fenolite.pick.codes import issue
from fenolite.pick.grammar.schema import read_family
from fenolite.pick.match import match, rank_key
from fenolite.pick.propose import (
    RICH_SUPPLIER_API,
    SupplierLookup,
    load_supplier,
    proposals,
    read_rows,
    suppliers,
)
from fenolite.pick.query import parse_query
from fenolite.pick.rows import PROPOSED_DIR, Row, all_rows, is_grammar

EXAMPLE_COPY = "fenolite-pick-example"
"""The folder of ``mutation_example_args``: a copy of ``examples/picks`` that the test suites write into their
empty folder (``tests/_cliexamples.py``); the proposals land in its ``devices/proposed/``."""
HELP = "list the picks of a design's query parts, rank candidates, update picks, or propose rows"
DEFAULT_LIMIT = 20
SCRIPT = "design.py"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", metavar="PATH", help="a design script, or its folder (design.py in it)")
    parser.add_argument(
        "--candidates", metavar="COMPONENT", default=None, help="rank the rows of one query part (read-only)"
    )
    parser.add_argument(
        "--update",
        metavar="COMPONENT",
        action="append",
        default=None,
        help="re-resolve the pick of this part against the current catalog (repeatable)",
    )
    parser.add_argument("--update-all", action="store_true", help="re-resolve every pick")
    parser.add_argument(
        "--propose",
        metavar="QUERY",
        default=None,
        help="write UNVERIFIED rows that meet QUERY under devices/proposed/ (never the lock)",
    )
    parser.add_argument(
        "--from", dest="source", metavar="FILE", default=None, help="the CSV or JSON rows to propose"
    )
    parser.add_argument(
        "--supplier", metavar="NAME", default=None, help="a plugin of the group fenolite.suppliers"
    )
    parser.add_argument(
        "--allow-offsite",
        action="store_true",
        help="allow a supplier plugin that sends data off this machine",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        metavar="SECONDS",
        help="total supplier lookup timeout (above zero, at most 300; default 30)",
    )


def _script(args: argparse.Namespace, ctx: Context) -> Path:
    given = Path(args.path)
    path = given if given.is_absolute() else ctx.cwd / given
    if path.is_dir():
        path = path / SCRIPT
    if not path.is_file():
        raise CliError("FEN-3001", f"{args.path}: no design script {path.name} there", where=path.name)
    return path


def _relative(path: Path, ctx: Context) -> str:
    full = Path(os.path.abspath(path))
    try:
        return full.relative_to(Path(os.path.abspath(ctx.cwd))).as_posix()
    except ValueError:
        return full.as_posix()


def _row_level(row: Row) -> Level:
    try:
        level = Level(row.evidence)
    except ValueError:
        return Level.UNVERIFIED
    return Level.UNVERIFIED if level is Level.UNKNOWN else level


def _evidence(rows: list[Row]) -> Evidence:
    return Evidence.combine(EVIDENCE, *(Evidence(_row_level(row)) for row in rows))


def _row_issues(rows: list[Row]) -> tuple[Issue, ...]:
    uncertain = {(row.row, row.evidence) for row in rows if _row_level(row) is Level.UNVERIFIED}
    return tuple(
        issue(
            "pick.row-unverified",
            f"{name}: selected row retains {label} evidence; this reply does not verify that item",
            where=name,
        )
        for name, label in sorted(uncertain)
    )


def _row_json(query: PartQuery, row: Row) -> dict[str, object]:
    distance, *_ = rank_key(query, row)
    return {
        "device": row.device,
        "row": row.row,
        "catalog": row.catalog,
        "evidence": row.evidence,
        "value": row.record.value,
        "tolerance": row.record.tolerance or None,
        "case": row.record.case or None,
        "distance": str(distance),
    }


def _candidates(args: argparse.Namespace, design: Any, script: Path) -> Result:
    component = args.candidates
    queries = query_parts(design)
    query = queries.get(component)
    if not isinstance(query, PartQuery):
        known = ", ".join(sorted(queries)) or "none"
        raise CliError(
            "FEN-2001",
            f"--candidates: {component} is no query part; the query parts: {known}",
            where=component,
        )
    rows = all_rows(
        Path(os.path.abspath(script)).parent, tuple(design.device_records.values()), queries=(query,)
    )
    result = match(query, rows)
    excluded: dict[str, dict[str, object]] = {}
    for found in result.excluded:
        excluded.setdefault(
            found.row.row,
            {"row": found.row.row, "first": found.row.device, "failed": found.text, "reason": found.reason},
        )
    shown = list(result.matches)  # --limit (default 20) pages the list
    return Result(
        result={
            "path": component,
            "query": query.text(),
            "matches": len(result.matches),
            "candidates": [_row_json(query, row) for row in shown],
            "excluded": [excluded[key] for key in sorted(excluded)],
        },
        evidence=_evidence(shown),
        issues=_row_issues(shown),
    )


def _supplier_result(
    found: SupplierLookup, query: PartQuery, ctx: Context, script: Path, family_files: tuple[Path, ...]
) -> Result:
    folder = Path(os.path.abspath(script)).parent / "devices" / PROPOSED_DIR
    display = [{**item.display, "file": _relative(folder / item.file, ctx)} for item in found.drafts]
    saved = [{**item.persisted, "file": _relative(folder / item.file, ctx)} for item in found.drafts]
    common = {"query": query.text(), "sends": list(found.sends)}
    return Result(
        result={**common, "proposals": display},
        staged_result={**common, "proposals": saved},
        issues=found.issues,
        evidence=Evidence(Level.UNVERIFIED),
        writes=tuple(
            PlannedWrite(_relative(folder / item.file, ctx), item.text.encode("utf-8"), "supplier-proposal")
            for item in found.drafts
        ),
        depends=depends_on(ctx.cwd, *family_files),
    )


def _propose(args: argparse.Namespace, ctx: Context, script: Path) -> Result:
    try:
        query = parse_query(args.propose)
    except Exception as error:  # FormatError: a bad query text is a usage error here
        raise CliError("FEN-2001", f"--propose: {error}", where="--propose") from None
    if (args.source is None) == (args.supplier is None):
        raise CliError(
            "FEN-2001", "--propose takes exactly one of --from FILE and --supplier NAME", where="--propose"
        )
    if args.timeout is not None and args.supplier is None:
        raise CliError("FEN-2001", "--timeout belongs to --propose with --supplier")
    depends: tuple[str, ...] = ()
    if args.source is not None:
        given = Path(args.source)
        path = given if given.is_absolute() else ctx.cwd / given
        if not path.is_file():
            raise CliError("FEN-3001", f"--from: {args.source} is not a file", where="--from")
        rows = read_rows(path.read_text(encoding="utf-8"), file=path.name)
        source = path.name
        depends = depends_on(ctx.cwd, path)
    else:
        if args.supplier not in suppliers():
            raise CliError(
                "FEN-2001",
                f"--supplier: no plugin named {args.supplier} is installed (entry-point group "
                "fenolite.suppliers)",
                where="--supplier",
                hint="check capabilities for installed suppliers, or export rows and use --from FILE",
            )
        plugin = load_supplier(args.supplier)
        if plugin.sends_data_offsite and not args.allow_offsite:
            raise CliError(
                "FEN-2001",
                f"the supplier {args.supplier} sends query keywords offsite",
                hint="pass --allow-offsite to continue",
            )
        lookup = getattr(plugin, "lookup", None)
        if getattr(plugin, "proposal_api", None) == RICH_SUPPLIER_API and callable(lookup):
            limit = args.limit if args.limit is not None else DEFAULT_LIMIT
            timeout = args.timeout if args.timeout is not None else 30
            if not 1 <= limit <= 50 or not 0 < timeout <= 300:
                raise CliError(
                    "FEN-2001", "supplier --limit is 1..50 and --timeout is above zero and at most 300"
                )
            family_files = tuple(
                path
                for path in sorted((script.parent / "devices").rglob("*.toml"))
                if is_grammar(path.read_text(encoding="utf-8"))
            )
            found = lookup(
                query,
                limit=limit,
                timeout=timeout,
                timestamp=ctx.timestamp.isoformat(),
                families=tuple(read_family(p) for p in family_files),
            )
            if not isinstance(found, SupplierLookup):
                raise TypeError("supplier lookup did not return SupplierLookup")
            return _supplier_result(found, query, ctx, script, family_files)
        rows = list(enumerate((dict(row) for row in plugin.propose(query)), start=1))
        source = f"supplier {args.supplier}"
    found, skipped = proposals(query, rows, source=source)
    folder = Path(os.path.abspath(script)).parent / "devices" / PROPOSED_DIR
    writes = tuple(
        PlannedWrite(path=_relative(folder / item.file, ctx), data=item.text.encode("utf-8"), kind="device")
        for item in found
    )
    return Result(
        result={
            "query": query.text(),
            "proposed": [
                {"id": item.device.id, "file": _relative(folder / item.file, ctx)} for item in found
            ],
            "skipped": skipped,
        },
        evidence=Evidence(Level.UNVERIFIED, hypotheses=EVIDENCE.hypotheses) if found else EVIDENCE,
        issues=tuple(
            issue(
                "pick.row-unverified",
                f"{item.device.id}: proposed row remains UNVERIFIED and needs review",
                where=item.device.id,
            )
            for item in found
        ),
        writes=writes,
        depends=depends,
    )


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    script = _script(args, ctx)
    if args.propose is not None:
        return _propose(args, ctx, script)
    if args.source is not None or args.supplier is not None or args.allow_offsite or args.timeout is not None:
        raise CliError(
            "FEN-2001",
            "--from, --supplier, --allow-offsite and --timeout belong to --propose",
            where="--from",
        )
    run = run_design_script(script)
    design = run.design
    if args.candidates is not None:
        if args.update or args.update_all:
            raise CliError("FEN-2001", "--candidates is read-only; drop --update", where="--candidates")
        return _candidates(args, design, script)
    queries = query_parts(design)
    update: frozenset[str] = frozenset()
    if args.update_all:
        update = frozenset(queries)
    elif args.update:
        unknown = sorted(set(args.update) - set(queries))
        if unknown:
            known = ", ".join(sorted(queries)) or "none"
            raise CliError(
                "FEN-2001",
                f"--update: {', '.join(unknown)} is no query part; the query parts: {known}",
                where=unknown[0],
            )
        update = frozenset(args.update)
    given, path = lock_location(_relative(script, ctx), None, ctx.cwd)
    try:
        with picking(script, update) as picks:
            lock = plan_lock(design, script=script, given=given, path=path, frozen=False)
    except DslError as error:
        raise DesignScriptError(str(error), file=str(args.path)) from error
    summary = picks.summary()
    rows = [pick.row for pick in picks.resolution.picks if pick.row is not None] if picks.resolution else []
    found = picks.resolution
    updates: list[dict[str, object]] = [
        {"path": pick.path, "before": pick.before, "after": pick.entry.device if pick.entry else None}
        for pick in (found.picks if found is not None else ())
        if pick.path in update
    ]
    body: dict[str, object] = {**summary, "updates": updates}
    reading = not update
    listed = with_lock(Result(result=body, evidence=_evidence(rows), issues=_row_issues(rows)), lock)
    if reading:
        listed = Result(result=listed.result, issues=listed.issues, evidence=listed.evidence)
    depends = depends_on(ctx.cwd, script, *(f for f in (path,) if f.is_file()))
    return Result(
        result=listed.result,
        issues=listed.issues,
        evidence=listed.evidence,
        writes=listed.writes,
        depends=depends,
    )


COMMAND = Command(
    name="pick",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_PICKS,),
    paged="candidates|picks|proposals",
    default_limit=DEFAULT_LIMIT,
    mutation_example_args=(
        EXAMPLE_COPY,
        "--propose",
        "capacitor(10uF, rating>=25V)",
        "--from",
        f"{EXAMPLE_COPY}/rows.csv",
    ),
)

__all__ = ["COMMAND"]
