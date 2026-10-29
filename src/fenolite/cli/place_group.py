# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite place --turn`` and ``--shift``: a group of parts moved rigidly with the copper and zones
joined to their pads only, and ``--pose-search``, the demand across the group's border for the four turns
and a grid of shifts (change c0227; capability layout-reuse, "Group moves", "Copper of a moved group" and
"Pose search"; ``docs/cli-contract.md``, "Group moves"; ``docs/placement.md``, "Group moves").

The move is one ``geometry.Transform``: a turn about a point, or a shift. Each part's new placement is the
move composed with its placement (``reuse.moved_placement``), so a part on the bottom turns the right way.
The copper that moves is each joined group of a net, built without fills, that holds a pad of the group
and no other pad, and each zone whose stored fill joins pads of the group only. Every moved pad is
measured against the move of its old position, and the copper check with the project's rules compares the
board before and after. ``cmd_place`` judges the layout with its legality check and plans the write.
"""

from __future__ import annotations

import argparse
import dataclasses
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from math import isqrt
from pathlib import Path

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.replace import PlacementError, footprint_ref, move_footprint
from fenolite.checks.copper import EVIDENCE as COPPER_EVIDENCE
from fenolite.cli._boardview import length
from fenolite.cli.errors import CliError
from fenolite.cli.place_reuse import CopperChecker, project_beside
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.trig import FULL_TURN, ONE, QUARTER_TURN
from fenolite.core.units import Nm, Udeg, parse_angle, round_half_even_div
from fenolite.geometry.transform import Transform
from fenolite.model.board import Arc, Track, Via, Zone, ZoneFill
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef
from fenolite.placement.codes import issue
from fenolite.reuse import Placement, moved_placement
from fenolite.tidy import fresh_clashes
from fenolite.tidy.graph import groups, net_pieces

HYPOTHESIS = "H-G-GROUP-MOVE"
"""The register row that a group moved by composing one rigid transform with each part's placement keeps
every pad on the moved position of its old one, and the copper moved with it on its pads."""
EVIDENCE = Evidence(Level.INFERRED, hypotheses=(HYPOTHESIS,))
"""The evidence of a group move: every moved pad is measured, the copper check judges the copper."""
PAD_TOLERANCE: Nm = 1_000
"""The largest distance of a moved pad from the move of its old position: a turn rounds each point."""
MAX_POSES = 10_000
"""The most poses ``--pose-search`` tries."""
BEST = 10
"""The poses of least demand that the reply lists."""
OPTIONS = ("turn", "about", "angle", "shift", "by", "pose_search", "within")
"""The ``place`` options of this strategy, by ``argparse`` dest."""
Copper = Track | Arc | Via | Zone


def register(parser: argparse.ArgumentParser) -> None:
    """The options of the strategy on ``place``'s parser."""
    parser.add_argument(
        "--turn", default=None, metavar="REF,REF", help="group (implied): turn these parts about --about"
    )
    parser.add_argument("--about", default=None, metavar="X,Y", help="group: the point of the turn")
    parser.add_argument("--angle", default=None, metavar="DEGREES", help="group: the angle of the turn")
    parser.add_argument(
        "--shift", default=None, metavar="REF,REF", help="group (implied): shift these parts by --by"
    )
    parser.add_argument("--by", default=None, metavar="DX,DY", help="group: the shift, lengths with a unit")
    parser.add_argument(
        "--pose-search",
        action="store_true",
        help="group: with --turn, the demand of the four turns and the shifts of step --pitch; no write",
    )
    parser.add_argument("--within", default=None, metavar="L", help="group: the largest shift of the search")


def given(args: argparse.Namespace) -> bool:
    """Whether an option of the strategy was given."""
    return any(getattr(args, name) not in (None, False) for name in OPTIONS)


def implied(args: argparse.Namespace) -> bool:
    """Whether ``--turn`` or ``--shift`` imply the strategy."""
    return args.turn is not None or args.shift is not None


