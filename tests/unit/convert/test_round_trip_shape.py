# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An Altium board through KiCad and back keeps its shape and its connections (capability
design-conversion, "Altium round trip keeps the board"; change c0441).

The fixture is the authored Altium sample ``tests/data/altium/routed``: a 50 × 30 mm board with three vias
and rounded-rectangle pads of corner ratio 0.25. One via is given a hole equal to its diameter, as a saved
document can hold (``H-A-PCBX-VIA-FULL``), and one corner of the board is rounded by an arc."""

from __future__ import annotations

import dataclasses
import shutil
from collections import Counter
from pathlib import Path

import pytest

from fenolite.api.equivalence import equivalent
from fenolite.backends.altium import lower, pcbdoc
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.kicad.frame import board_pads
from fenolite.checks.equivalence.levels import compare_designs
from fenolite.convert import convert_project
from fenolite.convert.sources import SourceProject, read_source
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.board import Graphic
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
ROUTED = ROOT / "tests" / "data" / "altium" / "routed"
FILLET = 5_000_000
"""The radius of the rounded corner, in nm."""


def _write(files: dict[str, bytes], folder: Path) -> None:
    for name, data in files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)


def _source(tmp_path: Path) -> SourceProject:
    shutil.copytree(ROUTED, tmp_path / "src")
    return read_source(tmp_path / "src" / "routed.PrjPcb")


def _full_drill(design: Design) -> tuple[Design, Point]:
    """``design`` whose first via has a hole equal to its diameter, and that via's position."""
    board = design.board
    assert board is not None
    first, *rest = board.vias
    full = dataclasses.replace(first, drill=first.diameter)
    return dataclasses.replace(design, board=dataclasses.replace(board, vias=(full, *rest))), first.position


def _rounded(design: Design) -> Design:
    """``design`` whose edge corner of highest x and y is rounded: the two lines there are shortened by
    ``FILLET`` and joined by a quarter arc."""
    board = design.board
    assert board is not None
    edges = [g for g in board.graphics if g.layer == "Edge.Cuts"]
    assert {g.kind for g in edges} == {"line"} and len(edges) == 4
    corner = Point(max(p.x for g in edges for p in g.points), max(p.y for g in edges for p in g.points))
    lines: list[Graphic] = []
    for g in edges:
        a, b = g.points
        moved = [
            p if p != corner else Point(p.x - FILLET, p.y) if a.y == b.y else Point(p.x, p.y - FILLET)
            for p in (a, b)
        ]
        lines.append(dataclasses.replace(g, points=tuple(moved)))
    centre = Point(corner.x - FILLET, corner.y - FILLET)
    half = round(FILLET * 0.7071067811865476)
    arc = Graphic(
        id=derived_id("gfx", "c0441", "fillet"),
        kind="arc",
        layer="Edge.Cuts",
        points=(
            Point(corner.x, centre.y),
            Point(centre.x + half, centre.y + half),
            Point(centre.x, corner.y),
        ),
        width=edges[0].width,
    )
    kept = tuple(g for g in board.graphics if g.layer != "Edge.Cuts")
    return dataclasses.replace(design, board=dataclasses.replace(board, graphics=(*kept, *lines, arc)))


def _round_trip(source: SourceProject, tmp_path: Path) -> tuple[Path, SourceProject]:
    """The source written to KiCad, that KiCad project written to Altium; the Altium document and its
    reading."""
    kicad = convert_project(source, to="kicad", allow_lossy=True)
    _write(dict(kicad.files), tmp_path / "kicad")
    back = convert_project(next((tmp_path / "kicad").glob("*.kicad_pro")), to="altium", allow_lossy=True)
    for kind in ("via", "pad"):
        row = back.report.row(kind)
        assert row is None or row.lost == 0, row
    _write(dict(back.files), tmp_path / "back")
    document = next((tmp_path / "back").glob("*.PcbDoc"))
    return document, read_source(next((tmp_path / "back").glob("*.PrjPcb")))


