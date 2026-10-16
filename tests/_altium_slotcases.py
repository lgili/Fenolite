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

``FIXTURE`` is the document of ``tests/data/slots/altium.py`` written with ``pcbdoc.CUTOUT_REGIONS`` true
(the kit's form), committed because the merged L needs the ``geo`` extra, which the oracle jobs do not
install; ``tests/unit/backends/altium/test_cutout_regions.py`` keeps it equal to a fresh build
(``FENOLITE_SLOTS_WRITE=1`` writes it). The probes ``altium-slot-pad`` and ``altium-cutout-region`` import it
and compare KiCad's board with what Fenolite's reader finds in the document, relative to the board's
corner (KiCad moves the board on its sheet).
"""

from __future__ import annotations

import os
import struct
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from pathlib import Path

from _resources import kicad_cli

from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.pcbdoc import PcbDocSpec, write_pcbdoc
from fenolite.backends.kicad.cli import KicadCli, cli_for
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.model.board import Graphic
from fenolite.lens.build import BuildOutput
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


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests" / "data" / "slots" / "altium.py"
FIXTURE = ROOT / "tests" / "data" / "slots" / "slots_altium.PcbDoc"
WRITE_VARIABLE = "FENOLITE_SLOTS_WRITE"
NM_PER_UNIT = Fraction(254, 100)
"""Nanometres per Altium binary unit (``pcb-records.md``)."""
OFFSET = 25_400_000
"""The board's lower-left corner lies at (1000 mil, 1000 mil) of a built document (``pcbdoc.Frame``)."""


def fixture_document(*, gate: bool = True) -> bytes:
    """``tests/data/slots/altium.py`` built for Altium with ``pcbdoc.CUTOUT_REGIONS`` set to ``gate``: the
    bytes of ``slots.PcbDoc``. The merged L needs the ``geo`` extra when ``gate`` is true."""
    return fixture_build(gate=gate).files["slots.PcbDoc"]


def fixture_build(*, gate: bool = True, source: Path | None = None) -> BuildOutput:
    """The build of ``source`` (``SOURCE`` by default) for Altium with ``pcbdoc.CUTOUT_REGIONS`` set to
    ``gate``; no issue of it is an error."""
    import runpy

    from _altium import blink_resolver, blink_tree

    from fenolite.backends.altium import pcbdoc
    from fenolite.dsl import Design as Script
    from fenolite.dsl import placements, to_model
    from fenolite.lens.altium import build_altium

    design = runpy.run_path(str(source or SOURCE))["design"]
    assert isinstance(design, Script)
    kept = pcbdoc.CUTOUT_REGIONS
    pcbdoc.CUTOUT_REGIONS = gate  # type: ignore[misc]  # pyright: ignore[reportConstantRedefinition]
    try:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = build_altium(
                to_model(design),
                name=design.name,
                placed=tuple(placements(design)),
                placements=placements(design),
                resolver=blink_resolver(root, blink_tree(root)),
                authored_footprints={key: fp.definition for key, fp in design.footprints.items()},
                authored_symbols={key: s.definition for key, s in design.symbols.items()},  # type: ignore[attr-defined]
            )
    finally:
        pcbdoc.CUTOUT_REGIONS = kept  # type: ignore[misc]  # pyright: ignore[reportConstantRedefinition]
    assert not [found for found in output.issues if found.severity == "error"]
    return output


def _nm(units: float | int) -> int:
    return round(Fraction(units) * NM_PER_UNIT)


@dataclass(frozen=True)
class WrittenSlot:
    """A free slot pad of a document: its centre (Altium frame, nm), hole width, overall length and the
    pad's rotation in microdegrees."""

    at: Point
    width: int
    length: int
    rotation: int


def written_slots(data: bytes) -> list[WrittenSlot]:
    """The pads with hole shape 2 of the document, as Fenolite's reader finds them."""
    from fenolite.backends.altium.read.pcb import read_pcbdoc
    from fenolite.backends.altium.read.pcbprims import PadRecord

    found: list[WrittenSlot] = []
    for pad in read_pcbdoc(data).pads:
        if isinstance(pad, PadRecord) and pad.hole_shape == rec.HOLE_SHAPE_SLOT and pad.slot_length:
            rotation = round(Fraction(pad.rotation) * 1_000_000)
            found.append(
                WrittenSlot(Point(_nm(pad.x), _nm(pad.y)), _nm(pad.hole), _nm(pad.slot_length), rotation)
            )
    return found


def written_cutouts(data: bytes) -> list[tuple[Point, ...]]:
    """The rings of the regions with ``ISBOARDCUTOUT=TRUE`` (Altium frame, nm), from ``Regions6``."""
    from fenolite.backends.altium.read.pcb import read_pcbdoc
    from fenolite.backends.altium.read.pcbprims import RegionRecord

    rings: list[tuple[Point, ...]] = []
    for region in read_pcbdoc(data).regions:
        if isinstance(region, RegionRecord) and dict(region.properties.fields).get("ISBOARDCUTOUT") == "TRUE":
            rings.append(tuple(Point(_nm(v.x), _nm(v.y)) for v in region.outline))
    return rings


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


def board_frame(design: Design) -> tuple[Point, int]:
    """The lower-left corner of the imported board's edges in KiCad's frame and the board's height."""
    points = [p for g in edge_items(design) for p in g.points]
    x0, y0 = min(p.x for p in points), min(p.y for p in points)
    return Point(x0, y0), max(p.y for p in points) - y0


def to_kicad(point: Point, corner: Point, height: int) -> Point:
    """A point of a built document (Altium frame, nm) in the frame of KiCad's import of it."""
    return Point(corner.x + point.x - OFFSET, corner.y + height - (point.y - OFFSET))


@cache
def imported_fixture() -> Imported:
    return import_document(FIXTURE.read_bytes(), "slots.PcbDoc")


def _same_axis(a: int, b: int) -> bool:
    """Two slot axes within 0.001° (a slot is the same turned by 180°)."""
    d = (a - b) % 180_000_000
    return min(d, 180_000_000 - d) <= 1_000


def slot_pad() -> str:
    """``H-A-SLOT-PAD``: every free slot pad of the fixture is one non-plated oval hole of KiCad's import,
    of the same centre (10 nm), width, length and angle."""
    found = imported_fixture().design
    assert found.board is not None
    corner, height = board_frame(found)
    slots = written_slots(FIXTURE.read_bytes())
    holes = [
        (fp.position, pad)
        for fp in found.board.footprints
        for pad in fp.pads
        if pad.kind == "np_thru_hole" and pad.padstack is not None and pad.padstack.hole_shape == "slot"
    ]
    if len(slots) != 3 or len(holes) != len(slots):
        return "different"
    for slot in slots:
        at = to_kicad(slot.at, corner, height)
        if not any(
            abs(position.x - at.x) <= TOLERANCE
            and abs(position.y - at.y) <= TOLERANCE
            and pad.drill is not None
            and abs(pad.drill - slot.width) <= TOLERANCE
            and pad.padstack is not None
            and pad.padstack.hole_length is not None
            and abs(pad.padstack.hole_length - slot.length) <= TOLERANCE
            and _same_axis(pad.rotation, slot.rotation)
            for position, pad in holes
        ):
            return "different"
    return "equal"


def cutout_region() -> str:
    """``H-A-CUTOUT-REGION``: every vertex of every written cut-out lies within 10 nm of an end of an
    ``Edge.Cuts`` line of KiCad's import, each ring imported as exactly its edges, three rings in all."""
    found = imported_fixture().design
    corner, height = board_frame(found)
    rings = written_cutouts(FIXTURE.read_bytes())
    ends = [p for g in edge_items(found) for p in g.points]
    cut_lines = len(edge_items(found)) - 4  # the board's own rectangle is four lines
    if len(rings) != 3 or cut_lines != sum(len(ring) for ring in rings):
        return "different"
    for ring in rings:
        for vertex in ring:
            at = to_kicad(vertex, corner, height)
            if not any(abs(p.x - at.x) <= TOLERANCE and abs(p.y - at.y) <= TOLERANCE for p in ends):
                return "different"
    return "equal"


def slot_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """The probes of change c0168, on 10.0 only (``pcb import``)."""
    return {"altium-slot-pad": (slot_pad, (10,)), "altium-cutout-region": (cutout_region, (10,))}


def write_wanted() -> bool:
    return os.environ.get(WRITE_VARIABLE) == "1"


__all__ = [
    "BOARD",
    "FIXTURE",
    "WrittenSlot",
    "board_frame",
    "cutout_region",
    "fixture_build",
    "fixture_document",
    "imported_fixture",
    "slot_pad",
    "slot_probes",
    "to_kicad",
    "write_wanted",
    "written_cutouts",
    "written_slots",
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
