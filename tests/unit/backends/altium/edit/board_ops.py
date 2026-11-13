# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The test boards of change c0497, authored for Fenolite from the Part J kit board (``conftest.kit_board``):
each a function of the kit board's bytes that gives a new document, written with the edit state.

- ``drawn``: the outline turned into four lines and one arc corner (centre (35, 25) mm, radius 5 mm), drawn
  on Mechanical 1 by 5 tracks (one edge in two pieces) and 1 arc; one free board cut-out (5, 10)–(7, 12) mm,
  drawn there too (4 tracks); one keep-out region (25, 20)–(28, 23) mm; one polygon cut-out on the Bottom
  Layer (30, 8)–(32, 10) mm; one planted pour piece each for ``GND`` and ``VIN``;
- ``vias``: nine vias added to the three of the kit, six on ``GND`` and six on ``VIN``, in the four tenting
  states, some with bits 2 and 7 of the flags byte set;
- ``texts``: ``R1`` flipped to the bottom, ``D1`` with position-mode keys, and the free text ``REV A`` on
  Top Overlay and on Bottom Overlay.

Every value is a round number chosen here."""

from __future__ import annotations

from fenolite.backends.altium import edit
from fenolite.backends.altium.docboard import angle_text
from fenolite.backends.altium.edit import drawing, ops
from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.edit.ops import View
from fenolite.backends.altium.edit.state import WIDE, State
from fenolite.backends.altium.pcbrecords import (
    KEEPOUT_LAYER,
    cutout_region,
    mil_text,
    polygon_region,
    region_record,
    to_units,
)
from fenolite.backends.altium.read.pcbprims import ARC, TEXT, TRACK
from tests.unit.backends.altium.edit.conftest import mm

MECHANICAL_1, BOTTOM_LAYER, TOP_LAYER = 57, 32, 1
TOP_OVERLAY, BOTTOM_OVERLAY = 33, 34
CUTOUT = ((5, 10), (7, 10), (7, 12), (5, 12))
KEEPOUT = ((25, 20), (28, 20), (28, 23), (25, 23))
POLYGON_CUTOUT = ((30, 8), (32, 8), (32, 10), (30, 10))
CORNER = (35, 25)
"""The centre of the outline's arc corner, mm, radius 5 mm."""


def _units(view: View, points: tuple[tuple[float, float], ...]) -> list[tuple[int, int]]:
    return [view.units((mm(x), mm(y))) for x, y in points]


def _outline(state: State, view: View) -> None:
    """(0, 0) → (40, 0) → (40, 25), an arc counter-clockwise about (35, 25) to (35, 30), → (0, 30)."""
    corners = _units(view, ((0, 0), (40, 0), (40, 25), (35, 30), (0, 30)))
    cx, cy = view.units((mm(CORNER[0]), mm(CORNER[1])))
    arc = {"KIND": "1", "CX": mil_text(cx), "CY": mil_text(cy), "SA": angle_text(0),
           "EA": angle_text(90_000_000), "R": mil_text(to_units(mm(5)))}  # fmt: skip
    vertices = [(x, y, arc if n == 2 else None) for n, (x, y) in enumerate(corners)]
    raw = state.properties("Board6")[0].raw
    state.replace("Board6", 0, ops._with_board_outline(raw, vertices))  # pyright: ignore[reportPrivateUsage]


def _free(state: State, storage: str, kind: int) -> bytes:
    """A record of ``kind`` made free and put on Mechanical 1, without net."""
    raw = next(r for r in state.get(storage) if r[0] == kind)
    raw = rec.set_prefix(raw, net=rec.NO_INDEX, polygon=rec.NO_INDEX, component=rec.NO_INDEX)
    return ops.relayer(raw, MECHANICAL_1)


def _draw(state: State, width: int = mm(0.1)) -> None:
    """The board shape drawn on Mechanical 1, the first line edge in two collinear pieces."""
    track, arc = _free(state, "Tracks6", TRACK), _free(state, "Arcs6", ARC)
    split = False
    for edge in drawing.board_shape(state):
        if edge.centre is not None:
            raw = rec.patch(arc, 13, "<3i", *map(round, (*edge.centre, edge.radius)))
            state.append("Arcs6", rec.patch(rec.patch(raw, 25, "<2d", edge.start, edge.end), 41, "<i", width))
            continue
        a, b = (round(edge.a[0]), round(edge.a[1])), (round(edge.b[0]), round(edge.b[1]))
        pieces = [(a, b)]
        if not split:
            middle = ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2)
            pieces, split = [(a, middle), (middle, b)], True
        for p, q in pieces:
            state.append("Tracks6", rec.patch(track, 13, "<5i", *p, *q, width))


