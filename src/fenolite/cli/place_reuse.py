# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite place --strategy reuse``: the placement, and with ``--copper`` the copper, of a block of a
reference board copied onto parts of the board, fitted by their pads (change c0210; capability
layout-reuse, "Reuse strategy of place"; ``docs/cli-contract.md``, "Layout reuse"; ``docs/placement.md``,
"Layout reuse").

``fenolite.reuse`` fits the block; ``cli.reuse_copper`` moves the footprints, measures their pads and
settles the copied copper. This module reads the reference board and the rules of the project beside the
board, runs the copper check before and after the moves, and with ``--drc`` runs ``kicad-cli`` DRC on the
board before and after. ``cmd_place`` judges the layout with its legality check and plans the write.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from fenolite.backends.base import DrcReport, ProjectSet
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.cli import KicadCliError
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.checks.copper import EVIDENCE as COPPER_EVIDENCE
from fenolite.checks.copper import LOWERING_CODES, check_copper, frame_edges, rules_issues
from fenolite.cli._boardview import length, load_board
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT, preflight
from fenolite.cli.api import Context
from fenolite.cli.cmd_tidy import clashes_of
from fenolite.cli.errors import CliError
from fenolite.cli.reuse_copper import (
    Settled,
    apply_fit,
    block_items,
    kind_of,
    landed,
    misplaced,
    settle_copper,
    zone_pads,
)
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.trig import ONE
from fenolite.core.units import Nm, round_half_even_div
from fenolite.model.board import Zone
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef
from fenolite.reuse import (
    DEFAULT_TOLERANCE,
    EVIDENCE,
    BlockFit,
    Layout,
    PartFit,
    Placement,
    copy_copper,
    fit_block,
)
from fenolite.reuse.codes import ZONE_EVIDENCE, issue
from fenolite.tidy import Clash, fresh_clashes

DRC_HYPOTHESIS = "H-K-REUSE-DRC"
"""The register row that a board written by the reuse strategy and judged by Fenolite's checks gives no new
KiCad DRC finding."""
MAP_HINT = "write --map TARGET=REFERENCE, for example --map R11=R1"
OPTIONS = ("source", "anchor", "map", "copper", "tolerance", "drc")
"""The ``place`` options of this strategy, by ``argparse`` dest."""


def register(parser: argparse.ArgumentParser) -> None:
    """The options of the strategy on ``place``'s parser."""
    parser.add_argument(
        "--from",
        dest="source",
        default=None,
        metavar="REFERENCE",
        help="reuse (implied): the board that holds the block to copy onto the --only parts, the first the "
        "anchor",
    )
    parser.add_argument(
        "--anchor", default=None, metavar="REF", help="reuse: the part the block is fitted on"
    )
    parser.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="TARGET=REFERENCE",
        help="reuse: a part whose reference part has another reference",
    )
    parser.add_argument("--copper", action="store_true", help="reuse: copy the block's tracks, arcs and vias")
    parser.add_argument(
        "--tolerance", default=None, metavar="L", help="reuse: the largest pad distance (default 0.05mm)"
    )
    parser.add_argument(
        "--drc", action="store_true", help="reuse: kicad-cli DRC before and after; no write if it grows"
    )


def given(args: argparse.Namespace) -> bool:
    """Whether an option of the strategy, other than ``--from``, was given."""
    return bool(args.anchor is not None or args.map or args.copper or args.tolerance is not None or args.drc)


def parse_parts(text: str | None) -> list[str]:
    """``--only REF,REF`` as the ordered parts of the block; missing, empty or repeated names are
    ``FEN-2001``."""
    if text is None:
        raise CliError("FEN-2001", "--strategy reuse needs --only", where="--only", hint="--only U1,R1,R2")
    parts = [part.strip() for part in text.split(",")]
    if not all(parts) or len(set(parts)) != len(parts):
        raise CliError(
            "FEN-2001", f"--only: cannot read {text!r}", where="--only", hint="name each part once"
        )
    return parts


def parse_map(entries: list[str]) -> dict[str, str]:
    """``TARGET=REFERENCE`` entries as a map; a malformed or repeated entry is ``FEN-2001``."""
    found: dict[str, str] = {}
    for text in entries:
        ours, eq, theirs = (part.strip() for part in text.partition("="))
        if not eq or not ours or not theirs or ours in found:
            raise CliError("FEN-2001", f"--map: cannot read {text!r}", where="--map", hint=MAP_HINT)
        found[ours] = theirs
    return found


