# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.reuse.copy_copper`` and the settling of the copy by ``cli.reuse_copper`` (change c0210;
capability layout-reuse, "Copper of a copied block"), on the authored boards of ``tests/_reusebench.py``.
Hermetic."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from _groundties import _p, _via
from _reusebench import DEFINITIONS, POUR, layout, reference, target, with_zones, y_up
from _ties import MM

from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.layers import created_layers
from fenolite.checks.copper import check_copper
from fenolite.cli.reuse_copper import (
    Settled,
    apply_fit,
    block_items,
    landed,
    misplaced,
    settle_copper,
    zone_pads,
)
from fenolite.core.coords import Point
from fenolite.geometry.polygon import area2
from fenolite.model.board import Board, Track, Via, Zone
from fenolite.model.design import Design
from fenolite.reuse import REBUILT, CopiedItem, CopperCopy, Layout, copy_copper, fit_block, layer_map
from fenolite.tidy import Clash
from fenolite.tidy.graph import groups, net_pieces

BLOCK = ("U1", "R1", "R2", "R3", "R4")


def check(design: Design) -> Sequence[Clash]:
    report = check_copper(design, pads=board_pads(design))
    return [
        Clash(found.code, found.layer, tuple(sorted({item.entity_id for item in found.items})), found.gap)
        for found in report.findings
    ]


def _ids(design: Design) -> dict[str, str]:
    """The id of each reference track by its label in ``tests/_reusebench.py``."""
    assert design.board is not None
    labels = ("in", "out", "tail", "down")
    return {label: track.id for label, track in zip(labels, design.board.tracks, strict=True)}


def _copied(
    source: Design, onto: Design, *, drawn: Layout | None = None
) -> tuple[Design, CopperCopy, Layout]:
    """The target with the block placed, the copy of the block's copper, and the placed layout."""
    ref = drawn or layout(source)
    fit = fit_block(ref, layout(onto), BLOCK)
    moved = apply_fit(onto, fit, definitions=DEFINITIONS)
    placed = layout(moved.design)
    assert misplaced(fit, placed.pads, moved=moved.moved) == []
    return moved.design, copy_copper(fit, ref, placed, items=block_items(ref, fit)), placed


def _ends(track: Track) -> set[Point]:
    return {track.start, track.end}


def test_copper_that_ends_nowhere_is_pruned() -> None:
    """Scenario "Copper that ends nowhere is pruned": ``tail`` runs to ``TP1``, which is not copied, so it
    is not written and is named with ``free-end``; the lead ``down`` and its via, which nothing joins on
    ``B.Cu``, go too; ``in`` and ``out`` stay, locked, on their pads."""
    source = reference()
    ids = _ids(source)
    placed, copy, after = _copied(source, target())
    assert sorted(held.source for held in copy.items) == sorted([*ids.values(), source.board.vias[0].id])  # type: ignore[union-attr]
    settled = settle_copper(placed, copy, pads=after.pads, check=check)
    assert settled.issues == ()
    assert [held.source for held in settled.kept] == [ids["in"], ids["out"]]
    reasons = {dropped.item: dropped.reason for dropped in settled.dropped}
    assert reasons == {
        ids["tail"]: "free-end",
        ids["down"]: "free-end",
        source.board.vias[0].id: "via-under-two-layers",  # type: ignore[union-attr]
    }
    tail = next(dropped for dropped in settled.dropped if dropped.item == ids["tail"])
    assert (tail.kind, tail.net) == ("track", "OUT")
    board = settled.design.board
    assert board is not None
    kept = [track for track in board.tracks if track.id in {held.item.id for held in settled.kept}]
    assert all(track.locked for track in kept) and len(kept) == 2
    pads = {(record.ref, record.number): record.position for record in board_pads(settled.design)}
    assert _ends(kept[0]) == {pads[("U1", "1")], pads[("R1", "1")]}
    assert _ends(kept[1]) == {pads[("U1", "4")], pads[("R2", "1")]}
    assert check(settled.design) == []


def test_the_copy_of_a_y_up_reference() -> None:
    """The copper of the reference drawn with the Y axis up lands on the same pads."""
    source = reference()
    placed, copy, after = _copied(source, target(), drawn=y_up(layout(source)))
    settled = settle_copper(placed, copy, pads=after.pads, check=check)
    plain = settle_copper(*_copied(source, target())[:2], pads=after.pads, check=check)
    assert [_ends(held.item) for held in settled.kept] == [_ends(held.item) for held in plain.kept]  # type: ignore[arg-type]


