# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The optimizer's check of the moved parts only gives the whole board's verdicts (change c0487, follow-up
2026-11-17)."""

import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace

import pytest
from _coppercheck import Copper, disc_entry, ident

import fenolite.cli.placement_checks as placement_checks
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.rooms import LOCATOR
from fenolite.backends.altium.read.rules import keepout_clearance_rule
from fenolite.backends.base import BoardFrame, DesignRules
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.cli.place_optimize import propose, propose_altium
from fenolite.cli.placement_checks import MovedPartsCheck, check_placement_constraints
from fenolite.core.coords import Point
from fenolite.core.provenance import Provenance
from fenolite.geometry.shapes import BBox
from fenolite.model import canonical
from fenolite.model.board import ComponentBody, Graphic, Hole, Keepout, Outline, OutlineArc, placed_keepout
from fenolite.model.design import Design
from fenolite.placement.constrained_legality import PlacementLegality
from fenolite.placement.constraints import PlacementConstraints
from fenolite.placement.optimization_contract import OptimizationBudget, OptimizationRequest

MM = 1_000_000
W, H = 50 * MM, 40 * MM


def _rect(x0: int, y0: int, x1: int, y1: int) -> tuple[Point, ...]:
    return (Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1))


def authored(seed: int, count: int = 24) -> Design:
    """A two-layer board of ``count`` parts (through-hole and SMD, some on the back, some with courtyards,
    one with its own rule area), tracks, vias, a filled zone, rule areas, holes and a cut-out."""
    rng = random.Random(seed)
    made = Copper()
    made.rule("all", 200_000)
    made.rule("holes", 300_000, kind="hole_clearance")
    nets = [f"N{i}" for i in range(6)]
    for i in range(count):
        tht = i % 3 == 0
        for n in range(2 + i % 2):
            made.pad(
                f"U{i}",
                str(n + 1),
                rng.choice(nets),
                disc_entry(n * 2 * MM, 0, 1_200_000),
                kind="thru_hole" if tht else "smd",
                layers=("F.Cu", "B.Cu") if tht else ("F.Cu",),
            )
    for _ in range(60):
        a = Point(rng.randrange(2 * MM, W - 2 * MM), rng.randrange(2 * MM, H - 2 * MM))
        b = Point(a.x + rng.randrange(-8 * MM, 8 * MM), a.y + rng.randrange(-8 * MM, 8 * MM))
        made.track(rng.choice(nets), a, b, layer=rng.choice(("F.Cu", "B.Cu")))
    for _ in range(15):
        made.via(
            rng.choice(nets), Point(rng.randrange(2 * MM, W - 2 * MM), rng.randrange(2 * MM, H - 2 * MM))
        )
    made.zone("N0", _rect(0, 0, W, H), layer="B.Cu", fills=(_rect(30 * MM, 2 * MM, 48 * MM, 20 * MM),))
    design = made.build()
    board = design.board
    assert board is not None
    footprints = []
    for i, fp in enumerate(board.footprints):
        side = "bottom" if i % 5 == 4 else "top"
        courtyard = "B.CrtYd" if side == "bottom" else "F.CrtYd"
        graphics = (
            (
                Graphic(
                    id=ident("gra", 900 + i),
                    kind="polygon",
                    layer=courtyard,
                    points=_rect(-MM, -MM, 5 * MM, MM),
                    width=50_000,
                ),
            )
            if i % 2
            else ()
        )
        keepouts = (
            (
                Keepout(
                    id=ident("kpo", 900),
                    outline=_rect(-MM, 2 * MM, 3 * MM, 4 * MM),
                    layers=("F.Cu",),
                    no_pads=True,
                ),
            )
            if i == 7
            else ()
        )
        footprints.append(
            replace(
                fp,
                position=Point(4 * MM + (i % 6) * 8 * MM, 4 * MM + (i // 6) * 9 * MM),
                rotation=rng.choice((0, 90_000_000, 180_000_000)),
                side=side,
                graphics=graphics,
                keepouts=keepouts,
                pads=tuple(replace(p, drill=600_000) if p.kind == "thru_hole" else p for p in fp.pads),
            )
        )
    outline = Outline(
        id="out_00000000-0000-0000-0000-000000000001",
        points=_rect(0, 0, W, H),
        cutouts=(_rect(20 * MM, 30 * MM, 24 * MM, 34 * MM),),
    )
    return replace(
        design,
        board=replace(
            board,
            footprints=tuple(footprints),
            outline=outline,
            keepouts=(
                Keepout(
                    id=ident("kpo", 901),
                    outline=_rect(10 * MM, 10 * MM, 16 * MM, 16 * MM),
                    layers=("F.Cu", "B.Cu"),
                    no_pads=True,
                    no_footprints=True,
                ),
                Keepout(
                    id=ident("kpo", 902),
                    outline=_rect(36 * MM, 24 * MM, 44 * MM, 30 * MM),
                    layers=("F.Cu",),
                    no_tracks=True,
                ),
            ),
            holes=(
                Hole(id=ident("hol", 1), position=Point(26 * MM, 6 * MM), drill=3 * MM),
                Hole(id=ident("hol", 2), position=Point(6 * MM, 34 * MM), drill=2 * MM),
            ),
        ),
    )


def verdicts(legality: PlacementLegality) -> tuple[object, ...]:
    """What an evaluation reads: hard and missing strings, the copper and mechanical findings, and the order
    of the copper keys."""
    copper = legality.copper.findings
    return (
        legality.hard,
        legality.missing_inputs,
        Counter(copper),
        [(f.code, f.where) for f in copper],
        Counter(legality.mechanical.findings),
        Counter(legality.mechanical.missing_inputs),
    )


def _pose(rng: random.Random, design: Design, extra: Sequence[Point] = ()) -> Point:
    """Anywhere, on the edge, or next to a part, a hole, a rule area, a drill or a point of ``extra``."""
    board = design.board
    assert board is not None
    near = [
        *(fp.position for fp in board.footprints),
        *(hole.position for hole in board.holes),
        *(area.outline[0] for area in board.keepouts),
        Point(0, rng.randrange(H)),
        Point(W, rng.randrange(H)),
        Point(22 * MM, 30 * MM),
        *extra,
    ]
    if rng.random() < 0.3:
        return Point(rng.randrange(-2 * MM, W + 2 * MM), rng.randrange(-2 * MM, H + 2 * MM))
    at = rng.choice(near)
    return Point(at.x + rng.randrange(-3 * MM, 3 * MM), at.y + rng.randrange(-3 * MM, 3 * MM))


def _equivalence(
    seed: int,
    design: Design,
    frame: BoardFrame,
    holder: str,
    *,
    rules: DesignRules | None = None,
    extra: Sequence[Point] = (),
) -> int:
    """Three rounds of 12 random candidates of a few movable parts (``holder``, which holds a rule area, among
    them in the first): each candidate's verdicts of ``MovedPartsCheck`` are those of the whole board's check.
    The number of candidates judged on a cut board."""
    rng = random.Random(seed)
    board = design.board
    assert board is not None
    constraints = PlacementConstraints(gap=500_000, edge_clearance=500_000)
    windows = 0
    for round in range(3):
        movable = set(rng.sample([fp.id for fp in board.footprints], rng.randint(1, 3)))
        if round == 0:
            movable.add(holder)  # it holds a rule area: the whole board is checked
        fixed = replace(
            design, board=replace(board, footprints=tuple(f for f in board.footprints if f.id not in movable))
        )
        check = MovedPartsCheck(fixed, frame, constraints, rules=rules)
        assert verdicts(check(fixed, set())) == verdicts(
            check_placement_constraints(fixed, frame, constraints, rules=rules)
        )
        for _ in range(12):
            placed = {ident for ident in movable if rng.random() < 0.8} or movable
            footprints = tuple(
                replace(
                    fp,
                    position=_pose(rng, design, extra),
                    rotation=rng.choice((0, 90_000_000, 180_000_000, 270_000_000, 45_000_000, 30_500_000)),
                    side=rng.choice(("top", "bottom")),
                )
                if fp.id in placed
                else fp
                for fp in board.footprints
                if fp.id not in movable or fp.id in placed
            )
            candidate = replace(design, board=replace(board, footprints=footprints))
            full = check_placement_constraints(candidate, frame, constraints, rules=rules)
            assert verdicts(check(candidate, placed)) == verdicts(full)
        windows += check.windows
    return windows


@pytest.mark.parametrize("seed", [1, 2])
def test_moved_parts_check_equals_the_whole_board_check(seed):
    design = authored(seed)
    board = design.board
    assert board is not None
    windows = _equivalence(seed, design, KicadBackend(), board.footprints[7].id)
    assert 12 <= windows < 36  # most were judged on the cut board, some by the whole-board fallback


def altium_authored(seed: int) -> tuple[Design, DesignRules, bytes]:
    """``authored`` with extruded bodies, two free pads and a copper region of a net, written as an Altium PCB
    document and read back by the Altium import, as ``place --optimize`` reads one: its outline from the
    board's edges, its rules from the document. A room (the rule area the import makes of a room record, which
    the writer keeps only as a record it read) and Altium's keep-out clearance (1 mm, wider than every other
    clearance) are added to the reading. Every footprint's extent is its derived courtyard (change c0489), a
    free pad's the hull of its pad."""
    design = authored(seed, count=26)
    board = design.board
    assert board is not None
    footprints = list(board.footprints)
    free = {footprints[k].component_id for k in (24, 25)}
    for k in (24, 25):  # one-pad parts without a reference: the writer writes them as free pads
        footprints[k] = replace(
            footprints[k], pads=footprints[k].pads[:1], lib_ref="lib:FREE_PAD", side="top"
        )
    for k in range(0, 24, 3):
        fab = "F.Fab" if footprints[k].side == "top" else "B.Fab"
        outline = _rect(-2 * MM, -3 * MM, 4 * MM, 3 * MM)
        body = ComponentBody(id=ident("bdy", k), kind="extruded", height=2 * MM, outline=outline, layer=fab)
        footprints[k] = replace(footprints[k], bodies=(body,))
    region = Graphic(
        id=ident("gra", 990),
        kind="polygon",
        layer="F.Cu",
        points=_rect(2 * MM, 30 * MM, 8 * MM, 36 * MM),
        width=0,
        filled=True,
        net_id=design.circuit.nets[1].id,
    )
    components = tuple(replace(c, ref="") if c.id in free else c for c in design.circuit.components)
    design = replace(
        design,
        circuit=replace(design.circuit, components=components),
        board=replace(board, footprints=tuple(footprints), graphics=(*board.graphics, region)),
    )
    backend = AltiumBackend()
    written = backend.write(design, allow_lossy=True, bodies="extruded")
    name = next(n for n in written.files if n.endswith(".PcbDoc"))
    data = written.files[name]
    read = backend.board_from_bytes(data, file=name).design
    rules = backend.rules_from_bytes(read, data, file=name)
    rings = backend.board_edges(read)
    assert rings and read.board is not None
    outline = Outline(
        id="out_00000000-0000-0000-0000-000000000002",
        points=rings[0].points,
        cutouts=tuple(ring.points for ring in rings[1:]),
        arcs=tuple(
            OutlineArc(i, j, mid) for i, ring in enumerate(rings) for j, mid in enumerate(ring.mids) if mid
        ),
    )
    corner = rings[0].points[0]
    room = Keepout(
        id=ident("kpo", 990),
        provenance=Provenance("altium", name, "0" * 64, f"{LOCATOR}0"),
        outline=_rect(corner.x + 30 * MM, corner.y + 20 * MM, corner.x + 45 * MM, corner.y + 35 * MM),
        layers=("F.Cu",),
        name="PWR",
    )
    clearance = keepout_clearance_rule(
        {"SCOPE1EXPRESSION": "IsKeepOut", "SCOPE2EXPRESSION": "All", "GAP": "1mm"}
    )
    assert clearance is not None and rules.design.rules is not None
    held = replace(rules.design.rules, rules=(*rules.design.rules.rules, clearance))
    board = replace(read.board, outline=outline, keepouts=(*read.board.keepouts, room))
    checked = replace(read, circuit=rules.design.circuit, rules=held, board=board)
    return checked, replace(rules, design=checked), data