def _rewritten(design: Design, folder: Path) -> Path:
    """``design`` (a reading of an Altium document) written back as an Altium document."""
    written = lower.write_design(design, allow_lossy=True, rewrite=True)
    _write(dict(written.files), folder)
    return next(folder.glob("*.PcbDoc"))


def test_vias_and_pads_come_back_where_they_were(tmp_path: Path) -> None:
    """Scenario "Vias and pads come back": the via with a full hole and every rounded-rectangle pad are
    written back, and every pad and via of the round trip is its source moved by one translation, to the
    nanometre. The source lies 1 mm off the sample, so its corner is no multiple of 254 nm: the frame moves
    the board by whole document units, or the round trip rounds each coordinate apart."""
    sample = _source(tmp_path)
    design, _ = _full_drill(sample.design)
    assert design.board is not None
    design = dataclasses.replace(design, board=lower.moved(design.board, 1_000_000, 1_000_000))
    document = _rewritten(design, tmp_path / "src-moved")
    source = read_source(document)
    assert source.design.board is not None
    full_at = next(v.position for v in source.design.board.vias if v.drill == v.diameter)
    _, back = _round_trip(source, tmp_path)
    assert back.design.board is not None
    pads_a = {(p.ref, p.number): p for p in board_pads(source.design)}
    pads_b = {(p.ref, p.number): p for p in board_pads(back.design)}
    assert pads_a.keys() == pads_b.keys()
    shifts = Counter(
        (pads_b[k].position.x - pads_a[k].position.x, pads_b[k].position.y - pads_a[k].position.y)
        for k in pads_a
    )
    assert len(shifts) == 1, shifts  # one translation, no rounding
    (dx, dy), _ = shifts.most_common(1)[0]
    vias_a = sorted(
        (v.position.x + dx, v.position.y + dy, v.diameter, v.drill) for v in source.design.board.vias
    )
    vias_b = sorted((v.position.x, v.position.y, v.diameter, v.drill) for v in back.design.board.vias)
    assert vias_a == vias_b
    assert (full_at.x + dx, full_at.y + dy) in {(x, y) for x, y, d, h in vias_b if d == h}
    ratios = Counter(
        p.corner_ratio for fp in back.design.board.footprints for p in fp.pads if p.shape == "roundrect"
    )
    assert ratios == Counter(
        p.corner_ratio for fp in source.design.board.footprints for p in fp.pads if p.shape == "roundrect"
    )


def test_a_region_of_a_net_keeps_its_net(tmp_path: Path) -> None:
    """Scenario "A region of a net comes back with it": a free copper region of a net (read from Altium as a
    filled copper graphic with ``net_id``) is written to KiCad with its ``(net …)`` and back to Altium with
    the same net, so the vias and tracks that end on it stay joined."""
    sample = _source(tmp_path)
    design = sample.design
    assert design.board is not None
    net = next(n for n in design.circuit.nets if n.name)
    via = (
        next(v for v in design.board.vias if v.net_id == net.id)
        if any(v.net_id == net.id for v in design.board.vias)
        else design.board.vias[0]
    )
    c, h = via.position, 1_000_000
    region = Graphic(
        id=derived_id("gfx", "c0441", "region"),
        kind="polygon",
        layer="F.Cu",
        points=(
            Point(c.x - h, c.y - h),
            Point(c.x + h, c.y - h),
            Point(c.x + h, c.y + h),
            Point(c.x - h, c.y + h),
        ),
        filled=True,
        net_id=net.id,
    )
    board = dataclasses.replace(design.board, graphics=(*design.board.graphics, region))
    document = _rewritten(dataclasses.replace(design, board=board), tmp_path / "src-region")
    _, back = _round_trip(read_source(document), tmp_path)
    assert back.design.board is not None
    names = {n.id: n.name for n in back.design.circuit.nets}
    copper = [g for g in back.design.board.graphics if g.layer == "F.Cu" and g.kind == "polygon"]
    assert [names.get(g.net_id or "") for g in copper] == [net.name]


