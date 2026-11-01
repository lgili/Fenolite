# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite family``: grammar families (``fenolite.family.v1``) listed, shown, linted, and used to decode
an MPN, to encode a query into ranked MPNs, or to expand a family (change c0263; ``docs/cli-contract.md``,
"family"; ``docs/picking.md``, "Families with ordering codes").

Families come from the project (``devices/`` and ``devices/proposed/`` beside the script or in the folder
that ``--project`` names; the working directory by default) and from every ``--families DIR``. The command
is read-only: it writes no file, runs no subprocess and opens no network connection. ``lint`` exits 5 on an
error finding, ``decode`` when an MPN does not decode, ``encode`` with ``pick.no-match`` when nothing
matches; an unknown family id is ``FEN-2001``.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping
from pathlib import Path

from fenolite.cli._examples import EXAMPLE_FAMILIES
from fenolite.cli.api import Command, Context, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.core.partquery import VALUE_UNITS
from fenolite.pick.codes import issue as pick_issue
from fenolite.pick.grammar import EXPANSION_LIMIT
from fenolite.pick.grammar.candidates import checked
from fenolite.pick.grammar.codes import EVIDENCE, label_evidence
from fenolite.pick.grammar.decode import decode
from fenolite.pick.grammar.expand import Candidate, Expansion, ExpansionLimitError
from fenolite.pick.grammar.lint import lint_family
from fenolite.pick.grammar.schema import Field, GrammarFamily, MatrixRow, parse_family
from fenolite.pick.match import encode
from fenolite.pick.query import parse_query
from fenolite.pick.rows import PROPOSED_DIR, Row, is_grammar, value_text

HELP = "list, show, lint grammar families, decode MPNs, encode a query into MPNs, or expand a family"
ACTIONS = ("list", "show", "lint", "decode", "encode", "expand")
DEFAULT_LIMIT = 20
DEVICES = "devices"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("family_action", choices=ACTIONS, help="what to do")
    parser.add_argument(
        "targets",
        nargs="*",
        metavar="ARG",
        help="show and expand: a family ID; lint: grammar files; decode: MPNs; encode: one query text",
    )
    parser.add_argument(
        "--project",
        metavar="PATH",
        default=None,
        help="a design script or its folder: the families of its devices/ (default: the working directory)",
    )
    parser.add_argument(
        "--families",
        metavar="DIR",
        action="append",
        default=[],
        help="a folder of grammar family files (repeatable)",
    )


def _full(path: str, ctx: Context) -> Path:
    given = Path(path)
    return Path(os.path.abspath(given if given.is_absolute() else ctx.cwd / given))


def _label(path: Path, ctx: Context) -> str:
    try:
        return path.relative_to(Path(os.path.abspath(ctx.cwd))).as_posix()
    except ValueError:
        return path.as_posix()


def _files(args: argparse.Namespace, ctx: Context) -> list[tuple[Path, str]]:
    """``(path, catalog label)`` of every grammar family file the command reads, in reading order."""
    folders: list[tuple[Path, str]] = []
    if args.project is not None or not args.families:
        project = _full(args.project or ".", ctx)
        if args.project is not None and not project.exists():
            raise CliError("FEN-3001", f"--project: {args.project} does not exist", where="--project")
        base = project.parent if project.is_file() else project
        folders += [(base / DEVICES, DEVICES), (base / DEVICES / PROPOSED_DIR, f"{DEVICES}/{PROPOSED_DIR}")]
    for given in args.families:
        folder = _full(given, ctx)
        if not folder.is_dir():
            raise CliError("FEN-3001", f"--families: {given} is not a folder", where="--families")
        folders.append((folder, _label(folder, ctx)))
    found: list[tuple[Path, str]] = []
    for folder, prefix in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.toml"), key=lambda item: item.name):
            if is_grammar(path.read_text(encoding="utf-8")):
                found.append((path, f"{prefix}/{path.name}"))
    return found