def _altium_points(design: Design) -> list[Point]:
    """Points to place a part near in an Altium reading: the outline's and cut-out's corners, the copper
    regions, the polygons' fills, the free pads and the components' keep-outs."""
    board = design.board
    assert board is not None and board.outline is not None
    return [
        *board.outline.points,
        *(p for ring in board.outline.cutouts for p in ring),
        *(g.points[0] for g in board.graphics if g.layer.endswith(".Cu")),
        *(fill.polygon[0] for zone in board.zones for fill in zone.fills),
        *(fp.position for fp in board.footprints if "board_only" in fp.attributes),
        *(placed_keepout(fp, area).outline[0] for fp in board.footprints for area in fp.keepouts),
    ]


@pytest.mark.parametrize("seed", [1, 2])
def test_moved_parts_check_equals_the_whole_board_check_on_an_altium_reading(seed):
    """The same on a board read from an Altium PCB document (follow-up 2026-11-18): free pads, derived
    courtyards, bodies, a component's keep-out, a room, a polygon, a copper region and the keep-out
    clearance; the poses go near each and off the board's edge."""
    design, rules, _ = altium_authored(seed)
    board = design.board
    assert board is not None
    assert sum(1 for fp in board.footprints if "board_only" in fp.attributes) == 2
    assert sum(len(fp.bodies) for fp in board.footprints) == 8 and board.zones and board.holes
    assert {e.source for e in AltiumBackend().placed_extents(design)} == {"derived", "pads"}
    holder = next(fp.id for fp in board.footprints if fp.keepouts)
    windows = _equivalence(seed, design, AltiumBackend(), holder, rules=rules, extra=_altium_points(design))
    assert 12 <= windows < 36


