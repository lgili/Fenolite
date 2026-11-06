# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Plain keep-out lines of the Keep-Out layer come back as lines, not regions (change c0442)."""

import dataclasses
from collections import Counter
from pathlib import Path

from _convert import source_of, two_layer

from fenolite.backends.altium import keepout_lines, lower
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.checks.equivalence import compare_designs
from fenolite.convert import convert_project
from fenolite.convert.altium_to_kicad import Ledger, keepouts
from fenolite.core.coords import Point
from fenolite.model.board import Graphic, Keepout
from fenolite.model.design import Design

MM = 1_000_000
KEEPOUT_LAYER, KEEPOUT_FLAG = 56, 2


def _stroke(ident: str, kind: str, *points: Point, width: int = MM // 5) -> Graphic:
    return Graphic(id=ident, kind=kind, layer=keepout_lines.LAYER, points=points, width=width)  # type: ignore[arg-type]


def _drawn() -> Design:
    """The two-layer board with a line, an arc, a circle and a filled square on the Keep-Out layer, and a
    line of the Keep-Out layer in its first footprint."""
    design = two_layer()
    assert design.board is not None
    graphics = (
        _stroke("gra-line", "line", Point(0, 0), Point(10 * MM, 0)),
        _stroke("gra-arc", "arc", Point(0, 5 * MM), Point(5 * MM, 10 * MM), Point(10 * MM, 5 * MM)),
        _stroke("gra-circle", "circle", Point(20 * MM, 20 * MM), Point(22 * MM, 20 * MM)),
        Graphic(
            id="gra-square",
            kind="polygon",
            layer=keepout_lines.LAYER,
            points=(Point(30 * MM, 0), Point(32 * MM, 0), Point(32 * MM, 2 * MM), Point(30 * MM, 2 * MM)),
            filled=True,
        ),
    )
    first, *rest = design.board.footprints
    own = _stroke("gra-own", "line", Point(-MM, 3 * MM), Point(MM, 3 * MM), width=MM // 10)
    first = dataclasses.replace(first, graphics=(*first.graphics, own))
    board = dataclasses.replace(
        design.board, graphics=(*design.board.graphics, *graphics), footprints=(first, *rest)
    )
    return dataclasses.replace(design, board=board)


def test_a_marker_carries_its_stroke() -> None:
    line = _stroke("gra-1", "line", Point(-3, 4), Point(5, -6), width=2)
    assert keepout_lines.parse(keepout_lines.marker(line) or "") == ("line", line.points, 2, False)
    circle = _stroke("gra-2", "circle", Point(0, 0), Point(7, 0))
    second = keepout_lines.marker(circle, 1) or ""
    assert second.endswith("/2") and keepout_lines.parse(second) == ("circle", circle.points, MM // 5, True)
    square = dataclasses.replace(
        line, kind="polygon", points=(Point(0, 0), Point(1, 0), Point(1, 1)), filled=True
    )
    assert keepout_lines.marker(square) is None
    assert keepout_lines.parse("GND_area") is None


def test_plain_strokes_name_their_rule_areas() -> None:
    """A stroke without a keep-out record names each area of its band with itself; a stroke whose record
    is a keep-out, and a filled shape, leave their areas unnamed."""
    design = _drawn()
    converted = keepouts(design, Ledger(), {"gra-arc": 7})
    assert converted.board is not None
    names = sorted(area.name.split("/")[1] for area in converted.board.keepouts if area.name)
    assert names == ["circle", "circle", "line"]
    own = [area.name for fp in converted.board.footprints for area in fp.keepouts]
    assert len(own) == 1 and keepout_lines.parse(own[0]) is not None


def _written(design: Design) -> bytes:
    written = lower.write_design(design, allow_lossy=True)
    return written.files[f"{design.header.name}.PcbDoc"]


def _keepout_layer(document: bytes) -> Counter[tuple[str, bool, str]]:
    found: Counter[tuple[str, bool, str]] = Counter()
    doc = read_pcbdoc(document)
    for kind, records in (("track", doc.tracks), ("arc", doc.arcs), ("region", doc.regions)):
        for record in records:
            prefix = getattr(record, "prefix", None)
            if prefix is not None and prefix.layer == KEEPOUT_LAYER:
                owner = "free" if prefix.component is None else "component"
                found[(kind, prefix.flags2 == KEEPOUT_FLAG, owner)] += 1
    return found


def test_marked_rule_areas_are_written_as_plain_strokes(tmp_path: Path) -> None:
    """Scenario "A keep-out line comes back as a line": the line, the arc and the circle come back as
    tracks and arcs of the Keep-Out layer without the keep-out flag, the footprint's line as a track of its
    component; only the area of the filled square is a keep-out region, as the board's own rule area is."""
    converted = keepouts(_drawn(), Ledger(), {})
    document = _written(converted)
    assert _keepout_layer(document) == Counter(
        {
            ("track", False, "free"): 1,
            ("arc", False, "free"): 2,
            ("track", False, "component"): 1,
            ("region", True, "free"): 2,  # the filled square, and the board's own rule area
        }
    )
    path = tmp_path / "lines.PcbDoc"
    path.write_bytes(document)
    back = AltiumBackend().read(path).design
    assert back.board is not None
    drawn = sorted((g.kind, g.width) for g in back.board.graphics if g.layer == keepout_lines.LAYER)
    assert drawn == [("arc", MM // 5), ("circle", MM // 5), ("line", MM // 5), ("polygon", 0), ("polygon", 0)]


def test_a_marked_area_is_counted_written_as_a_keepout() -> None:
    """Every rule area, marked or not, is counted written under ``keep-out``, and no stroke is counted as a
    graphic of its own."""
    converted = keepouts(_drawn(), Ledger(), {})
    conversion = convert_project(source_of(converted), to="altium", allow_lossy=True)
    rows = {row.kind: row for row in conversion.report.rows}
    assert (rows["keep-out"].written, rows["keep-out"].lost) == (rows["keep-out"].source, 0)
    assert rows["graphic"].written == rows["graphic"].source


def test_an_edited_marked_area_stays_a_keepout_region() -> None:
    """Scenario "An edited keep-out line stays an area": a marked area whose restrictions or outline no
    longer are its stroke's is written as a keep-out region, as any rule area is."""
    converted = keepouts(_drawn(), Ledger(), {})
    assert converted.board is not None

    def edited(area: Keepout) -> Keepout:
        if area.name.startswith(keepout_lines.PREFIX + "line"):
            return dataclasses.replace(area, no_vias=False)
        if area.name.startswith(keepout_lines.PREFIX + "arc"):
            return dataclasses.replace(area, outline=tuple(Point(p.x + MM, p.y) for p in area.outline))
        return area

    board = dataclasses.replace(converted.board, keepouts=tuple(edited(k) for k in converted.board.keepouts))
    found = _keepout_layer(_written(dataclasses.replace(converted, board=board)))
    assert found[("track", False, "free")] == 0
    assert found[("arc", False, "free")] == 1  # the circle alone
    assert found[("region", True, "free")] == 4  # with the square and the board's own rule area


def test_equivalent_tells_a_keepout_line_from_a_keepout_region() -> None:
    """Scenario "A keep-out line written as a region is reported": a drawn line against a filled drawing of
    the ring its band covers is a ``keepout-field`` difference on ``form``."""
    from fenolite.geometry.bands import segment_band

    design = _drawn()
    assert design.board is not None
    line = next(g for g in design.board.graphics if g.id == "gra-line")
    band = Graphic(id="gra-band", kind="polygon", layer=keepout_lines.LAYER,
                   points=segment_band(line.points[0], line.points[1], line.width), filled=True)  # fmt: skip
    other = dataclasses.replace(
        design,
        board=dataclasses.replace(
            design.board, graphics=tuple(band if g.id == "gra-line" else g for g in design.board.graphics)
        ),
    )
    layers = ({keepout_lines.LAYER}, {keepout_lines.LAYER})
    report = compare_designs(design, other, level=7, keepout_layers=layers)
    found = [d.field for result in report.levels for d in result.differences if d.kind == "keepout-field"]
    assert found == ["form"]
    same = compare_designs(design, design, level=7, keepout_layers=layers)
    assert not [d for result in same.levels for d in result.differences if d.kind == "keepout-field"]