def _region(state: State, plain: bytes, shaped: bytes) -> None:
    state.append("Regions6", plain)
    state.append("ShapeBasedRegions6", shaped)


def drawn(data: bytes) -> bytes:
    state = State.of(data)
    view = View(state)
    _outline(state, view)
    ring = _units(view, CUTOUT)
    _region(state, cutout_region(ring), cutout_region(ring, shape_based=True))
    ring = _units(view, KEEPOUT)
    keepout = region_record(KEEPOUT_LAYER, ring, keepout=1)
    _region(state, keepout, region_record(KEEPOUT_LAYER, ring, keepout=1, shape_based=True))
    ring = _units(view, POLYGON_CUTOUT)
    _region(state, region_record(BOTTOM_LAYER, ring, polygon_cutout=True),
            region_record(BOTTOM_LAYER, ring, polygon_cutout=True, shape_based=True))  # fmt: skip
    for polygon, layer, box in ((0, BOTTOM_LAYER, ((20, 14), (24, 14), (24, 16), (20, 16))),
                                (1, TOP_LAYER, ((3, 23), (5, 23), (5, 25), (3, 25)))):  # fmt: skip
        ring = _units(view, box)
        for shaped, storage in ((False, "Regions6"), (True, "ShapeBasedRegions6")):
            piece = polygon_region(layer, ring, (), polygon=polygon, piece=0, arc_resolution="0.5mil",
                                   shape_based=shaped)  # fmt: skip
            state.append(storage, piece)
    _draw(state)
    return state.data()


VIA_STATES = ((0x0C, None), (0x2C, 0.05), (0x4C, None), (0x6C, -0.05), (0x8C, 0.1), (0xEC, None))
"""The first flags byte and the solder-mask expansion (mm, ``None``: the template's) of each added via."""


def vias(data: bytes) -> bytes:
    state = State.of(data)
    view = View(state)
    template = state.get("Vias6")[0]
    gnd, vin = view.net_index("GND"), view.net_index("VIN")
    held = [rec.prefix_of(raw)[1] for raw in state.get("Vias6")]
    plan = [gnd] * (6 - held.count(gnd)) + [vin] * (6 - held.count(vin))
    for number, net in enumerate(plan):
        flags, expansion = VIA_STATES[number % len(VIA_STATES)]
        raw = rec.set_prefix(template, net=net)
        raw = rec.patch(raw, 13, "<2i", *view.units((mm(30 + 2 * (number % 4)), mm(14 + 2 * (number // 4)))))
        raw = rec.patch(raw, 1, "<B", flags)
        if expansion is not None:
            raw = rec.patch(
                rec.patch(raw, 54, "<i", to_units(mm(expansion))), 242, "<i", to_units(mm(expansion))
            )
            raw = rec.patch(raw, 66, "<B", 2)
        state.append("Vias6", raw)
    return state.data()


def _free_text(state: State, view: View, text: str, at: tuple[float, float], layer: int) -> None:
    source = next(r for r in state.get("Texts6") if r[0] == TEXT and rec.prefix_of(r)[3] == rec.NO_INDEX)
    index = max(state.wide(), default=-1) + 1
    state.append(WIDE, rec.wide_entry(index, text))
    raw = rec.set_text_string(rec.set_wide_index(source, index), text)
    raw = rec.patch(raw, 13, "<2i", *view.units((mm(at[0]), mm(at[1]))))
    raw = ops.relayer(raw, layer)
    state.append("Texts6", rec.patch(raw, 35, "<B", 1 if layer == BOTTOM_OVERLAY else 0))


def texts(data: bytes, folder: object) -> bytes:
    """``folder`` is a ``Path`` to write the flipped board through a session."""
    from pathlib import Path

    work = Path(str(folder)) / "flip.PcbDoc"
    work.write_bytes(data)
    session = edit.open(work, gates={"flip": True})
    assert isinstance(session, edit.Session)
    receipt = session.flip(edit.Component("R1")).declare_connectivity("VIN", "MID").commit(work, backup=False)
    assert receipt.written, receipt.issues
    state = State.of(work.read_bytes())
    view = View(state)
    index = view.component("D1")
    raw = rec.set_property(view.components[index].raw, {"NAMEAUTOPOSITION": "1", "COMMENTAUTOPOSITION": "3"})
    state.replace("Components6", index, raw)
    _free_text(state, view, "REV A", (30, 22), TOP_OVERLAY)
    _free_text(state, view, "REV A", (30, 18), BOTTOM_OVERLAY)
    return state.data()