@dataclass(frozen=True, slots=True)
class ReuseOptions:
    """The options of the strategy, checked: the reference board, the parts, the anchor, the map and the
    tolerance."""

    source: str
    parts: tuple[str, ...]
    anchor: str
    mapping: dict[str, str]
    tolerance: Nm
    copper: bool
    drc: bool


def options(args: argparse.Namespace) -> ReuseOptions:
    """The options of ``--strategy reuse``; ``FEN-2001`` for a missing or inconsistent one."""
    if args.source is None:
        raise CliError(
            "FEN-2001", "--strategy reuse needs --from", where="--from", hint="--from reference.kicad_pcb"
        )
    if args.force:
        raise CliError("FEN-2001", "--strategy reuse cannot use --force", where="--force")
    parts = parse_parts(args.only)
    mapping = parse_map(args.map)
    anchor = parts[0] if args.anchor is None else args.anchor.strip()
    if anchor not in parts:
        raise CliError("FEN-2001", f"--anchor {anchor} is not one of --only", where="--anchor")
    for ref in mapping:
        if ref not in parts:
            raise CliError("FEN-2001", f"--map names {ref}, which is not one of --only", where="--map")
    tolerance = DEFAULT_TOLERANCE if args.tolerance is None else length(args.tolerance, "--tolerance")
    if tolerance <= 0:
        raise CliError("FEN-2001", "--tolerance must be above 0", where="--tolerance")
    return ReuseOptions(
        args.source, tuple(parts), anchor, mapping, tolerance, bool(args.copper), bool(args.drc)
    )


def _unread(name: str, error: str) -> Issue:
    return issue(
        "reuse.project-unread",
        f"{name} could not be read, so the copper check runs without its rules: {error}",
        where=name,
    )


class CopperChecker:
    """The copper check of a design with the rules of the project beside the board; a file of the
    project that cannot be read gives the issue ``unread(name, error)`` once (``reuse.project-unread`` by
    default)."""

    def __init__(
        self, project: ProjectSet, issues: list[Issue], *, unread: Callable[[str, str], Issue] = _unread
    ) -> None:
        self.project = project
        self.backend = KicadBackend()
        self.issues = issues
        self.unread = unread
        self.lowered = False
        self.runs = 0

    def __call__(self, design: Design) -> list[Clash]:
        rules = self.backend.design_rules(design, self.project, issues=[])
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
                self.issues.append(self.unread(name, str(error)))
            lowering = [*rules_issues(rules), *edge_issues, *report.issues]
            self.lowered = any(found.code in LOWERING_CODES for found in lowering)
        self.runs += 1
        return clashes_of(report.findings)


@dataclass
class ReusePlan:
    """The board after the moves and the copy, the ids of the moved footprints, the issues, the fit, the
    settled copper (``None`` without ``--copper``), the copper-check counts, the evidence, the reference
    board's name, the project files beside the board, and ``result.reuse.drc`` once DRC ran."""

    design: Design
    moved: tuple[str, ...]
    issues: list[Issue]
    fit: BlockFit
    settled: Settled | None
    counts: dict[str, int]
    evidence: Evidence
    reference: str
    beside: dict[str, Path]
    reference_evidence: Evidence
    drc: dict[str, object] | None = field(default=None)

    @property
    def copied(self) -> bool:
        """Whether copper was copied."""
        return self.settled is not None and bool(self.settled.kept)


def files_beside(board_path: Path) -> dict[str, Path]:
    """The project and rules files beside a board, by suffix."""
    return {
        suffix: board_path.with_suffix(suffix)
        for suffix in (".kicad_pro", ".kicad_dru")
        if board_path.with_suffix(suffix).is_file()
    }


def project_beside(board_path: Path, beside: dict[str, Path] | None = None) -> ProjectSet:
    """The project set of a board and the files beside it."""
    found = files_beside(board_path) if beside is None else beside
    return ProjectSet(
        root=board_path.parent,
        board=board_path.name,
        files={board_path.name: board_path, **{path.name: path for path in found.values()}},
    )


