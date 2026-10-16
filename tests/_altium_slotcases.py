# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slot pads and board cut-out regions of an Altium document against ``kicad-cli pcb import`` (change
c0168; hypotheses ``H-A-SLOT-PAD`` and ``H-A-CUTOUT-REGION``).

``CANDIDATES`` are the region forms task 1.2 measured: the property keys of the saved regions
(``pcb-records.md``, "Regions and keep-outs": ``KIND`` 0 or 1, ``ISBOARDCUTOUT=TRUE`` on the Keep-Out
layer) on the layers a board cut-out could take (Keep-Out 56, Multi-Layer 74, Top 1). Each is written
as the one free region of a 60 × 40 mm board, in ``Regions6`` and ``ShapeBasedRegions6`` alike, by
``candidate_document``; ``import_document`` runs ``kicad-cli pcb import`` (10.0 only) through the oracle's
runner, so a ``docker:<image>`` marker works. All files are authored here for Fenolite.
"""

from __future__ import annotations

import struct
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from _resources import kicad_cli

from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.pcbdoc import PcbDocSpec, write_pcbdoc
from fenolite.backends.kicad.cli import KicadCli, cli_for
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.model.board import Graphic
from fenolite.model.design import Design

MM = 1_000_000
BOARD = (Point(0, 0), Point(60 * MM, 0), Point(60 * MM, 40 * MM), Point(0, 40 * MM))
"""The board of a candidate document (KiCad frame)."""
CUT = (Point(10 * MM, 10 * MM), Point(20 * MM, 10 * MM), Point(20 * MM, 20 * MM), Point(10 * MM, 20 * MM))
"""The square cut-out of a candidate document (KiCad frame)."""
TOLERANCE = 10
"""KiCad rounds a length to 10 nm (``pcb-read.md``)."""

Fields = tuple[tuple[str, str], ...]


def _keys(v7: str, kind: str, extra: Fields = ()) -> Fields:
    return (
        ("V7_LAYER", v7),
        ("NAME", " "),
        ("KIND", kind),
        ("SUBPOLYINDEX", "-1"),
        ("UNIONINDEX", "0"),
        ("ARCRESOLUTION", "0.5mil"),
        ("ISSHAPEBASED", "FALSE"),
        ("CAVITYHEIGHT", "0mil"),
        *extra,
    )


CUTOUT_KEY = (("ISBOARDCUTOUT", "TRUE"),)
CANDIDATES: dict[str, tuple[int, Fields]] = {
    "kind0-keepout-boardcutout": (56, _keys("KEEPOUT", "0", CUTOUT_KEY)),
    "kind0-keepout-saved": (
        56,
        (("LAYER", "KEEPOUT"), ("KEEPOUT", "TRUE"), *CUTOUT_KEY, *_keys("KEEPOUT", "0")[1:]),
    ),
    "kind0-multilayer-boardcutout": (74, _keys("MULTILAYER", "0", CUTOUT_KEY)),
    "kind0-top-boardcutout": (1, _keys("TOP", "0", CUTOUT_KEY)),
    "kind1-keepout": (56, _keys("KEEPOUT", "1")),
    "kind1-multilayer": (74, _keys("MULTILAYER", "1")),
    "kind1-multilayer-boardcutout": (74, _keys("MULTILAYER", "1", CUTOUT_KEY)),
    "kind1-top": (1, _keys("TOP", "1")),
}
"""Candidate name → (layer id, property keys in order)."""
CUT_OUT = frozenset(name for name in CANDIDATES if name.startswith("kind0-"))
"""The candidates KiCad 10.0.6 imports as an ``Edge.Cuts`` cut-out (measured 2026-10-16)."""


def candidate_record(
    layer: int, fields: Fields, vertices: Sequence[tuple[int, int]], *, shape_based: bool, round_at: int = -1
) -> bytes:
    """A region record with ``fields`` as its property text (``pcb-records.md``, "Regions and keep-outs":
    the prefix without net, polygon and component, five zero bytes, the text, the outline). In the
    shape-based form the vertex ``round_at`` has the round flag, its centre on the next vertex's x and
    halfway to it in y, and the angles 270 and 90 (a half circle to the right of an upward edge)."""
    text = "|".join(f"{key}={value}" for key, value in fields).encode("ascii") + b"\0"
    body = rec.prefix(layer) + bytes(5) + struct.pack("<I", len(text)) + text
    body += struct.pack("<I", len(vertices))
    if shape_based:
        for index, (x, y) in enumerate((*vertices, vertices[0])):
            if index == round_at:
                _, ny = vertices[(index + 1) % len(vertices)]
                cx, cy, radius = x, (y + ny) // 2, abs(ny - y) // 2
                body += struct.pack("<B5i2d", 1, x, y, cx, cy, radius, 270.0, 90.0)
            else:
                body += struct.pack("<B5i2d", 0, x, y, 0, 0, 0, 0.0, 0.0)
    else:
        for x, y in vertices:
            body += struct.pack("<2d", float(x), float(y))
    return bytes((rec.REGION,)) + rec.subrecord(body)


def candidate_document(name: str, *, arc: bool = False) -> bytes:
    """The board with candidate ``name`` as its one free region. The document is written with a filled
    polygon on ``F.SilkS`` (one region), whose two records are then replaced by the candidate's;
    ``arc`` makes the second edge of the shape-based outline a half circle (``candidate_record``)."""
    from fenolite.backends.altium import pcbdoc

    layer, fields = CANDIDATES[name]
    original = pcbdoc._Free.region  # pyright: ignore[reportPrivateUsage]

    def region(
        self: pcbdoc._Free,  # pyright: ignore[reportPrivateUsage]
        _layer: int,
        ring: Sequence[Point],
        frame: pcbdoc.Frame,
        _keepout: int | None = None,
    ) -> None:
        points = [(rec.to_units(frame(p).x), rec.to_units(frame(p).y)) for p in ring]
        self.regions.append(candidate_record(layer, fields, points, shape_based=False))
        self.shapes.append(
            candidate_record(layer, fields, points, shape_based=True, round_at=1 if arc else -1)
        )

    graphic = Graphic(id="gr_cut", kind="polygon", layer="F.SilkS", points=CUT, filled=True)
    pcbdoc._Free.region = region  # type: ignore[method-assign]  # pyright: ignore[reportPrivateUsage]
    try:
        return write_pcbdoc(PcbDocSpec(outline=BOARD, graphics=(graphic,)), filename="candidate.PcbDoc")
    finally:
        pcbdoc._Free.region = original  # type: ignore[method-assign]  # pyright: ignore[reportPrivateUsage]


@cache
def runner() -> KicadCli:
    path = kicad_cli()
    assert path is not None  # the needs_kicad marker skips before this is reached
    return cli_for(Path(path), timeout=600)


@dataclass(frozen=True)
class Imported:
    """What ``kicad-cli pcb import`` made of a document: its exit code and output, and the board read."""

    code: int
    output: str
    design: Design


def import_document(data: bytes, name: str = "slots.PcbDoc") -> Imported:
    """The bytes of a PCB document as ``kicad-cli pcb import --format altium`` reads them."""
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / name
        source.write_bytes(data)
        found = runner().import_board(source)
        assert found.board is not None, found.run.stdout + found.run.stderr
        target = Path(folder) / "imported.kicad_pcb"
        target.write_bytes(found.board)
        return Imported(
            -1 if found.run.returncode is None else found.run.returncode,
            found.run.stdout + found.run.stderr,
            read_board(target),
        )


@cache
def imported_candidate(name: str, arc: bool = False) -> Imported:
    return import_document(candidate_document(name, arc=arc), "candidate.PcbDoc")


def edge_items(design: Design) -> list[Graphic]:
    """The ``Edge.Cuts`` graphics of an imported board."""
    assert design.board is not None
    return [g for g in design.board.graphics if g.layer == "Edge.Cuts"]


def _corner(points: Sequence[Point]) -> Point:
    return Point(min(p.x for p in points), min(p.y for p in points))


def relative(design: Design) -> list[tuple[str, tuple[Point, ...]]]:
    """The ``Edge.Cuts`` graphics as (kind, points) relative to the board's lower-left corner (KiCad
    moves the board on its sheet)."""
    items = edge_items(design)
    corner = _corner([p for g in items for p in g.points])
    return sorted((g.kind, tuple(Point(p.x - corner.x, p.y - corner.y) for p in g.points)) for g in items)


def cut_edges(design: Design) -> list[tuple[str, tuple[Point, ...]]]:
    """The edges of ``relative`` that are not the board's own (inside the 60 × 40 mm rectangle)."""

    def inside(p: Point) -> bool:
        return 0 < p.x < 60 * MM and 0 < p.y < 40 * MM

    return [(kind, points) for kind, points in relative(design) if any(inside(p) for p in points)]


__all__ = [
    "BOARD",
    "CANDIDATES",
    "CUT",
    "CUT_OUT",
    "Imported",
    "candidate_document",
    "candidate_record",
    "cut_edges",
    "edge_items",
    "import_document",
    "imported_candidate",
    "relative",
    "runner",
]