def test_a_flipped_block_flips_its_layers() -> None:
    """With the anchor on the bottom the copy lies on ``B.Cu``, joined to the bottom pads."""
    source = reference()
    placed, copy, after = _copied(source, target(anchor_side="bottom"))
    settled = settle_copper(placed, copy, pads=after.pads, check=check)
    assert len(settled.kept) == 2
    assert {held.item.layer for held in settled.kept} == {"B.Cu"}  # type: ignore[union-attr]
    assert check(settled.design) == []
    pads = {(record.ref, record.number): record for record in board_pads(settled.design)}
    first, second = (held.item for held in settled.kept)
    assert isinstance(first, Track) and isinstance(second, Track)
    assert _ends(first) == {pads[("U1", "1")].position, pads[("R1", "1")].position}
    assert _ends(second) == {pads[("U1", "4")].position, pads[("R2", "1")].position}
    assert {pads[("U1", "1")].side, pads[("R1", "1")].side} == {"bottom"}


def test_layer_map() -> None:
    two, four = Board(id="brd_1", layers=created_layers(2)), Board(id="brd_2", layers=created_layers(4))
    assert layer_map(four, four, flipped=False) == {n: n for n in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")}
    assert layer_map(four, four, flipped=True) == {
        "F.Cu": "B.Cu", "In1.Cu": "In2.Cu", "In2.Cu": "In1.Cu", "B.Cu": "F.Cu",
    }  # fmt: skip
    assert layer_map(four, two, flipped=False) == {"F.Cu": "F.Cu", "B.Cu": "B.Cu"}


def test_a_net_claimed_by_two_target_nets() -> None:
    """``R2-2`` on ``GND2`` in the target: the reference ``GND`` maps to two nets, so its copper is left
    out with ``net-ambiguous``."""
    onto = target()
    assert onto.board is not None
    gnd2 = dataclasses.replace(
        onto.circuit.nets[0], id="net_00000000-0000-4000-8000-000000000099", name="GND2"
    )
    circuit = dataclasses.replace(onto.circuit, nets=(*onto.circuit.nets, gnd2))
    r2 = next(fp for fp in onto.board.footprints if fp.component_id == onto.circuit.components[2].id)
    pads = tuple(dataclasses.replace(pad, net_id=gnd2.id) if pad.number == "2" else pad for pad in r2.pads)
    footprints = tuple(
        dataclasses.replace(fp, pads=pads) if fp.id == r2.id else fp for fp in onto.board.footprints
    )
    onto = dataclasses.replace(
        onto, circuit=circuit, board=dataclasses.replace(onto.board, footprints=footprints)
    )
    source = reference()
    _, copy, _ = _copied(source, onto)
    ambiguous = [dropped for dropped in copy.dropped if dropped.reason == "net-ambiguous"]
    assert sorted(dropped.kind for dropped in ambiguous) == ["track", "via"]
    assert all(dropped.net == "GND" and "GND2" in dropped.detail for dropped in ambiguous)


def test_an_island_goes() -> None:
    """A loop of two vias and two tracks that touches no pad survives pruning; it is an island."""
    placed = target()
    gnd = next(net.id for net in placed.circuit.nets if net.name == "GND")
    loop: list[Track | Via] = [
        _via(7, gnd, _p(30, 5)),
        _via(8, gnd, _p(34, 5)),
        Track(
            id="trk_00000000-0000-4000-8000-000000000071",
            start=_p(30, 5),
            end=_p(34, 5),
            width=MM // 4,
            layer="F.Cu",
            net_id=gnd,
        ),
        Track(
            id="trk_00000000-0000-4000-8000-000000000072",
            start=_p(30, 5),
            end=_p(34, 5),
            width=MM // 4,
            layer="B.Cu",
            net_id=gnd,
        ),
    ]
    copy = CopperCopy(tuple(CopiedItem(item, f"src{n}", "GND") for n, item in enumerate(loop)), {"x": gnd})
    settled = settle_copper(placed, copy, pads=board_pads(placed), check=check)
    assert settled.kept == ()
    assert sorted(dropped.reason for dropped in settled.dropped) == ["island"] * 4


def test_copper_that_clashes_is_left_out() -> None:
    """A part of another net on the target where ``in`` would run: ``in`` is left out with the copper
    check's code, and nothing else is."""
    source = reference()
    ids = _ids(source)
    placed, copy, after = _copied(source, target(intruder=True))
    assert check(placed) == []
    settled = settle_copper(placed, copy, pads=after.pads, check=check)
    assert [held.source for held in settled.kept] == [ids["out"]]
    reasons = {dropped.item: dropped.reason for dropped in settled.dropped}
    assert reasons[ids["in"]] in ("copper.short", "copper.clearance")
    assert check(settled.design) == []


def _zoned(source: Design, onto: Design) -> Settled:
    """The block of ``source`` copied with its zones onto ``onto`` and settled."""
    ref = layout(source)
    fit = fit_block(ref, layout(onto), BLOCK)
    moved = apply_fit(onto, fit, definitions=DEFINITIONS)
    placed = layout(moved.design)
    copy = copy_copper(fit, ref, placed, items=block_items(ref, fit), zones=zone_pads(ref))
    images = {source_id: record.pad_id for source_id, record in landed(fit, placed.pads).items()}
    return settle_copper(moved.design, copy, pads=placed.pads, check=check, images=images)


def _zone_pads(design: Design, zone: Zone) -> set[tuple[str, str]]:
    """The pads (reference, number) in the group of the fill of ``zone`` on ``design``."""
    records = board_pads(design)
    assert zone.net_id is not None
    pieces = net_pieces(design, records).pieces[zone.net_id]
    roots = groups(pieces)
    root = roots[f"{zone.id}#0"]
    held = {piece.ident for piece in pieces if piece.kind == "pad" and roots[piece.ident] == root}
    return {(record.ref, record.number) for record in records if record.pad_id in held}


def _zones(settled: Settled) -> list[CopiedItem]:
    return [held for held in settled.kept if isinstance(held.item, Zone)]


def test_a_zone_copied_with_the_block() -> None:
    """Scenario "A zone copied with the block": the ``GND`` pour joins ``R1-2`` and ``R2-2`` and is copied
    onto their images, locked; the ``OUT`` strip also joins ``TP1`` and is ``zone-beyond-block``."""
    settled = _zoned(with_zones(reference()), target())
    (pour,) = _zones(settled)
    assert pour.source == "zon_00000000-0000-4000-8000-000000000001"
    assert isinstance(pour.item, Zone) and pour.item.locked and pour.detail == ""
    assert _zone_pads(settled.design, pour.item) == {("R1", "2"), ("R2", "2")}
    reasons = {dropped.item: dropped.reason for dropped in settled.dropped if dropped.kind == "zone"}
    assert reasons == {"zon_00000000-0000-4000-8000-000000000002": "zone-beyond-block"}
    assert settled.issues == () and check(settled.design) == []


def test_a_zone_read_without_its_outline() -> None:
    """Scenario "A zone read without its outline": the copy gets the image of the fill as its outline,
    says so, joins the ground pads, the tracks are still copied, and the copper check finds nothing
    new."""
    settled = _zoned(with_zones(reference(), outline=False), target())
    (pour,) = _zones(settled)
    assert isinstance(pour.item, Zone) and pour.detail == REBUILT
    assert pour.item.outline == pour.item.fills[0].polygon and len(pour.item.outline) == len(POUR)
    assert _zone_pads(settled.design, pour.item) == {("R1", "2"), ("R2", "2")}
    assert len([held for held in settled.kept if not isinstance(held.item, Zone)]) == 2
    assert settled.issues == () and check(settled.design) == []


def test_a_flipped_zone_keeps_its_winding() -> None:
    """With the anchor on the bottom the pour lies on ``B.Cu`` and its rings keep their winding."""
    settled = _zoned(with_zones(reference()), target(anchor_side="bottom"))
    (pour,) = _zones(settled)
    assert isinstance(pour.item, Zone) and pour.item.layers == ("B.Cu",)
    assert pour.item.fills[0].layer == "B.Cu"
    assert area2(pour.item.outline) * area2(POUR) > 0
    assert check(settled.design) == []


def test_a_zone_that_loses_a_pad_goes() -> None:
    """A copied zone whose group lacks the image of one of its pads goes as ``pad-lost``."""
    settled = _zoned(with_zones(reference()), target())
    (pour,) = _zones(settled)
    assert isinstance(pour.item, Zone)
    lost = dataclasses.replace(
        pour, item=dataclasses.replace(pour.item, locked=False), joins=(*pour.joins, "pad_missing")
    )
    fit = fit_block(layout(reference()), layout(target()), BLOCK)
    placed = apply_fit(target(), fit, definitions=DEFINITIONS).design
    records = board_pads(placed)
    images = {source_id: record.pad_id for source_id, record in landed(fit, records).items()}
    again = settle_copper(placed, CopperCopy((lost,), {}), pads=records, check=check, images=images)
    assert again.kept == ()
    assert [(dropped.reason, dropped.kind) for dropped in again.dropped] == [("pad-lost", "zone")]


def test_an_unfilled_zone_is_named() -> None:
    """A zone of a block net without a fill whose outline's box holds a paired pad is ``zone-unfilled``."""
    source = with_zones(reference())
    assert source.board is not None
    zones = tuple(dataclasses.replace(zone, fills=(), filled=False) for zone in source.board.zones)
    source = dataclasses.replace(source, board=dataclasses.replace(source.board, zones=zones))
    settled = _zoned(source, target())
    reasons = sorted(dropped.reason for dropped in settled.dropped if dropped.kind == "zone")
    assert reasons == ["zone-unfilled", "zone-unfilled"]
