# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Keep-out primitives and a polygon cut-out in an authored PCB document (change c0407).

``keepout_document`` writes the 60 × 40 mm board of ``_altium_slotcases`` with these free records, each
authored here for Fenolite from the record layout of ``pcb-records.md`` ("Regions and keep-outs"):

- ``RING``: four tracks on the Keep-Out layer (56), 1 mm wide, round a 10 mm square, with the keep-out flag;
- ``LINE``: one track on Top (1), 0.5 mm wide, with the keep-out flag;
- ``CUTOUT``: one region of ``KIND=1`` (a polygon cut-out) on Top, without a net.

``keepout_library`` writes a PCB library of one footprint ``KO`` (change c0410): a pad and, in the
library's frame, a keep-out track on Top (0.5 mm), a keep-out track and a plain track on the Keep-Out layer
(1 mm), a region of ``KIND=1`` on Top and a keep-out region on Bottom whose restrictions are 3. KiCad 10.0.6's
``fp upgrade`` makes five rule areas of the footprint of them (``pcb-records.md``).

KiCad 10.0.6's ``pcb import`` of the document gives six rule areas (measured 2026-11-05):
one per ring track on both copper layers, the band of its width with round ends; the band of ``LINE`` on
``F.Cu``; and ``CUTOUT`` on ``F.Cu``, where only poured copper is not allowed. Points are in the KiCad frame
of the board (``BOARD``), millimetres.
"""

from __future__ import annotations

from collections.abc import Sequence

from _altium_slotcases import BOARD, MM, candidate_record

from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.pcbdoc import PcbDocSpec, write_pcbdoc
from fenolite.core.coords import Point

RING = ((30, 10), (40, 10), (40, 20), (30, 20))
RING_WIDTH = MM
LINE = ((10, 30), (50, 30))
LINE_WIDTH = MM // 2
CUTOUT = ((10, 10), (20, 10), (20, 20), (10, 20))


def _flagged(record: bytes) -> bytes:
    """``record`` with the keep-out flag: the second flag byte of its prefix (after the type byte and the
    length of its first subrecord) is 2."""
    out = bytearray(record)
    out[5 + 2] = rec.KEEPOUT_FLAG
    return bytes(out)


def _fields(v7: str, kind: str) -> tuple[tuple[str, str], ...]:
    return (
        ("V7_LAYER", v7),
        ("NAME", " "),
        ("KIND", kind),
        ("SUBPOLYINDEX", "-1"),
        ("UNIONINDEX", "0"),
        ("ARCRESOLUTION", "0.5mil"),
        ("ISSHAPEBASED", "FALSE"),
        ("CAVITYHEIGHT", "0mil"),
    )


def keepout_document() -> bytes:
    """The board with the keep-out records of the module docstring."""
    original = pcbdoc.free_records

    def free_records(spec: PcbDocSpec, copper: pcbdoc._Copper) -> pcbdoc._Free:  # pyright: ignore[reportPrivateUsage]
        out = original(spec, copper)

        def at(x: int, y: int) -> tuple[int, int]:
            return pcbdoc._units(copper.frame(Point(x * MM, y * MM)))  # pyright: ignore[reportPrivateUsage]

        def region(layer: int, fields: tuple[tuple[str, str], ...], ring: Sequence[tuple[int, int]]) -> None:
            vertices = [at(*p) for p in ring]
            out.regions.append(candidate_record(layer, fields, vertices, shape_based=False))
            out.shapes.append(candidate_record(layer, fields, vertices, shape_based=True))

        width = rec.to_units(RING_WIDTH)
        for index, a in enumerate(RING):
            b = RING[(index + 1) % len(RING)]
            out.tracks.append(_flagged(rec.track_record(rec.KEEPOUT_LAYER, at(*a), at(*b), width)))
        out.tracks.append(_flagged(rec.track_record(1, at(*LINE[0]), at(*LINE[1]), rec.to_units(LINE_WIDTH))))
        region(1, _fields("TOP", "1"), CUTOUT)
        return out

    pcbdoc.free_records = free_records  # type: ignore[assignment]
    try:
        return write_pcbdoc(PcbDocSpec(outline=BOARD), filename="keepouts.PcbDoc")
    finally:
        pcbdoc.free_records = original  # type: ignore[assignment]


def keepout_library() -> bytes:
    """The PCB library of the module docstring."""
    from fenolite.backends.altium.pcblib import LibFootprint, write_pcblib
    from fenolite.core.coords import Size
    from fenolite.model.board import Pad
    from fenolite.model.library import FootprintDef

    def at(x: float, y: float) -> tuple[int, int]:
        return rec.to_units(round(x * MM)), rec.to_units(round(y * MM))

    def region(layer: int, fields: tuple[tuple[str, str], ...], ring: Sequence[tuple[float, float]]) -> bytes:
        return candidate_record(layer, fields, [at(*p) for p in ring], shape_based=False)

    restricted = (*_fields("BOTTOM", "0"), ("KEEPOUTRESTRICTIONS", "3"), ("KEEPOUTRESTRIC", "3"))
    extra = (
        ("Track", _flagged(rec.track_record(1, at(-3, 2), at(3, 2), rec.to_units(LINE_WIDTH)))),
        ("Track", _flagged(rec.track_record(rec.KEEPOUT_LAYER, at(-3, -2), at(3, -2), rec.to_units(MM)))),
        ("Track", rec.track_record(rec.KEEPOUT_LAYER, at(-3, -4), at(3, -4), rec.to_units(MM))),
        ("Region", region(1, _fields("TOP", "1"), ((4, 4), (6, 4), (6, 6), (4, 6)))),
        ("Region", _flagged(region(32, restricted, ((-6, 4), (-4, 4), (-4, 6), (-6, 6))))),
    )
    pad = Pad(id="pad1", number="1", shape="rect", size=Size(MM, MM), position=Point(0, 0),
              layers=("F.Cu", "F.Mask", "F.Paste"))  # fmt: skip
    footprint = LibFootprint(FootprintDef(id="fp", name="KO", pads=(pad,)), extra_primitives=extra)
    return write_pcblib([footprint], filename="keepouts.PcbLib")