def test_an_altium_part_near_a_free_pad_or_a_components_keepout_gives_the_whole_board_verdicts():
    """A part 0.7 mm from a component's keep-out (within the 1 mm keep-out clearance, beyond the 0.5 mm gap)
    and a part on a free pad: the findings each depends on, as on the whole board."""
    design, rules, _ = altium_authored(1)
    board = design.board
    assert board is not None
    frame = AltiumBackend()
    constraints = PlacementConstraints(gap=500_000, edge_clearance=500_000)
    holder = next(fp for fp in board.footprints if fp.keepouts)
    area = BBox.of_points(placed_keepout(holder, holder.keepouts[0]).outline)
    pad = next(fp for fp in board.footprints if "board_only" in fp.attributes)
    mover = next(
        fp for fp in board.footprints if fp.attributes == ("smd",) and not fp.keepouts and not fp.bodies
    )
    ref = next(c.ref for c in design.circuit.components if c.id == mover.component_id)
    fixed = replace(
        design, board=replace(board, footprints=tuple(f for f in board.footprints if f.id != mover.id))
    )
    check = MovedPartsCheck(fixed, frame, constraints, rules=rules)
    cases = (
        (Point(area.x0 + MM, area.y0 - 1_300_000), "copper:copper.keepout-clearance:" + ref),  # a 1.2 mm pad
        (Point(pad.position.x - 3_300_000, pad.position.y), f"copper:copper.short:{ref}-3, {pad.id}-1"),
    )  # fmt: skip
    for at, expected in cases:
        moved = replace(mover, position=at, rotation=0, side="top")
        footprints = tuple(moved if fp.id == mover.id else fp for fp in board.footprints)
        candidate = replace(design, board=replace(board, footprints=footprints))
        full = check_placement_constraints(candidate, frame, constraints, rules=rules)
        assert any(key.startswith(expected) for key in full.hard), full.hard
        assert verdicts(check(candidate, {mover.id})) == verdicts(full)
    assert check.windows == 2