def _refs(text: str, option: str) -> tuple[str, ...]:
    refs = [ref.strip() for ref in text.split(",")]
    if not all(refs) or len(set(refs)) != len(refs):
        raise CliError(
            "FEN-2001", f"{option}: cannot read {text!r}", where=option, hint="name each part once"
        )
    return tuple(refs)


def _pair(text: str, option: str) -> Point:
    parts = text.split(",")
    if len(parts) != 2:
        raise CliError(
            "FEN-2001", f"{option}: cannot read {text!r}", where=option, hint=f"{option} 20mm,20mm"
        )
    return Point(length(parts[0], option), length(parts[1], option))


@dataclass(frozen=True, slots=True)
class GroupOptions:
    """The options of the strategy, checked: the parts, ``turn`` or ``shift``, the point of the turn in
    the frame of ``--move`` (``None`` for a shift), the angle, the shift, and the search."""

    refs: tuple[str, ...]
    kind: str
    about: Point | None = None
    angle: Udeg = 0
    by: Point = Point(0, 0)
    search: bool = False
    within: Nm = 0


def options(args: argparse.Namespace) -> GroupOptions:
    """The options of the strategy; ``FEN-2001`` for a missing or inconsistent one."""
    if args.turn is not None and args.shift is not None:
        raise CliError("FEN-2001", "--turn and --shift cannot be given together", where="--shift")
    if args.turn is None and args.shift is None:
        raise CliError("FEN-2001", "the group strategy needs --turn or --shift", where="--turn")
    if args.turn is not None:
        if args.by is not None:
            raise CliError("FEN-2001", "--by goes with --shift", where="--by")
        if args.about is None:
            raise CliError("FEN-2001", "--turn needs --about", where="--about", hint="--about 20mm,20mm")
        about = _pair(args.about, "--about")
        refs = _refs(args.turn, "--turn")
        if args.pose_search:
            if args.angle is not None:
                raise CliError(
                    "FEN-2001", "--pose-search tries the four turns: drop --angle", where="--angle"
                )
            if args.within is None:
                raise CliError(
                    "FEN-2001", "--pose-search needs --within", where="--within", hint="--within 2mm"
                )
            within = length(args.within, "--within")
            if within < 0:
                raise CliError("FEN-2001", "--within must not be negative", where="--within")
            return GroupOptions(refs, "turn", about, search=True, within=within)
        if args.within is not None:
            raise CliError("FEN-2001", "--within goes with --pose-search", where="--within")
        if args.angle is None:
            raise CliError("FEN-2001", "--turn needs --angle", where="--angle", hint="--angle 90")
        try:
            angle = parse_angle(args.angle.strip(), default_unit="deg") % FULL_TURN
        except ValueError as error:
            raise CliError("FEN-2001", f"--angle: {error}", where="--angle") from None
        return GroupOptions(refs, "turn", about, angle=angle)
    for name, value in (("--about", args.about), ("--angle", args.angle), ("--within", args.within)):
        if value is not None:
            raise CliError("FEN-2001", f"{name} goes with --turn", where=name)
    if args.pose_search:
        raise CliError("FEN-2001", "--pose-search goes with --turn", where="--pose-search")
    if args.by is None:
        raise CliError("FEN-2001", "--shift needs --by", where="--by", hint="--by 1mm,0mm")
    shift = str(args.shift)
    return GroupOptions(_refs(shift, "--shift"), "shift", by=_pair(args.by, "--by"))


def turn_about(at: Point, angle: Udeg) -> Transform:
    """``p ↦ R(angle)·(p − at) + at``."""
    return (
        Transform.translation(at.x, at.y)
        .compose(Transform.rotation(angle))
        .compose(Transform.translation(-at.x, -at.y))
    )