def _families(args: argparse.Namespace, ctx: Context) -> tuple[list[GrammarFamily], tuple[str, ...]]:
    """The families of the project and of ``--families`` (each read and checked for form), in id order,
    and the files read; two files of one id are ``FEN-3004``."""
    families: dict[str, GrammarFamily] = {}
    paths: list[Path] = []
    for path, label in _files(args, ctx):
        family = parse_family(path.read_text(encoding="utf-8"), file=label)
        if family.id in families:
            raise FormatError(
                f"id: {family.id} is defined in {families[family.id].file} and in {label}",
                file=label,
                locator="id",
            )
        families[family.id] = family
        paths.append(path)
    return [families[key] for key in sorted(families)], depends_on(ctx.cwd, *paths)


def _evidence(families: list[GrammarFamily]) -> Evidence:
    return Evidence.combine(EVIDENCE, *(label_evidence(family.evidence) for family in families))


def _one(families: list[GrammarFamily], wanted: str) -> GrammarFamily:
    for family in families:
        if family.id == wanted:
            return family
    known = ", ".join(family.id for family in families) or "none"
    raise CliError("FEN-2001", f"no grammar family {wanted}; the families: {known}", where=wanted)


def _summary(family: GrammarFamily) -> dict[str, object]:
    found = lint_family(family)
    return {
        "id": family.id,
        "kind": family.kind,
        "manufacturer": family.manufacturer,
        "summary": family.summary,
        "version": family.version,
        "evidence": family.evidence,
        "file": family.file,
        "uid": family.uid,
        "errors": sum(1 for item in found if item.severity == "error"),
        "warnings": sum(1 for item in found if item.severity == "warning"),
    }


def _span_json(family: GrammarFamily, row: MatrixRow) -> dict[str, object]:
    out: dict[str, object] = {name: list(codes) for name, codes in row.codes.items()}
    value_field = family.value_field
    if row.span is not None and value_field is not None:
        unit = VALUE_UNITS[family.kind]
        span: dict[str, object] = {}
        if row.span.low is not None:
            span["min"] = value_text(unit, row.span.low)
        if row.span.high is not None:
            span["max"] = value_text(unit, row.span.high)
        if row.span.series:
            span["series"] = row.span.series
        if row.span.values is not None:
            span["values"] = [value_text(unit, value) for value in row.span.values]
        out[value_field.name] = span
    return out


def _field_json(item: Field) -> dict[str, object]:
    if item.is_value:
        return {"scheme": item.scheme, "unit": item.unit, "series": item.series or None}
    return {
        "role": item.role,
        "prefer": item.prefer or None,
        "codes": {code.code: dict(code.texts) for code in item.codes},
    }


def _show(family: GrammarFamily) -> dict[str, object]:
    return {
        **_summary(family),
        "licence": family.licence,
        "datasheet": family.datasheet or None,
        "symbol": family.symbol or None,
        "footprint": family.footprint or None,
        "pattern": family.pattern,
        "tail": family.tail,
        "fields": {name: _field_json(item) for name, item in family.fields.items()},
        "valid": [_span_json(family, row) for row in family.valid],
        "exclude": [_span_json(family, row) for row in family.exclude],
        "sources": list(family.sources) or {name: list(ids) for name, ids in family.sources_by.items()},
        "combinations": Expansion(family).size,
    }


def _candidate_json(candidate: Candidate) -> dict[str, object]:
    texts = candidate.code_texts()
    return {
        "mpn": candidate.mpn,
        "family": candidate.family.id,
        "device": candidate.device,
        "value": value_text(VALUE_UNITS[candidate.family.kind], candidate.value),
        **{name: texts[name] for name in sorted(texts)},
    }


def _row_json(row: Row) -> dict[str, object]:
    record = row.record
    texts: Mapping[str, object] = {
        "mpn": record.mpn,
        "family": row.row,
        "device": row.device,
        "manufacturer": record.manufacturer,
        "value": value_text(VALUE_UNITS[row.kind], row.value),
        "case": record.case or None,
        "tolerance": record.tolerance or None,
        "dielectric": record.dielectric or None,
        "footprint": record.footprint,
        "evidence": row.evidence,
    }
    return {key: value for key, value in texts.items() if value is not None}