def test_the_altium_optimizer_evaluations_match_the_whole_board(monkeypatch, tmp_path):
    """``place --optimize`` on the PCB document (``propose_altium``): every evaluation's verdicts are those of
    the whole board's check, and most are judged on a cut board."""
    _, _, data = altium_authored(2)
    document = tmp_path / "moved.PcbDoc"
    document.write_bytes(data)
    read = AltiumBackend().board_from_bytes(data, file=document.name).design
    assert read.board is not None
    movable = tuple(
        fp.id for fp in read.board.footprints if not fp.keepouts and "board_only" not in fp.attributes
    )
    request = OptimizationRequest(
        "fenolite.placement-optimization.v0",
        movable[:3],
        OptimizationBudget(evaluations=12, beam_width=2),
        PlacementConstraints(max_candidates=12, pitch=MM, gap=500_000),
    )
    (tmp_path / "request.json").write_text(canonical.dumps(request), encoding="utf-8")
    judged: list[bool] = []
    windows: list[int] = []
    incremental = MovedPartsCheck.__call__

    def compared(self, design, placed):
        found = incremental(self, design, placed)
        judged.append(verdicts(found) == verdicts(self.full(design)))
        windows.append(self.windows)
        return found

    monkeypatch.setattr(MovedPartsCheck, "__call__", compared)
    result = propose_altium(document, tmp_path / "request.json")
    work = result.result["optimization"]["work"]
    assert work >= 6 and len(judged) == work and all(judged)
    assert windows[-1] > work // 2


