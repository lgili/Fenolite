# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The optimizer's check of the moved parts only gives the whole board's verdicts (change c0487, follow-up
2026-11-17)."""

import random
from collections import Counter
from dataclasses import replace

import pytest
from _coppercheck import Copper, disc_entry, ident

import fenolite.cli.placement_checks as placement_checks
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.cli.place_optimize import propose
from fenolite.cli.placement_checks import MovedPartsCheck, check_placement_constraints
from fenolite.core.coords import Point
from fenolite.model.board import Graphic, Hole, Keepout, Outline
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


def _pose(rng: random.Random, design: Design) -> Point:
    """Anywhere, on the edge, or next to a part, a hole, a rule area or a drill."""
    board = design.board
    assert board is not None
    near = [
        *(fp.position for fp in board.footprints),
        *(hole.position for hole in board.holes),
        *(area.outline[0] for area in board.keepouts),
        Point(0, rng.randrange(H)),
        Point(W, rng.randrange(H)),
        Point(22 * MM, 30 * MM),
    ]
    if rng.random() < 0.3:
        return Point(rng.randrange(-2 * MM, W + 2 * MM), rng.randrange(-2 * MM, H + 2 * MM))
    at = rng.choice(near)
    return Point(at.x + rng.randrange(-3 * MM, 3 * MM), at.y + rng.randrange(-3 * MM, 3 * MM))


@pytest.mark.parametrize("seed", [1, 2])
def test_moved_parts_check_equals_the_whole_board_check(seed):
    rng = random.Random(seed)
    design = authored(seed)
    board = design.board
    assert board is not None
    frame = KicadBackend()
    constraints = PlacementConstraints(gap=500_000, edge_clearance=500_000)
    windows = 0
    for round in range(3):
        movable = set(rng.sample([fp.id for fp in board.footprints], rng.randint(1, 3)))
        if round == 0:
            movable.add(board.footprints[7].id)  # it holds a rule area: the whole board is checked
        fixed = replace(
            design, board=replace(board, footprints=tuple(f for f in board.footprints if f.id not in movable))
        )
        check = MovedPartsCheck(fixed, frame, constraints)
        assert verdicts(check(fixed, set())) == verdicts(
            check_placement_constraints(fixed, frame, constraints)
        )
        for _ in range(12):
            placed = {ident for ident in movable if rng.random() < 0.8} or movable
            footprints = tuple(
                replace(
                    fp,
                    position=_pose(rng, design),
                    rotation=rng.choice((0, 90_000_000, 180_000_000, 270_000_000, 45_000_000, 30_500_000)),
                    side=rng.choice(("top", "bottom")),
                )
                if fp.id in placed
                else fp
                for fp in board.footprints
                if fp.id not in movable or fp.id in placed
            )
            candidate = replace(design, board=replace(board, footprints=footprints))
            full = check_placement_constraints(candidate, frame, constraints)
            assert verdicts(check(candidate, placed)) == verdicts(full)
        windows += check.windows
    assert 12 <= windows < 36  # most were judged on the cut board, some by the whole-board fallback


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