def _moved_item(item: Copper, move: Transform) -> Copper:
    if isinstance(item, Track):
        return dataclasses.replace(item, start=move.apply(item.start), end=move.apply(item.end))
    if isinstance(item, Arc):
        return dataclasses.replace(
            item, start=move.apply(item.start), mid=move.apply(item.mid), end=move.apply(item.end)
        )
    if isinstance(item, Via):
        return dataclasses.replace(item, position=move.apply(item.position))
    return dataclasses.replace(
        item,
        outline=tuple(move.apply(point) for point in item.outline),
        fills=tuple(
            ZoneFill(fill.layer, tuple(move.apply(point) for point in fill.polygon), fill.island)
            for fill in item.fills
        ),
    )


def moving_copper(design: Design, pads: Sequence[BoardPad], members: Collection[str]) -> frozenset[str]:
    """The ids of the tracks, arcs, vias and zones that move with the footprints ``members``: each joined
    group of a net, without fills, that holds a pad of them and no other pad, and each zone whose stored
    fill joins pads of them only."""
    owner = {record.pad_id: record.footprint_id for record in pads}
    shaped = net_pieces(design, pads)
    found: set[str] = set()
    for net, held in shaped.pieces.items():
        if net in shaped.unsupported:
            continue
        for with_fills in (False, True):
            pieces = [piece for piece in held if with_fills or piece.kind != "fill"]
            roots = groups(pieces)
            joined: dict[int, set[str]] = {}
            for piece in pieces:
                if piece.kind == "pad":
                    joined.setdefault(roots[piece.ident], set()).add(owner[piece.ident])
            for piece in pieces:
                fps = joined.get(roots[piece.ident], set())
                if not fps or not fps <= set(members):
                    continue
                if with_fills and piece.kind == "fill":
                    found.add(piece.ident.split("#", 1)[0])
                elif not with_fills and piece.kind in ("track", "arc", "via"):
                    found.add(piece.ident)
    return frozenset(found)


def without(design: Design, items: Collection[str]) -> Design:
    """``design`` without the tracks, arcs, vias and zones ``items``."""
    board = design.board
    if board is None or not items:
        return design
    return dataclasses.replace(
        design,
        board=dataclasses.replace(
            board,
            tracks=tuple(item for item in board.tracks if item.id not in items),
            arcs=tuple(item for item in board.arcs if item.id not in items),
            vias=tuple(item for item in board.vias if item.id not in items),
            zones=tuple(item for item in board.zones if item.id not in items),
        ),
    )


def _distance(a: Point, b: Point) -> int:
    square = (a.x - b.x) ** 2 + (a.y - b.y) ** 2
    root = isqrt(square)
    return root if root * root == square else root + 1


@dataclass
class GroupPlan:
    """The board after the move, the ids of the moved footprints and copper, the issues, the largest pad
    distance from its goal, the copper-check counts, the poses of a search, and the evidence."""

    options: GroupOptions
    design: Design
    moved: tuple[str, ...] = ()
    copper: frozenset[str] = frozenset()
    issues: list[Issue] = field(default_factory=lambda: [])
    move: Transform | None = None
    residual: Nm | None = None
    counts: dict[str, int] = field(default_factory=lambda: {})
    search: dict[str, object] | None = None
    evidence: Evidence = EVIDENCE


def _members(design: Design, refs: Sequence[str], issues: list[Issue]) -> list[str]:
    """The footprint ids of ``refs``; a reference the board lacks is ``place.unknown-ref``."""
    assert design.board is not None
    by_ref: dict[str, str] = {}
    for fp in design.board.footprints:
        by_ref.setdefault(footprint_ref(design, fp), fp.id)
    for ref in refs:
        if ref not in by_ref:
            issues.append(issue("place.unknown-ref", f"the board has no part {ref}", ref))
    return [by_ref[ref] for ref in refs if ref in by_ref]


