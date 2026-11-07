# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The placement precedence with an injected resolver (change c0255; capability layout-lens, "Placement
precedence": "A relative request on a fresh build", "A request wins over the strategy" and the rounds of
``resolving``)."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.coords import Point
from fenolite.dsl import Design, block, mm, placements, row, to_model
from fenolite.dsl.convert import BOARD_ORIGIN
from fenolite.dsl.relative import block_layouts, frames, relative_requests, top_layout, turns
from fenolite.geometry.shapes import BBox
from fenolite.lens.preserve import (
    CodePlacement,
    KeptPlacement,
    LayoutMatch,
    Placed,
    PlacementLike,
    effective_placements,
    resolving,
)
from fenolite.placement.relative import Absolute, Footprint, Scene, resolve

MM = 1_000_000
CHIP = Footprint(BBox(-2 * MM, -MM, 2 * MM, MM))


def _resolver(design: Design):  # type: ignore[no-untyped-def]
    absolute = {
        path: Absolute(p.request.x, p.request.y, p.request.rotation, p.request.side, p.request.locked)
        for path, p in design.parts.items()
        if p.request is not None
    }
    scene = Scene(
        footprints={path: CHIP for path in design.parts},
        frames={key: items.items for key, items in frames(design).items()},
        absolute=absolute,
        relative=relative_requests(design),
        turns=turns(design),
        blocks=block_layouts(design),
        origin=BOARD_ORIGIN,
        top=top_layout(design),
    )

    def run(fixed: Mapping[str, PlacementLike]) -> Mapping[str, PlacementLike]:
        from fenolite.placement.relative import Placed as Held

        held = {path: Held(p.at, p.rotation, p.side) for path, p in fixed.items()}
        found = resolve(scene, held)
        return {
            path: CodePlacement(r.at, r.rotation, r.side, r.locked, staged=r.staged)  # type: ignore[arg-type]
            for path, r in found.placements.items()
        }

    return run


def test_a_relative_request_on_a_fresh_build() -> None:
    design = Design("fresh")
    design.board(mm(40), mm(30))
    u1 = design.part("U1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="1u")
    c5 = design.part("C5", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="1u")
    u1.place(mm(14), mm(15))
    c5.place(right_of=u1, gap=mm(1))
    found, issues = effective_placements(
        placements(design), LayoutMatch(MappingProxyType({})), design=to_model(design), board=None,
        resolver=_resolver(design),
    )  # fmt: skip
    assert not issues
    assert found["C5"].at == Point(BOARD_ORIGIN.x + 19 * MM, BOARD_ORIGIN.y + 15 * MM)
    assert found["U1"].at == Point(BOARD_ORIGIN.x + 14 * MM, BOARD_ORIGIN.y + 15 * MM)


def test_a_request_wins_over_the_strategy() -> None:
    design = Design("strategy")
    design.board(mm(40), mm(30))

    @block
    def grouped(b):  # type: ignore[no-untyped-def]
        r1 = b.part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
        c1 = b.part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="1u")
        c1.place(below=r1)
        b.layout(row())

    design.use(grouped, "g").place(mm(5), mm(5))
    found, _ = effective_placements(
        placements(design), LayoutMatch(MappingProxyType({})), design=to_model(design), board=None,
        resolver=_resolver(design),
    )  # fmt: skip
    r1, c1 = found["g/R1"], found["g/C1"]
    assert r1.at == Point(BOARD_ORIGIN.x + 7 * MM, BOARD_ORIGIN.y + 6 * MM)
    assert c1.at == Point(r1.at.x, r1.at.y + 2 * MM)


def test_resolving_rounds_follow_the_decided_reference() -> None:
    design = Design("rounds")
    design.board(mm(40), mm(30))
    u1 = design.part("U1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="1u")
    c5 = design.part("C5", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="1u")
    u1.place(mm(14), mm(15))
    c5.place(right_of=u1, gap=mm(1))
    moved = KeptPlacement(Point(BOARD_ORIGIN.x + 14 * MM, BOARD_ORIGIN.y + 20 * MM), 0, "top", False)
    rounds: list[Mapping[str, PlacementLike]] = []

    def decide(code: Mapping[str, PlacementLike]) -> Placed:
        rounds.append(code)
        return Placed(MappingProxyType({**code, "U1": moved}))

    placed = resolving(placements(design), _resolver(design), decide)
    assert len(rounds) == 2
    assert placed.placements["C5"].at == Point(BOARD_ORIGIN.x + 19 * MM, BOARD_ORIGIN.y + 20 * MM)
    assert resolving(placements(design), None, decide).placements["U1"] == moved