def _lint(args: argparse.Namespace, ctx: Context) -> Result:
    if not args.targets:
        raise CliError("FEN-2001", "family lint takes one or more grammar files", where="lint")
    files: list[dict[str, object]] = []
    issues: list[Issue] = []
    paths: list[Path] = []
    for given in args.targets:
        path = _full(given, ctx)
        if not path.is_file():
            raise CliError("FEN-3001", f"{given} is not a file", where=given)
        paths.append(path)
        family = parse_family(path.read_text(encoding="utf-8"), file=_label(path, ctx))
        found = lint_family(family)
        issues += [
            Issue(item.code, item.severity, item.message, where=f"{family.file}:{item.where}", hint=item.hint)
            for item in found
        ]
        files.append({**_summary(family)})
    return Result(
        result={"files": files},
        issues=tuple(issues),
        evidence=EVIDENCE,
        depends=depends_on(ctx.cwd, *paths),
    )


def _decode(args: argparse.Namespace, families: list[GrammarFamily]) -> Result:
    if not args.targets:
        raise CliError("FEN-2001", "family decode takes one or more MPNs", where="decode")
    usable = [checked(family) for family in families]
    decoded: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    issues: list[Issue] = []
    evidence = [EVIDENCE]
    for mpn in args.targets:
        found = decode(mpn, usable)
        decoded += [item.as_json() for item in found.decoded]
        evidence += [item.evidence for item in found.decoded]
        if not found.decoded:
            for item in found.failures:
                failures.append(
                    {"mpn": mpn, "family": item.family, "position": item.position, "field": item.field}
                )
        issues += found.issues
    return Result(
        result={"decoded": decoded, "failures": failures},
        issues=tuple(issues),
        evidence=Evidence.combine(*evidence),
    )


def _encode(args: argparse.Namespace, families: list[GrammarFamily]) -> Result:
    if len(args.targets) != 1:
        raise CliError(
            "FEN-2001", "family encode takes one query text, such as 'capacitor(100nF, case=0603)'"
        )
    try:
        query = parse_query(args.targets[0])
    except FormatError as error:
        raise CliError("FEN-2001", f"encode: {error}", where="encode") from None
    usable = [checked(family) for family in families if family.kind == query.kind]
    rows = encode(query, usable)
    issues: tuple[Issue, ...] = ()
    if not rows:
        issues = (
            pick_issue(
                "pick.no-match",
                f"no grammar family gives a candidate that meets {query.text()}",
                query.text(),
                "relax the query, or add or widen a grammar family",
            ),
        )
    return Result(
        result={"query": query.text(), "matches": len(rows), "candidates": [_row_json(row) for row in rows]},
        issues=issues,
        evidence=_evidence(usable),
    )


def _expand(args: argparse.Namespace, families: list[GrammarFamily]) -> Result:
    if len(args.targets) != 1:
        raise CliError("FEN-2001", "family expand takes one family ID", where="expand")
    family = checked(_one(families, args.targets[0]))
    expansion = Expansion(family, limit=sys.maxsize)  # listed lazily, at most EXPANSION_LIMIT
    listed: list[dict[str, object]] = []
    for candidate in expansion:
        if len(listed) == EXPANSION_LIMIT:
            break
        listed.append(_candidate_json(candidate))
    return Result(
        result={
            "family": family.id,
            "combinations": expansion.size,
            "candidates": listed,
            "truncated": len(listed) == EXPANSION_LIMIT,
        },
        evidence=_evidence([family]),
    )


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    action = args.family_action
    if action == "lint":
        return _lint(args, ctx)
    try:
        families, depends = _families(args, ctx)
        if action == "list":
            if args.targets:
                raise CliError("FEN-2001", "family list takes no argument", where="list")
            found = Result(
                result={"families": [_summary(family) for family in families]}, evidence=_evidence(families)
            )
        elif action == "show":
            if len(args.targets) != 1:
                raise CliError("FEN-2001", "family show takes one family ID", where="show")
            family = _one(families, args.targets[0])
            found = Result(result={"family": _show(family)}, evidence=_evidence([family]))
        elif action == "decode":
            found = _decode(args, families)
        elif action == "encode":
            found = _encode(args, families)
        else:
            found = _expand(args, families)
    except ExpansionLimitError as error:
        return Result(result={"candidates": []}, issues=(error.issue,), evidence=EVIDENCE)
    return Result(result=found.result, issues=found.issues, evidence=found.evidence, depends=depends)


COMMAND = Command(
    name="family",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    example_args=("expand", "Example:EX_MLCC", "--project", EXAMPLE_FAMILIES),
    paged="candidates|decoded|families",
    default_limit=DEFAULT_LIMIT,
)

__all__ = ["COMMAND"]