def test_a_rounded_corner_comes_back_as_an_arc(tmp_path: Path) -> None:
    """Scenario "The board shape comes back": the outline of the round trip holds the corner as one arc
    vertex, and ``equivalent`` in the relative frame finds no difference of the board shape; with the arc
    left out, as before the change, it reports the edges that differ."""
    source = _source(tmp_path)
    document = _rewritten(_rounded(source.design), tmp_path / "src-arc")
    assert [v.kind for v in read_pcbdoc(document.read_bytes()).board.outline].count(1) == 1
    start = read_source(document)
    back_document, _ = _round_trip(start, tmp_path)
    outline = read_pcbdoc(back_document.read_bytes()).board.outline
    assert [v.kind for v in outline].count(1) == 1
    result = equivalent(document, back_document, level=7, frame="relative")
    assert result.report is not None
    shape = [
        d
        for level in result.report.levels
        for d in level.differences
        if d.where.startswith(("board:Edge.Cuts", "board:outline"))
    ]
    assert shape == []


def test_equivalent_sees_a_flattened_arc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative case: the round trip written with its outline arcs dropped (the arc a straight edge, as
    before the change) gives differences of the board shape in the relative frame."""
    source = _source(tmp_path)
    document = _rewritten(_rounded(source.design), tmp_path / "src-arc")
    start = read_source(document)
    real = lower._arc_ring  # pyright: ignore[reportPrivateUsage]

    def flat(points: tuple[Point, ...], arcs: object) -> object:
        return real(points, ())

    monkeypatch.setattr(lower, "_arc_ring", flat)
    back_document, _ = _round_trip(start, tmp_path)
    result = equivalent(document, back_document, level=7, frame="relative")
    assert result.report is not None
    shape = [
        d
        for level in result.report.levels
        for d in level.differences
        if d.where.startswith("board:Edge.Cuts")
    ]
    assert shape


def _moved(design: Design, by: Point) -> Design:
    """``design`` with its footprints and its edges moved by ``by`` and nothing else on the board."""
    board = design.board
    assert board is not None

    def at(p: Point) -> Point:
        return Point(p.x + by.x, p.y + by.y)

    edges = tuple(
        dataclasses.replace(g, points=tuple(at(p) for p in g.points))
        for g in board.graphics
        if g.layer == "Edge.Cuts"
    )
    footprints = tuple(dataclasses.replace(fp, position=at(fp.position)) for fp in board.footprints)
    return dataclasses.replace(
        design, board=dataclasses.replace(board, graphics=edges, footprints=footprints)
    )


@pytest.mark.parametrize(("frame", "found"), [("relative", 0), ("absolute", 1)])
def test_level_7_compares_the_board_shape_in_the_relative_frame(
    tmp_path: Path, frame: str, found: int
) -> None:
    """The same board moved by (1.27 mm, -2.54 mm): in the relative frame level 7 moves side ``b``'s board
    shape back by level 4's translation and finds no difference of it; in the absolute frame the ring of
    the edges differs (one ring missing on each side)."""
    design = _rounded(_source(tmp_path).design)
    a = _moved(design, Point(0, 0))
    b = _moved(design, Point(1_270_000, -2_540_000))
    report = compare_designs(a, b, level=7, frame=frame)  # type: ignore[arg-type]
    assert report.translation == (Point(1_270_000, -2_540_000) if frame == "relative" else Point(0, 0))
    shape = [d for level in report.levels for d in level.differences if d.where.startswith("board:Edge.Cuts")]
    assert len(shape) == 2 * found


def test_the_frame_moves_by_whole_units() -> None:
    """``Frame.on_units`` moves the corner of the outline out to a multiple of 254 nm."""
    outline = (
        Point(323_392_526, -232_915_424),
        Point(349_392_524, -232_915_427),
        Point(349_392_524, -222_000_001),
    )
    frame = pcbdoc.Frame.on_units(outline)
    plain = pcbdoc.Frame.of(outline)
    assert frame.min_x % 254 == 0 and frame.max_y % 254 == 0
    assert 0 <= plain.min_x - frame.min_x < 254 and 0 <= frame.max_y - plain.max_y < 254