def plan_reuse(
    chosen: ReuseOptions,
    ctx: Context,
    design: Design,
    board_path: Path,
    *,
    definitions: dict[str, FootprintDef],
    need: Callable[[str], None],
) -> ReusePlan:
    """Fit the block of ``chosen.source`` onto ``design``, move the parts, check the copper and, with
    ``--copper``, copy and settle the block's copper. ``need(lib_ref)`` asks the project's libraries for
    a definition, which then appears in ``definitions``."""
    backend = KicadBackend()
    issues: list[Issue] = []
    pads = backend.board_pads(design)
    view = load_board(chosen.source, ctx)
    issues += [found for found in view.issues if found.severity == "error"]
    reference = Layout(view.design, view.pads)
    fit = fit_block(
        reference,
        Layout(design, pads),
        chosen.parts,
        anchor=chosen.anchor,
        mapping=chosen.mapping,
        tolerance=chosen.tolerance,
    )
    issues += fit.issues
    assert design.board is not None
    lib_refs = {fp.id: fp.lib_ref for fp in design.board.footprints}
    for part in fit.placed:
        placement = part.placement
        assert placement is not None
        if (placement.rotation, placement.side) != (part.before.rotation, part.before.side):
            need(lib_refs[part.footprint_id])
    moved = apply_fit(design, fit, definitions=definitions)
    issues += moved.issues
    placed = moved.design
    pads_after = backend.board_pads(placed)
    issues += misplaced(fit, pads_after, moved=moved.moved)
    beside = files_beside(board_path)
    check = CopperChecker(project_beside(board_path, beside), issues)
    base = check(design)
    after = check(placed) if moved.moved else base
    fresh = fresh_clashes(base, after)
    for clash in fresh:
        issues.append(
            issue(
                "reuse.check-failed",
                f"the board with the moved parts has {clash.code} on {clash.layer} between "
                f"{', '.join(clash.items)} that the board before lacks; nothing is written",
                where=", ".join(clash.items),
                hint="move the copper in the way, or route the parts after the copy",
            )
        )
    final = placed
    settled: Settled | None = None
    if chosen.copper and fit.transform is not None:
        copy = copy_copper(
            fit,
            reference,
            Layout(placed, pads_after),
            items=block_items(reference, fit),
            zones=zone_pads(reference),
        )
        images = {source: record.pad_id for source, record in landed(fit, pads_after).items()}
        settled = settle_copper(placed, copy, pads=pads_after, check=check, images=images)
        final = settled.design
        issues += settled.issues
        for reason, count in sorted(Counter(item.reason for item in settled.dropped).items()):
            issues.append(
                issue(
                    "reuse.copper-dropped",
                    f"{count} reference item(s) of the block were not copied: {reason}",
                    where=reason,
                )
            )
        board = design.board
        zoned = any(isinstance(held.item, Zone) for held in settled.kept)
        if settled.kept and (zoned or any(zone.filled or zone.fills for zone in board.zones)):
            issues.append(
                issue(
                    "reuse.fill-stale",
                    "reuse copied a zone with its reference fill, or copper onto a board with filled zones",
                    hint="run fenolite fill before check",
                )
            )
    evidence = Evidence.combine(EVIDENCE, view.evidence)
    if settled is not None:
        evidence = Evidence.combine(evidence, COPPER_EVIDENCE)
        if any(isinstance(held.item, Zone) for held in settled.kept):
            evidence = Evidence.combine(evidence, ZONE_EVIDENCE)
    if check.lowered:
        evidence = Evidence.combine(evidence, Evidence(Level.UNVERIFIED, hypotheses=EVIDENCE.hypotheses))
    counts = {"before": len(base), "placed": len(after), "new": len(fresh)}
    return ReusePlan(
        final, moved.moved, issues, fit, settled, counts, evidence, view.input.path, beside, view.evidence
    )


def _placement(placement: Placement | None) -> dict[str, object] | None:
    if placement is None:
        return None
    return {"x": placement.at.x, "y": placement.at.y, "rotation": placement.rotation, "side": placement.side}


