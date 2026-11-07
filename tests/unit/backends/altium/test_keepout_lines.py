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
from fenolite.backends.altium.read.pcbprims import RegionRecord
from fenolite.checks.equivalence import compare_designs
from fenolite.convert import convert_project
from fenolite.convert.altium_to_kicad import Ledger, keepouts, stroke_names
from fenolite.convert.sources import read_source
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
    component; only the area of the filled square is a keep-out region. Both rings of the circle give the one
    circle (change c0450: before it, its second ring stayed a keep-out region)."""
    converted = keepouts(_drawn(), Ledger(), {})
    document = _written(converted)
    assert _keepout_layer(document) == Counter(
        {
            ("track", False, "free"): 1,
            ("arc", False, "free"): 2,
            ("track", False, "component"): 1,
            ("region", True, "free"): 1,  # the filled square
        }
    )
    path = tmp_path / "lines.PcbDoc"
    path.write_bytes(document)
    back = AltiumBackend().read(path).design
    assert back.board is not None
    drawn = sorted((g.kind, g.width) for g in back.board.graphics if g.layer == keepout_lines.LAYER)
    assert drawn == [("arc", MM // 5), ("circle", MM // 5), ("line", MM // 5), ("polygon", 0)]


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
    assert found[("region", True, "free")] == 3  # the edited line and arc, and the square


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


# --- keep-out strokes of copper (change c0450) -----------------------------------------------------------


def _flagged_area(ident: str, stroke: Graphic, restrictions: int) -> list[Keepout]:
    """The rule areas that the import makes of a keep-out stroke of copper, with its marker as their name,
    as a conversion to KiCad gives them."""
    rings = 2 if stroke.kind == "circle" else 1
    areas: list[Keepout] = []
    for part in range(rings):
        name = keepout_lines.marker(stroke, part, restrictions=restrictions) or ""
        found = keepout_lines.parse(name)
        assert found is not None
        areas.append(
            Keepout(
                id=ident if part == 0 else f"{ident}:2",
                outline=keepout_lines.band(*found),
                layers=(stroke.layer,),
                no_vias=bool(restrictions & 1),
                no_tracks=bool(restrictions & 2),
                no_copper_pour=bool(restrictions & 4),
                no_pads=restrictions & 0x18 == 0x18,
                name=name,
            )
        )
    return areas


def _flagged() -> Design:
    """The two-layer board with a free keep-out line of ``F.Cu`` that keeps out pads alone (24) and a
    keep-out circle of ``F.Cu`` in its first footprint that keeps out everything (31)."""
    design = two_layer()
    assert design.board is not None
    line = Graphic(id="s", kind="line", layer="F.Cu", points=(Point(0, 0), Point(10 * MM, 0)), width=MM // 5)
    circle = Graphic(id="s", kind="circle", layer="F.Cu", points=(Point(0, 0), Point(0, MM)), width=MM // 4)
    first, *rest = design.board.footprints
    first = dataclasses.replace(first, keepouts=(*first.keepouts, *_flagged_area("kpo-own", circle, 31)))
    board = dataclasses.replace(
        design.board,
        keepouts=(*design.board.keepouts, *_flagged_area("kpo-line", line, 24)),
        footprints=(first, *rest),
    )
    return dataclasses.replace(design, board=board)


def test_a_keepout_stroke_marker_carries_its_byte() -> None:
    line = Graphic(id="s", kind="line", layer="F.Cu", points=(Point(-3, 4), Point(5, -6)), width=2)
    name = keepout_lines.marker(line, restrictions=24) or ""
    assert name.startswith(keepout_lines.PREFIX + "flag24/line/")
    assert keepout_lines.flag(name) == 24 and keepout_lines.parse(name) == ("line", line.points, 2, False)
    assert keepout_lines.flag(keepout_lines.marker(line) or "") is None
    assert keepout_lines.marker(line, restrictions=32) is None
    assert keepout_lines.parse(name.replace("flag24", "flag40")) is None


def _copper_strokes(document: bytes) -> Counter[tuple[str, int, str, int, int]]:
    """(kind, layer, owner, subrecord length, restriction byte) of each keep-out track and arc."""
    found: Counter[tuple[str, int, str, int, int]] = Counter()
    doc = read_pcbdoc(document)
    for kind, records, at in (("track", doc.tracks, 45), ("arc", doc.arcs, 56)):
        for record in records:
            prefix = getattr(record, "prefix", None)
            if prefix is None or prefix.flags2 != KEEPOUT_FLAG:
                continue
            body = record.raw[5:]
            owner = "free" if prefix.component is None else "component"
            found[(kind, prefix.layer, owner, len(body), body[at] if len(body) > at else -1)] += 1
    return found


def _keepout_regions(document: bytes) -> Counter[tuple[int, str, str]]:
    """(layer, owner, restrictions) of each keep-out region of ``Regions6``."""
    found: Counter[tuple[int, str, str]] = Counter()
    for record in read_pcbdoc(document).regions:
        if isinstance(record, RegionRecord) and record.prefix.flags2 == KEEPOUT_FLAG:
            prefix = record.prefix
            owner = "free" if prefix.component is None else "component"
            fields = dict(record.properties.fields)
            found[(prefix.layer, owner, fields.get("KEEPOUTRESTRICTIONS", ""))] += 1
    return found


def test_keepout_strokes_are_written_as_flagged_strokes(tmp_path: Path) -> None:
    """Scenario "A keep-out stroke comes back as a stroke": the free line is a keep-out track of the top
    layer in the 49-byte form with its byte, the footprint's circle a keep-out arc of its component in the
    60-byte form; no keep-out region is written beside the board's own rule area. Read again, each is the
    rule area it was, and its bag holds its marker."""
    design = _flagged()
    document = _written(design)
    assert _copper_strokes(document) == Counter(
        {("track", 1, "free", 49, 24): 1, ("arc", 1, "component", 60, 31): 1}
    )
    assert _keepout_regions(document) == _keepout_regions(_written(two_layer()))  # the board's own area
    path = tmp_path / "strokes.PcbDoc"
    path.write_bytes(document)
    back = AltiumBackend().read(path).design.board
    assert back is not None and design.board is not None
    every = [*back.keepouts, *(area for fp in back.footprints for area in fp.keepouts)]
    areas = [area for area in every if "altium" in area.ext]  # not the board's own area
    read = [
        keepout_lines.read_stroke(dict(area.ext["altium"].payload)["stroke"], area.layers[0])
        for area in areas
    ]
    found = [
        (graphic.kind, graphic.width, byte) for graphic, byte in (one for one in read if one is not None)
    ]
    assert sorted(found) == [("circle", MM // 4, 31), ("circle", MM // 4, 31), ("line", MM // 5, 24)]
    names = stroke_names(back)
    assert sorted(names) == sorted(area.id for area in areas)  # every area is still its stroke's band
    assert sorted(keepout_lines.flag(name) for name in names.values()) == [24, 31, 31]


def test_a_conversion_to_kicad_names_keepout_stroke_areas(tmp_path: Path) -> None:
    """A conversion to KiCad of the document read again names each area of a keep-out stroke with its
    marker, and the conversion back writes the strokes again."""
    path = tmp_path / "altium" / "strokes.PcbDoc"
    path.parent.mkdir()
    path.write_bytes(_written(_flagged()))
    conversion = convert_project(read_source(path), to="kicad", allow_lossy=True)
    text = conversion.files[conversion.read_back].decode()
    assert text.count(f'(name "{keepout_lines.PREFIX}flag24/line/') == 1
    assert text.count(f'(name "{keepout_lines.PREFIX}flag31/circle/') == 2
    folder = tmp_path / "kicad"
    for name, data in conversion.files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    back = convert_project(read_source(folder / conversion.read_back), to="altium", allow_lossy=True)
    document = next(data for name, data in back.files.items() if name.endswith(".PcbDoc"))
    assert _copper_strokes(document) == Counter(
        {("track", 1, "free", 49, 24): 1, ("arc", 1, "component", 60, 31): 1}
    )


def test_an_edited_keepout_stroke_area_stays_a_region() -> None:
    """Scenario "An edited keep-out stroke stays an area": an area of a keep-out stroke that forbids more
    than its byte says is written as a keep-out region."""
    design = _flagged()
    assert design.board is not None
    line = dataclasses.replace(design.board.keepouts[-1], no_vias=True)
    edited = dataclasses.replace(design.board, keepouts=(*design.board.keepouts[:-1], line))
    document = _written(dataclasses.replace(design, board=edited))
    assert _copper_strokes(document) == Counter({("arc", 1, "component", 60, 31): 1})
    assert _keepout_regions(document) - _keepout_regions(_written(two_layer())) == Counter(
        {(1, "free", "25"): 1}
    )