def plan_group(
    chosen: GroupOptions,
    design: Design,
    board_path: Path,
    *,
    origin: Point,
    pitch: Nm,
    definitions: dict[str, FootprintDef],
    need: Callable[[str], None],
    force: bool,
) -> GroupPlan:
    """Move the group of ``chosen`` (or, with ``--pose-search``, rank its poses) on ``design``.
    ``origin`` is the top-left corner of the outline's box, the frame of ``--about``; ``need(lib_ref)``
    asks the project's libraries for a definition, which then appears in ``definitions``."""
    backend = KicadBackend()
    plan = GroupPlan(chosen, design)
    members = _members(design, chosen.refs, plan.issues)
    pads = backend.board_pads(design)
    about = None if chosen.about is None else Point(origin.x + chosen.about.x, origin.y + chosen.about.y)
    if chosen.search:
        assert about is not None
        plan.search = pose_search(pads, members, about=about, within=chosen.within, pitch=pitch)
        return plan
    if about is not None:
        move = turn_about(about, chosen.angle)
    else:
        move = Transform.translation(chosen.by.x, chosen.by.y)
    plan.move = move
    if not members:
        return plan
    assert design.board is not None
    copper = moving_copper(design, pads, members)
    placed = design
    moved: list[str] = []
    footprints = {fp.id: fp for fp in design.board.footprints}
    for fp_id in members:
        fp = footprints[fp_id]
        target = moved_placement(move, Placement(fp.position, fp.rotation, fp.side))
        if target.rotation != fp.rotation:
            need(fp.lib_ref)
        try:
            changed = move_footprint(
                placed,
                fp_id,
                at=target.at,
                rotation=target.rotation,
                side=target.side,
                definitions=definitions,
                force=force,
            )
        except PlacementError as error:
            plan.issues.extend(error.issues)
            continue
        if changed is not placed:
            placed = changed
            moved.append(fp_id)
    board = placed.board
    assert board is not None
    if moved:
        board = dataclasses.replace(
            board,
            tracks=tuple(_moved_item(t, move) if t.id in copper else t for t in board.tracks),  # type: ignore[misc]
            arcs=tuple(_moved_item(a, move) if a.id in copper else a for a in board.arcs),  # type: ignore[misc]
            vias=tuple(_moved_item(v, move) if v.id in copper else v for v in board.vias),  # type: ignore[misc]
            zones=tuple(_moved_item(z, move) if z.id in copper else z for z in board.zones),  # type: ignore[misc]
        )
        placed = dataclasses.replace(placed, board=board)
        plan.copper = copper
    plan.moved = tuple(moved)
    plan.design = placed
    after: dict[tuple[str, str], list[BoardPad]] = {}
    for record in backend.board_pads(placed):
        after.setdefault((record.footprint_id, record.number), []).append(record)
    far = 0
    for record in pads:
        if record.footprint_id not in moved:
            continue
        goal = move.apply(record.position)
        held = after.get((record.footprint_id, record.number), [])
        distance = min((_distance(other.position, goal) for other in held), default=None)
        if distance is None or distance > PAD_TOLERANCE:
            where = "is missing" if distance is None else f"lies {distance} nm from its goal"
            plan.issues.append(
                issue(
                    "place.group-failed",
                    f"pad {record.number} of {record.ref} {where} after the move; nothing is written",
                    record.ref,
                    "report the board: the move and the footprint disagree",
                )
            )
            continue
        far = max(far, distance)
    plan.residual = far if moved else None
    if moved:
        check = CopperChecker(project_beside(board_path), plan.issues, unread=_unread)
        base, now = check(design), check(placed)
        fresh = fresh_clashes(base, now)
        for clash in fresh:
            plan.issues.append(
                issue(
                    "place.group-failed",
                    f"the board with the moved group has {clash.code} on {clash.layer} between "
                    f"{', '.join(clash.items)} that the board before lacks; nothing is written",
                    ", ".join(clash.items),
                    "move the copper in the way, or pick another pose",
                )
            )
        plan.counts = {"before": len(base), "after": len(now), "new": len(fresh)}
        plan.evidence = Evidence.combine(EVIDENCE, COPPER_EVIDENCE)
        if check.lowered:
            plan.evidence = Evidence.combine(
                plan.evidence, Evidence(Level.UNVERIFIED, hypotheses=(HYPOTHESIS,))
            )
        stale = sorted(zone.id for zone in board.zones if zone.id in copper and zone.fills)
        if stale:
            plan.issues.append(
                issue(
                    "place.fill-stale",
                    f"{len(stale)} zone(s) moved with the group keep their moved fill",
                    "zones",
                    "run fenolite fill before check",
                )
            )
    return plan


