# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Tidy the routed copper of a KiCad board: prune dangling copper, straighten runs, chamfer right-angle
joints, T-joints and zone corners, each edit kept only when its net keeps its groups and the copper check
finds nothing new; or report its routing style (capability copper-tidy, "Tidy command" and "Tidy report
option"; ``docs/cli-contract.md``, "tidy"; ``docs/copper.md``, "Copper tidy").

The steps live in ``fenolite.tidy``; this module is the glue: it reads the board and the rules of the
project beside it, passes the board-frame pads and ``checks.copper.check_copper`` to the steps, checks the
whole result once more, and with ``--drc`` runs ``kicad-cli`` DRC on the board before and after. With
``--gate drc`` (change c0225, ``cli._gate``) the edits are judged through ``fenolite.api.trial(...,
gate=True)``, each edit kept or undone whole.
"""

from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import hashlib
import os
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fenolite.backends.base import DrcReport, ProjectSet
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.cli import KicadCliError
from fenolite.backends.kicad.copper import is_copper_uuid
from fenolite.backends.kicad.pcb import read_board, source_info, write_board
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.checks.copper import EVIDENCE as COPPER_EVIDENCE
from fenolite.checks.copper import LOWERING_CODES, check_copper, frame_edges, rules_issues
from fenolite.cli import _gate
from fenolite.cli._examples import EXAMPLE_TIDY
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT, preflight
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm, parse_length
from fenolite.model.design import Design
from fenolite.tidy import STEPS, Clash, Edit, chamfer, fresh_clashes, prune, straighten, style
from fenolite.tidy.codes import issue

HELP = "prune, straighten and chamfer the routed copper of a KiCad board, edit by edit; or report its style"
HYPOTHESIS = "H-K-TIDY-DRC"
"""The register row that a board tidied and judged by the copper check gives no new KiCad DRC finding."""
EVIDENCE = Evidence(Level.INFERRED, hypotheses=(HYPOTHESIS, "H-K-CONN-PARITY", *COPPER_EVIDENCE.hypotheses))
"""The evidence of a tidy without ``--drc``: the groups and the copper check, not KiCad."""
STYLE_HYPOTHESIS = "H-G-TIDY-STYLE"
"""The register row that the style report counts each joint, jog, width and via of the board once."""
REPORT_EVIDENCE = Evidence(Level.INFERRED, hypotheses=(STYLE_HYPOTHESIS,))
"""The evidence of ``--report``: counts of the board as read."""


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'tidy'."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, .kicad_pro or project folder")
    parser.add_argument(
        "--nets", action="append", default=[], metavar="GLOB", help="tidy only matching nets (repeatable)"
    )
    parser.add_argument("--prune", action="store_true", help="remove dangling tracks, arcs and vias")
    parser.add_argument("--straighten", action="store_true", help="redraw runs of tracks with fewer turns")
    parser.add_argument("--chamfer", action="store_true", help="chamfer right-angle joints and T-joints")
    parser.add_argument("--zones", action="store_true", help="with the chamfer: also cut zone corners")
    parser.add_argument(
        "--leg", metavar="LENGTH", help="the leg of a chamfer (default: twice the track width)"
    )
    parser.add_argument(
        "-o", "--out", metavar="FILE", help="write to this file instead of replacing PATH's board"
    )
    parser.add_argument("--drc", action="store_true", help="run kicad-cli DRC on the board before and after")
    parser.add_argument(
        "--kicad-cli", dest="kicad_cli", metavar="PATH", help="kicad-cli binary or docker:<image> for --drc"
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS")
    _gate.register(parser)
    parser.add_argument("--report", action="store_true", help="write nothing; report the routing style")
    parser.add_argument(
        "--compare", metavar="REFERENCE", help="also report this KiCad board (implies --report)"
    )


def _leg(text: str | None) -> Nm | None:
    if text is None:
        return None
    try:
        value = parse_length(text.strip())
    except ValueError as error:
        raise CliError(
            "FEN-2001", f"--leg: {error}", where="--leg", hint="lengths need a unit: 0.5mm"
        ) from None
    if value <= 0:
        raise CliError("FEN-2001", "--leg: must be above 0", where="--leg")
    return value


def _relative(path: Path, cwd: Path) -> str:
    try:
        return os.path.relpath(path, cwd)
    except ValueError:  # another Windows drive
        return str(path)


def clashes_of(findings: Sequence[Any]) -> list[Clash]:
    """``tidy.Clash`` values of copper-check findings."""
    return [
        Clash(found.code, found.layer, tuple(sorted({item.entity_id for item in found.items})), found.gap)
        for found in findings
    ]


class _Checker:
    """The copper check of a design with the project's rules, as ``check`` judges the board."""

    def __init__(self, project: ProjectSet, issues: list[Issue]) -> None:
        self.project = project
        self.backend = KicadBackend()
        self.issues = issues
        self.lowered = False
        self.runs = 0

    def __call__(self, design: Design) -> list[Clash]:
        found: list[Issue] = []
        rules = self.backend.design_rules(design, self.project, issues=found)
        checked = rules.design
        edges, edge_issues = frame_edges(self.backend, checked)
        report = check_copper(
            checked,
            pads=self.backend.board_pads(checked),
            min_clearance=rules.min_clearance,
            rules_over_classes=rules.rules_over_classes,
            floor_over_rules=rules.floor_over_rules,
            edges=edges,
            min_edge_clearance=rules.min_edge_clearance,
            edge_floor_over_rules=rules.edge_floor_over_rules,
        )
        if self.runs == 0:
            for name, error in rules.unread:
                self.issues.append(
                    issue(
                        "tidy.project-unread",
                        f"{name} could not be read, so the copper check runs without its rules: {error}",
                        where=name,
                    )
                )
            lowering = [*rules_issues(rules), *edge_issues, *report.issues]
            self.lowered = any(found.code in LOWERING_CODES for found in lowering)
        self.runs += 1
        return clashes_of(report.findings)


def _edit_json(edit: Edit) -> dict[str, object]:
    return {
        "step": edit.step,
        "reason": edit.reason,
        "net": edit.net,
        "layer": edit.layer or None,
        "at": {"x": edit.at.x, "y": edit.at.y},
        "removed": list(edit.removed),
        "replaced": list(edit.replaced),
        "added": list(edit.added),
    }


def _drc_counts(report: DrcReport) -> Counter[str]:
    return Counter(
        found.type for found in (*report.violations, *report.unconnected_items) if not found.excluded
    )


def _project(board_path: Path) -> tuple[ProjectSet, dict[str, Path]]:
    """The copy set of the board with the project and rules files beside it, and those files."""
    beside = {
        suffix: board_path.with_suffix(suffix)
        for suffix in (".kicad_pro", ".kicad_dru")
        if board_path.with_suffix(suffix).is_file()
    }
    project = ProjectSet(
        root=board_path.parent,
        board=board_path.name,
        files={board_path.name: board_path, **{path.name: path for path in beside.values()}},
    )
    return project, beside


def _selected(design: Design, patterns: Sequence[str]) -> list[str]:
    return sorted(
        net.name
        for net in design.circuit.nets
        if any(fnmatch.fnmatchcase(net.name, pattern) for pattern in patterns)
    )


def _board(path: str, ctx: Context) -> Path:
    return resolve_board(Path(path) if Path(path).is_absolute() else ctx.cwd / path)


def _classed(design: Design, project: ProjectSet, issues: list[Issue] | None = None) -> Design:
    """``design`` with the circuit (net classes) that the project beside the board gives; each file that
    fails to read gives ``tidy.project-unread`` in ``issues``."""
    rules = KicadBackend().design_rules(design, project)
    for name, error in rules.unread if issues is not None else ():
        assert issues is not None
        issues.append(
            issue(
                "tidy.project-unread",
                f"{name} could not be read, so the report runs without its net classes: {error}",
                where=name,
            )
        )
    return dataclasses.replace(design, circuit=rules.design.circuit)


def _options(args: argparse.Namespace) -> tuple[tuple[str, ...], Nm | None, bool]:
    """The steps, the leg and whether ``--report`` (or ``--compare``) asks for the report only."""
    if args.out and Path(args.out).is_absolute():
        raise CliError("FEN-2001", "--out must be relative to the working directory")
    leg = _leg(args.leg)
    chosen = tuple(step for step in STEPS if getattr(args, step))
    report = args.report or args.compare is not None
    if args.drc and args.gate:
        raise CliError(
            "FEN-2001", "--gate drc already runs DRC", where="--drc", hint="drop --drc, or --gate drc"
        )
    if report and (chosen or args.zones or leg is not None or args.drc or args.gate or args.out):
        raise CliError(
            "FEN-2001",
            "--report runs no step and writes nothing",
            where="--report",
            hint="drop the step options, or --report and --compare",
        )
    steps = chosen or STEPS
    if leg is not None and "chamfer" not in steps:
        raise CliError("FEN-2001", "--leg needs the chamfer step", where="--leg", hint="add --chamfer")
    if args.zones and "chamfer" not in steps:
        raise CliError("FEN-2001", "--zones needs the chamfer step", where="--zones", hint="add --chamfer")
    return steps, leg, report


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    steps, leg, report = _options(args)
    board_path = _board(args.path, ctx)
    data = board_path.read_bytes()
    text = data.decode("utf-8")
    issues: list[Issue] = []
    design = read_board(text, file=board_path.name, issues=issues)
    source = source_info(design)
    input_ref = InputRef(
        board_path.name,
        hashlib.sha256(data).hexdigest(),
        "kicad_pcb",
        str(source.version) if source is not None else None,
    )
    project, beside = _project(board_path)
    nets = _selected(design, tuple(args.nets or ("*",)))
    if report:
        return _report(args, ctx, board_path, design, (project, beside), input_ref, issues)
    _gate.preflight(args, board_path, args.timeout)
    check = _Checker(project, issues)
    board = design.board
    held = (*board.tracks, *board.arcs, *board.vias) if board is not None else ()
    keep = frozenset(item.id for item in held if is_copper_uuid(item.native_ids.get("kicad", "")))
    pads = KicadBackend().board_pads(design, issues=issues)
    base = check(design)
    tidied = design
    edits: list[Edit] = []
    for step in steps:
        if step == "prune":
            done = prune(tidied, pads=pads, nets=nets, keep=keep)
        elif step == "straighten":
            done = straighten(tidied, pads=pads, check=check, nets=nets, keep=keep)
        else:
            done = chamfer(tidied, pads=pads, check=check, nets=nets, keep=keep, leg=leg, zones=args.zones)
        tidied = done.design
        edits.extend(done.edits)
        issues.extend(found for found in done.issues if found not in issues)
    after = check(tidied) if edits else base
    fresh = fresh_clashes(base, after)
    for clash in fresh:
        issues.append(
            issue(
                "tidy.check-failed",
                f"the tidied board has {clash.code} on {clash.layer} between {', '.join(clash.items)} that "
                "the board before lacks; nothing is written",
                where=", ".join(clash.items),
                hint="report it: every edit is checked on its own first",
            )
        )
    gated: _gate.Gated | None = None
    if args.gate == "drc" and not fresh:
        units = _gate.joined((*edit.removed, *edit.replaced, *edit.added) for edit in edits)
        gated = _gate.gate(board_path, design, tidied, kicad_cli=args.kicad_cli, timeout=args.timeout,
                           together=units)  # fmt: skip
        if gated.dropped:
            gone = [unit for unit in units if unit & gated.dropped]
            edits = [edit for edit in edits if not any({*edit.removed, *edit.replaced, *edit.added} & unit
                                                       for unit in gone)]  # fmt: skip
            tidied = gated.design
            after = check(tidied) if edits else base
        issues.extend(gated.issues)
    major = source.major if source is not None and source.major is not None else ctx.kicad_target
    target = args.out or _relative(board_path, ctx.cwd)
    changed = bool(edits)
    board_text = write_board(tidied, target=major, allow_lossy=ctx.allow_lossy).text if changed else text
    stale = changed and board is not None and any(zone.filled or zone.fills for zone in board.zones)
    if stale:
        issues.append(
            issue(
                "tidy.fill-stale",
                "tidy changed copper of a board with filled zones",
                hint="run fenolite fill before check",
            )
        )
    evidence = Evidence(Level.UNVERIFIED, hypotheses=EVIDENCE.hypotheses) if check.lowered else EVIDENCE
    if gated is not None and gated.evidence is not None:
        evidence = gated.evidence
    drc: dict[str, object] | None = None
    if args.drc and changed and not fresh:
        drc, drc_issues, drc_evidence = _drc(args, board_path, beside, board_text.encode("utf-8"))
        issues.extend(drc_issues)
        if drc_evidence is not None:
            evidence = drc_evidence
    failed = any(found.severity == "error" for found in issues)
    writes = (
        (PlannedWrite(target, board_text.encode("utf-8"), "kicad_pcb"),)
        if changed and not failed and (args.out is not None or board_text != text)
        else ()
    )
    counts: dict[str, int] = Counter()
    for edit in edits:
        counts[f"{edit.step}.{edit.reason}"] += 1
    classes = _classed(design, project).circuit
    before = style(dataclasses.replace(design, circuit=classes), nets=nets).counts()
    after_style = (
        style(dataclasses.replace(tidied, circuit=classes), nets=nets).counts() if changed else before
    )
    return Result(
        result={
            "board": board_path.name,
            "target": target,
            "steps": list(steps),
            "nets": len(nets),
            "changed": changed,
            "edits": [_edit_json(edit) for edit in edits],
            "counts": dict(sorted(counts.items())),
            "removed": sum(len(edit.removed) for edit in edits),
            "added": sum(len(edit.added) for edit in edits),
            "copper_check": {"before": len(base), "after": len(after), "new": len(fresh)},
            "drc": drc,
            "gate": None if args.gate is None else gated.result if gated is not None else _gate.untouched(),
            "fills_stale": stale,
            "style": {"before": before, "after": after_style},
        },
        issues=tuple(issues),
        evidence=evidence,
        input=input_ref,
        writes=writes,
        depends=depends_on(ctx.cwd, board_path, *beside.values()),
    )


def _report(
    args: argparse.Namespace,
    ctx: Context,
    board_path: Path,
    design: Design,
    project: tuple[ProjectSet, dict[str, Path]],
    input_ref: InputRef,
    issues: list[Issue],
) -> Result:
    """``--report``: the style report of the board and, with ``--compare``, of the reference; nothing is
    planned."""
    patterns = tuple(args.nets or ("*",))
    found = style(_classed(design, project[0], issues), nets=_selected(design, patterns))
    issues.extend(found.issues)
    compare: dict[str, object] | None = None
    depends = [board_path, *project[1].values()]
    if args.compare is not None:
        reference = _board(args.compare, ctx)
        other = read_board(reference.read_text(encoding="utf-8"), file=reference.name)
        other_project, other_beside = _project(reference)
        counted = style(_classed(other, other_project), nets=_selected(other, patterns))
        compare = {"board": _relative(reference, ctx.cwd), **counted.as_json()}
        depends += [reference, *other_beside.values()]
    return Result(
        result={
            "board": board_path.name,
            "steps": [],
            "changed": False,
            "report": found.as_json(),
            "compare": compare,
        },
        issues=tuple(issues),
        evidence=REPORT_EVIDENCE,
        input=input_ref,
        depends=depends_on(ctx.cwd, *dict.fromkeys(depends)),
    )


def _drc(
    args: argparse.Namespace, board_path: Path, beside: dict[str, Path], tidied: bytes
) -> tuple[dict[str, object], list[Issue], Evidence | None]:
    """``kicad-cli`` DRC on the board as it is and as tidy would write it, in copies: ``result.drc``, a
    ``tidy.drc-new`` per violation type that the tidied board has more of, and the evidence."""
    cli = preflight(args.kicad_cli, args.timeout, board_path)
    others: dict[str, Path | bytes] = {path.name: path for path in beside.values()}
    runs: list[DrcReport] = []
    for board_bytes in (None, tidied):
        files = dict(others) if board_bytes is None else {**others, board_path.name: board_bytes}
        run = cli.drc(board_path, files=files)  # type: ignore[arg-type]
        if run.report is None:
            raise KicadCliError("kicad-cli wrote no DRC report", run.run)
        runs.append(run.report)
    before, after = (_drc_counts(report) for report in runs)
    grown = sorted(kind for kind in after if after[kind] > before.get(kind, 0))
    version = cli.version()
    found = [
        issue(
            "tidy.drc-new",
            f"kicad-cli {version} DRC finds {after[kind]} {kind} on the tidied board and "
            f"{before.get(kind, 0)} on the board as it is; nothing is written",
            where=kind,
            hint="run fenolite tidy without the step that made it, and report the board",
        )
        for kind in grown
    ]
    result: dict[str, object] = {
        "tool_version": version,
        "before": sum(before.values()),
        "after": sum(after.values()),
        "new": grown,
    }
    evidence = None if grown else Evidence(Level.KICAD_VERIFIED, f"kicad-cli {version}", (HYPOTHESIS,))
    return result, found, evidence


_EXAMPLE = (EXAMPLE_TIDY, "--out", "fenolite-tidy.kicad_pcb")
COMMAND = Command(
    name="tidy",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    paged="edits",
    example_args=(*_EXAMPLE, "--dry-run"),
    mutation_example_args=_EXAMPLE,
)
