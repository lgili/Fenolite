# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Keep-out primitives on copper and polygon cut-outs of a PCB document are rule areas, never copper
(change c0407; ``pcb-records.md``, "Regions and keep-outs")."""

from __future__ import annotations

import dataclasses
import hashlib

import _altium_keepouts as cases
import _altium_records as rec
import pytest

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import Prefix
from fenolite.core.coords import Point
from fenolite.geometry import area2
from fenolite.model.board import Board, Keepout

MM = 1_000_000
MIL = rec.MIL


def _document() -> Board:
    data = cases.keepout_document()
    design = import_board(read_pcbdoc(data), file="keepouts.PcbDoc", sha256=hashlib.sha256(data).hexdigest())
    assert design.board is not None
    return design.board


def _board(**parts: object) -> Board:
    document = rec.document(rec.board((1, 32)), **parts)  # type: ignore[arg-type]
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA)
    assert design.board is not None
    return design.board


def _flag(item: object) -> object:
    prefix: Prefix = item.prefix  # type: ignore[attr-defined]
    return dataclasses.replace(item, prefix=dataclasses.replace(prefix, flags2=2))  # type: ignore[type-var]


def _kind(region: object, *fields: tuple[str, str]) -> object:
    return dataclasses.replace(region, properties=rec.props(fields))  # type: ignore[type-var]


def _restrictions(area: Keepout) -> tuple[bool, bool, bool, bool]:
    return (area.no_tracks, area.no_vias, area.no_pads, area.no_copper_pour)


def _span(area: Keepout) -> tuple[int, int]:
    xs, ys = [p.x for p in area.outline], [p.y for p in area.outline]
    return max(xs) - min(xs), max(ys) - min(ys)


def test_a_polygon_cut_out_on_copper_is_a_pour_keep_out() -> None:
    """B2: the ``KIND=1`` region on Top without a net is no copper; it is one rule area on ``F.Cu`` that
    forbids poured copper alone, as KiCad 10.0.6 imports it."""
    board = _document()
    assert not [g for g in board.graphics if g.layer.endswith(".Cu")]
    assert not board.tracks
    cutouts = [k for k in board.keepouts if _restrictions(k) == (False, False, False, True)]
    (cutout,) = cutouts
    assert cutout.layers == ("F.Cu",) and len(cutout.outline) == 4
    assert all(abs(side - 10 * MM) <= 2 for side in _span(cutout))  # whole units and back: 1.27 nm each way


def test_a_keep_out_track_on_copper_is_a_band_keep_out() -> None:
    """B4: the keep-out track on Top is no copper track; it is the rule area of the band its 0.5 mm width
    covers, on ``F.Cu`` alone, with every restriction (KiCad: tracks, vias, pads and pours not allowed)."""
    board = _document()
    bands = [k for k in board.keepouts if _restrictions(k) == (True, True, True, True)]
    (band,) = bands
    assert band.layers == ("F.Cu",)
    length, width = _span(band)
    assert abs(length - (40 * MM + cases.LINE_WIDTH)) <= 4 and abs(width - cases.LINE_WIDTH) <= 4
    assert area2(band.outline) > 0


def test_keep_out_tracks_on_the_keep_out_layer_stay_drawings() -> None:
    """The ring on the Keep-Out layer stays four lines on ``Altium.KeepOut``: ``convert`` makes the rule
    areas (``test_to_kicad``)."""
    board = _document()
    lines = [g for g in board.graphics if g.layer == "Altium.KeepOut"]
    assert [g.kind for g in lines] == ["line"] * 4
    assert all(abs(g.width - cases.RING_WIDTH) <= 2 for g in lines)


@pytest.mark.parametrize(
    ("layer", "layers"), [(56, ("F.Cu", "B.Cu")), (74, ("F.Cu", "B.Cu")), (32, ("B.Cu",))]
)
def test_a_polygon_cut_out_keeps_pours_off_where_kicad_does(layer: int, layers: tuple[str, ...]) -> None:
    """A polygon cut-out on the Keep-Out or the Multi-Layer layer keeps pours off every copper layer; on a
    copper layer, off that layer (KiCad 10.0.6, measured with ``_altium_slotcases`` on 2026-11-05)."""
    square = [(0, 0), (100 * MIL, 0), (100 * MIL, 100 * MIL), (0, 100 * MIL)]
    region = _kind(rec.region(square, layer=layer), ("KIND", "1"))
    board = _board(regions=[region])
    (area,) = board.keepouts
    assert area.layers == layers and _restrictions(area) == (False, False, False, True)
    assert not [g for g in board.graphics if g.layer != "Edge.Cuts"]


def test_keep_out_arc_fill_and_region_on_copper() -> None:
    """A keep-out arc gives the band of its width, a full circle two half bands, a fill and a region their
    outline; a region holds its restrictions (3: tracks and vias), the others every restriction."""
    square = [(0, 0), (100 * MIL, 0), (100 * MIL, 100 * MIL), (0, 100 * MIL)]
    region = _kind(_flag(rec.region(square, layer=32)), ("KIND", "0"), ("KEEPOUTRESTRICTIONS", "3"))
    board = _board(
        arcs=[
            _flag(rec.arc((0, 0), 100 * MIL, 0.0, 180.0, width=20 * MIL)),
            _flag(rec.arc((500 * MIL, 0), 50 * MIL, 0.0, 360.0, width=10 * MIL, layer=32)),
        ],
        fills=[_flag(rec.fill((0, 0), (50 * MIL, 50 * MIL), layer=1))],
        regions=[region],
    )
    assert not board.arcs and not [g for g in board.graphics if g.layer != "Edge.Cuts"]
    half, *circle, fill, area = board.keepouts
    assert half.layers == ("F.Cu",) and _restrictions(half) == (True, True, True, True)
    # 100 mil radius, 20 mil wide: 220 mil across; 110 mil above the centre line, 10 mil below (round ends)
    across, tall = _span(half)
    assert abs(across - 220 * 25_400) <= 4 and abs(tall - 120 * 25_400) <= 4
    assert len(circle) == 2 and all(k.layers == ("B.Cu",) for k in circle)
    assert fill.layers == ("F.Cu",) and len(fill.outline) == 4
    assert area.layers == ("B.Cu",) and _restrictions(area) == (True, True, False, False)


def test_a_keep_out_of_a_component_is_a_board_keep_out() -> None:
    """A keep-out track of a component on copper is no copper of its footprint: it is a rule area of the
    board, in the board's frame."""
    component = rec.component("U1", x="500mil", y="500mil")
    track = _flag(rec.track((400 * MIL, 500 * MIL), (600 * MIL, 500 * MIL), component=0))
    board = _board(components=[component], tracks=[track])
    (footprint,) = board.footprints
    assert not [g for g in footprint.graphics if g.layer.endswith(".Cu")]
    (band,) = board.keepouts
    assert band.layers == ("F.Cu",)
    xs = [p.x for p in band.outline]
    assert abs(min(xs) - (400 * 25_400 - 5 * 25_400)) <= 2


def test_copper_without_the_flag_stays_copper() -> None:
    board = _board(nets=["A"], tracks=[rec.track((0, 0), (100 * MIL, 0), net=0)])
    assert len(board.tracks) == 1 and not board.keepouts
    assert Point(0, 0) == board.tracks[0].start