def _part_json(part: PartFit, fit: BlockFit, moved: set[str]) -> dict[str, object]:
    return {
        "ref": part.ref,
        "reference": part.reference,
        "matched": part.matched,
        "by_net": part.by_net,
        "within": part.within(fit.tolerance),
        "residual": part.residual,
        "placed": part.placement is not None,
        "moved": part.footprint_id in moved,
        "from": _placement(part.before),
        "to": _placement(part.placement),
        "side_changed": part.side_changed,
        "mirror_suspected": part.mirror_suspected,
    }


def _copper_json(settled: Settled) -> dict[str, object]:
    counts = Counter(dropped.reason for dropped in settled.dropped)
    return {
        "copied": len(settled.kept),
        "items": [
            {
                "uuid": kicad_uuid(held.item),
                "kind": kind_of(held.item),
                "source": held.source,
                "net": held.net,
                "detail": held.detail,
            }
            for held in settled.kept
        ],
        "dropped": [
            {
                "item": dropped.item,
                "kind": dropped.kind,
                "net": dropped.net,
                "reason": dropped.reason,
                "detail": dropped.detail,
            }
            for dropped in settled.dropped
        ],
        "counts": dict(sorted(counts.items())),
        "passes": settled.passes,
    }


def to_json(plan: ReusePlan) -> dict[str, object]:
    """``result.reuse``."""
    fit = plan.fit
    transform = None
    if fit.transform is not None:
        transform = {
            "rotation": fit.transform.rot_udeg,
            "mirror": fit.transform.mirror,
            "x": round_half_even_div(fit.transform.tx_fixed, ONE),
            "y": round_half_even_div(fit.transform.ty_fixed, ONE),
        }
    moved = set(plan.moved)
    return {
        "reference": plan.reference,
        "anchor": fit.anchor,
        "tolerance": fit.tolerance,
        "transform": transform,
        "flipped": fit.flipped,
        "parts": [_part_json(part, fit, moved) for part in fit.parts],
        "copper": None if plan.settled is None else _copper_json(plan.settled),
        "copper_check": plan.counts,
        "drc": plan.drc,
    }


def _drc_counts(report: DrcReport) -> Counter[str]:
    return Counter(
        found.type for found in (*report.violations, *report.unconnected_items) if not found.excluded
    )


def run_drc(plan: ReusePlan, board_path: Path, written: bytes) -> list[Issue]:
    """``kicad-cli`` DRC (the tool ``check`` finds) on the board as it is and as the strategy would write
    it, in copies: sets ``plan.drc`` and the evidence, and returns a ``reuse.drc-new`` per violation type
    that the written board has more of."""
    cli = preflight(None, DEFAULT_TIMEOUT, board_path)
    others: dict[str, Path | bytes] = {path.name: path for path in plan.beside.values()}
    runs: list[DrcReport] = []
    for board_bytes in (None, written):
        files = dict(others) if board_bytes is None else {**others, board_path.name: board_bytes}
        run = cli.drc(board_path, files=files)  # type: ignore[arg-type]
        if run.report is None:
            raise KicadCliError("kicad-cli wrote no DRC report", run.run)
        runs.append(run.report)
    before, after = (_drc_counts(report) for report in runs)
    grown = sorted(kind for kind in after if after[kind] > before.get(kind, 0))
    version = cli.version()
    plan.drc = {
        "tool_version": version,
        "before": sum(before.values()),
        "after": sum(after.values()),
        "new": grown,
    }
    if not grown:
        plan.evidence = Evidence.combine(
            plan.reference_evidence, Evidence(Level.KICAD_VERIFIED, f"kicad-cli {version}", (DRC_HYPOTHESIS,))
        )
    return [
        issue(
            "reuse.drc-new",
            f"kicad-cli {version} DRC finds {after[kind]} {kind} on the board reuse would write and "
            f"{before.get(kind, 0)} on the board as it is; nothing is written",
            where=kind,
            hint="read the violation in KiCad; copy the placement without --copper, or fewer parts",
        )
        for kind in grown
    ]


__all__ = [
    "DRC_HYPOTHESIS",
    "CopperChecker",
    "OPTIONS",
    "ReuseOptions",
    "ReusePlan",
    "files_beside",
    "given",
    "options",
    "parse_map",
    "parse_parts",
    "plan_reuse",
    "project_beside",
    "register",
    "run_drc",
    "to_json",
]