def _unread(name: str, error: str) -> Issue:
    return issue(
        "place.group-failed",
        f"{name} could not be read, so the copper check cannot judge the move with its rules: {error}",
        name,
        "repair or remove the file, then move the group again",
    )


def pose_search(
    pads: Sequence[BoardPad], members: Collection[str], *, about: Point, within: Nm, pitch: Nm
) -> dict[str, object]:
    """The demand of each pose of the group: the four quarter turns about ``about`` with every shift
    ``(i·pitch, j·pitch)`` within ``within`` on each axis. The demand of a pose is, per net with a pad of
    the group and one outside, the shortest distance between a moved pad of the group and a pad outside,
    rounded up; ``FEN-2001`` beyond ``MAX_POSES`` poses."""
    steps = within // pitch
    tried = 4 * (2 * steps + 1) ** 2
    if tried > MAX_POSES:
        raise CliError(
            "FEN-2001",
            f"--pose-search would try {tried} poses, more than {MAX_POSES}",
            where="--within",
            hint="raise --pitch or lower --within",
        )
    inside: dict[str, list[Point]] = {}
    outside: dict[str, list[Point]] = {}
    for record in pads:
        if record.net_id is None or record.kind == "np_thru_hole":
            continue
        side = inside if record.footprint_id in members else outside
        side.setdefault(record.net_id, []).append(record.position)
    nets = sorted(set(inside) & set(outside))
    names = {record.net_id: record.net or record.net_id for record in pads if record.net_id is not None}

    def demand(move: Transform) -> int:
        return sum(
            min(_distance(move.apply(point), other) for point in inside[net] for other in outside[net])
            for net in nets
        )

    poses: list[tuple[tuple[int, int, int, int, int], dict[str, object]]] = []
    for turn in range(4):
        angle = turn * QUARTER_TURN
        for i in range(-steps, steps + 1):
            for j in range(-steps, steps + 1):
                dx, dy = i * pitch, j * pitch
                move = Transform.translation(dx, dy).compose(turn_about(about, angle))
                total = demand(move)
                row: dict[str, object] = {"rotation": angle, "dx": dx, "dy": dy, "demand": total}
                poses.append(((total, angle, abs(dx) + abs(dy), dx, dy), row))
    poses.sort(key=lambda pose: pose[0])
    return {
        "about": {"x": about.x, "y": about.y},
        "within": within,
        "pitch": pitch,
        "tried": tried,
        "nets": [names[net] for net in nets],
        "current": demand(Transform()),
        "poses": [row for _, row in poses[:BEST]],
    }


def to_json(plan: GroupPlan) -> dict[str, object]:
    """``result.group``."""
    chosen = plan.options
    move = None
    if plan.move is not None:
        move = {
            "rotation": plan.move.rot_udeg,
            "x": round_half_even_div(plan.move.tx_fixed, ONE),
            "y": round_half_even_div(plan.move.ty_fixed, ONE),
        }
    board = plan.design.board
    zones: set[str] = {zone.id for zone in board.zones} if board is not None else set()
    return {
        "refs": list(chosen.refs),
        "kind": "pose-search" if chosen.search else chosen.kind,
        "transform": move,
        "copper": {"items": len(plan.copper - zones), "zones": len(plan.copper & zones)},
        "residual": plan.residual,
        "copper_check": plan.counts or None,
        "search": plan.search,
    }


__all__ = [
    "BEST",
    "EVIDENCE",
    "HYPOTHESIS",
    "MAX_POSES",
    "OPTIONS",
    "PAD_TOLERANCE",
    "GroupOptions",
    "GroupPlan",
    "given",
    "implied",
    "moving_copper",
    "options",
    "plan_group",
    "pose_search",
    "register",
    "to_json",
    "turn_about",
    "without",
]