def test_a_part_on_another_parts_drills_gives_the_whole_board_verdicts():
    """Two through-hole parts at one pose: duplicate drills, drill overlaps and shorts, as on the whole
    board; the same with a third part already there (a duplicate-drill group grows)."""
    design = authored(5)
    board = design.board
    assert board is not None
    frame = KicadBackend()
    constraints = PlacementConstraints(gap=500_000)
    first, second, third = board.footprints[0], board.footprints[6], board.footprints[12]  # two pads each
    for fixed_ids in ((first.id,), (first.id, third.id)):
        moved = replace(second, position=first.position, rotation=first.rotation, side=first.side)
        footprints = tuple(
            replace(fp, position=first.position, rotation=first.rotation, side=first.side)
            if fp.id in fixed_ids[1:]
            else fp
            for fp in board.footprints
            if fp.id != second.id
        )
        fixed = replace(design, board=replace(board, footprints=footprints))
        candidate = replace(design, board=replace(board, footprints=(*footprints, moved)))
        full = check_placement_constraints(candidate, frame, constraints)
        assert any(key.startswith("duplicate-drill:") for key in full.hard)
        check = MovedPartsCheck(fixed, frame, constraints)
        assert verdicts(check(candidate, {second.id})) == verdicts(full)


def test_the_optimizer_judges_only_the_parts_near_the_moved_one(monkeypatch, tmp_path):
    """Each evaluation checks a board cut to the parts near the moved one, not the whole board: without the
    incremental check every evaluation sees all 30 parts."""
    design = authored(3, count=30)
    board = design.board
    assert board is not None
    path = tmp_path / "moved.kicad_pcb"
    loose = replace(
        design, rules=None, board=replace(board, holes=(), tracks=(), vias=())
    )  # nothing attached
    path.write_text(write_board(loose, target=10).text, encoding="utf-8")
    path.with_suffix(".kicad_dru").write_text(
        "(version 1)\n(rule supplied (constraint clearance (min 0.2mm)))\n", encoding="utf-8"
    )
    read = read_board(path)
    assert read.board is not None
    read = replace(read, board=replace(read.board, outline=board.outline))
    movable = read.board.footprints[13]
    seen: list[int] = []
    check_copper = placement_checks.check_copper

    def counted(design, **kwargs):
        assert design.board is not None
        seen.append(len(design.board.footprints))
        return check_copper(design, **kwargs)

    monkeypatch.setattr(placement_checks, "check_copper", counted)
    request = OptimizationRequest(
        "fenolite.placement-optimization.v0",
        (movable.id,),
        OptimizationBudget(evaluations=6, beam_width=2),
        PlacementConstraints(max_candidates=6, pitch=MM),
    )
    result = propose(read, path, request, frozenset())
    assert result.work == 6
    assert seen[:2] == [30, 29]  # the board before, then the fixed parts once
    assert seen[2:] and max(seen[2:]) < 12, seen
