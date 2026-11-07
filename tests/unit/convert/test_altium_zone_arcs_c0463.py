# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Altium arc polygons through a conversion (change c0463, task 1.3; capability design-conversion, "Altium
arc polygons are never dropped"; c0427 task 2.4, ``zone-outline``).

The source is authored for these tests: the board of ``tests/_altium_pour.py`` whose one polygon has its
lower-left and upper-right corners rounded by arcs of 80 mil and an ``ARCRESOLUTION`` of 0.0394 mil, written
by Fenolite's own writer with those arc vertices (``PcbDocSpec.polygon_arcs``)."""

from __future__ import annotations

import dataclasses
import importlib.util
import re
from fractions import Fraction
from pathlib import Path

import pytest
from _altium_pour import FILENAME, MIL, Board, clearance, rect, via, zone
from _importcode import imported

from fenolite.api.conversion import ConversionResult, convert
from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium.adapter.arcring import ArcPolygon
from fenolite.backends.altium.adapter.units import NM_PER_UNIT
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.lower import ZONE_ARCS_EDITED, write_design
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbstack import OutlineVertex
from fenolite.backends.kicad import boardcarrier
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.convert import zonearcs
from fenolite.convert.altium_to_kicad import ZONE_ARC_REASON
from fenolite.core.coords import Point

pytestmark = pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra")

D = "0.0394mil"
R = 80 * MIL
W, H = 1400 * MIL, 1000 * MIL
"""Whole mils, so every length is a whole number of file units and the document holds it exactly."""


def _units(nm: int) -> Fraction:
    return Fraction(nm) / NM_PER_UNIT


def _line(x: int, y: int) -> OutlineVertex:
    zero = Fraction(0)
    return OutlineVertex(0, _units(x), _units(y), zero, zero, 0.0, 0.0, zero)


def _arc(x: int, y: int, cx: int, cy: int, start: float, end: float) -> OutlineVertex:
    return OutlineVertex(1, _units(x), _units(y), _units(cx), _units(cy), start, end, _units(R))


def _vertices() -> tuple[OutlineVertex, ...]:
    """The rounded outline in Altium's frame (Y up) from (0, 0), counter-clockwise, closed as a record is."""
    return (
        _line(R, 0),
        _line(W, 0),
        _arc(W, H - R, W - R, H - R, 0.0, 90.0),
        _line(W - R, H),
        _line(0, H),
        _arc(0, R, R, R, 180.0, 270.0),
        _line(R, 0),
    )


SOURCE = ArcPolygon(_vertices(), D)


def _source(folder: Path) -> Path:
    """The authored document: the polygon's first vertex where the zone's outline starts."""
    board = Board(zones=(zone("z1", "GND", rect(2, 2, 38, 28)),), vias=(via("v1", "GND", 20, 15),),
                  rules=(clearance(0.2),))  # fmt: skip
    spec = dataclasses.replace(board.spec(), polygon_arcs={"z1": SOURCE})
    path = folder / FILENAME
    path.write_bytes(pcbdoc.write_pcbdoc_result(spec, filename=FILENAME, pour="outline").data)
    return path


def _write(result: ConversionResult, folder: Path) -> Path:
    for key, data in result.conversion.files.items():
        path = folder / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return folder


def _zone_row(result: ConversionResult) -> dict[str, int]:
    (row,) = [r for r in result.conversion.report.rows if r.kind == "zone"]
    return {r.reason: r.count for r in row.reasons}


def _polygon(path: Path) -> tuple[tuple[OutlineVertex, ...], str]:
    (found,) = read_pcbdoc(path.read_bytes(), file=path.name).polygons
    return found.vertices, found.record.get("ARCRESOLUTION") or ""


def _moved(vertices: tuple[OutlineVertex, ...], first: OutlineVertex) -> list[tuple[object, ...]]:
    """The vertices moved so the first lies at ``first``, as comparable tuples (an end angle of 360 degrees
    is written 0, the same arc)."""
    dx, dy = first.x - vertices[0].x, first.y - vertices[0].y
    return [
        (v.kind, v.x + dx, v.y + dy, (v.cx + dx, v.cy + dy) if v.kind else None, v.radius,
         v.start_angle % 360, v.end_angle % 360)
        for v in vertices
    ]  # fmt: skip


def _kicad(tmp_path: Path) -> tuple[Path, ConversionResult]:
    (tmp_path / "altium").mkdir()
    source = _source(tmp_path / "altium")
    result = convert(source, to="kicad", allow_lossy=True, verify=False)
    (board,) = _write(result, tmp_path / "kicad").glob("*.kicad_pcb")
    return board, result


def test_source_document_holds_the_arcs(tmp_path: Path) -> None:
    """The authored polygon holds its two arc vertices and its ``ARCRESOLUTION`` as written."""
    (tmp_path / "a").mkdir()
    vertices, resolution = _polygon(_source(tmp_path / "a"))
    assert resolution == D and sum(v.kind for v in vertices) == 2
    assert _moved(SOURCE.vertices, vertices[0]) == _moved(vertices, vertices[0])


def test_import_chords_the_arcs_within_the_resolution(tmp_path: Path) -> None:
    """The import gives the zone ``record_outline``'s ring: each arc chorded within 0.0394 mil."""
    (tmp_path / "a").mkdir()
    source = _source(tmp_path / "a")
    design = AltiumBackend().read(source).design
    assert design.board is not None
    (found,) = design.board.zones
    assert ArcPolygon(*_polygon(source)).matches(found.outline) == Point(0, 0)
    assert len(found.outline) > 6  # the six corners and the chords of the two arcs


def test_to_kicad_carries_the_arcs_and_counts_the_zone_changed(tmp_path: Path) -> None:
    """Scenario "A rounded polygon goes to KiCad and back", first half: the KiCad zone's outline is the
    chorded ring, the zone is counted ``changed``, and the board carries the polygon under its zone's uuid."""
    board, result = _kicad(tmp_path)
    read_source = ArcPolygon(*_polygon(next((tmp_path / "altium").glob("*.PcbDoc"))))
    ((reason, count),) = _zone_row(result).items()
    assert reason.startswith(ZONE_ARC_REASON) and count == 1
    read = KicadBackend().read(board).design.board
    assert read is not None
    (kicad_zone,) = read.zones
    assert read_source.matches(kicad_zone.outline) is not None
    carried = zonearcs.read_carrier(
        boardcarrier.carried(board.read_text(encoding="utf-8")).get(zonearcs.PROPERTY)
    )
    assert list(carried) == [kicad_zone.native_ids["kicad"]]
    assert carried[kicad_zone.native_ids["kicad"]] == read_source


def test_way_back_writes_the_source_arcs(tmp_path: Path) -> None:
    """Scenario "A rounded polygon goes to KiCad and back": the written polygon holds the source's two arc
    vertices and its ``ARCRESOLUTION``, and the report counts no zone changed."""
    board, _ = _kicad(tmp_path)
    back = convert(board, to="altium", allow_lossy=True, verify=False)
    assert "zone" not in {r.kind for r in back.conversion.report.rows if r.changed}
    (document,) = _write(back, tmp_path / "back").glob("*.PcbDoc")
    vertices, resolution = _polygon(document)
    assert resolution == D
    assert _moved(SOURCE.vertices, vertices[0]) == _moved(vertices, vertices[0])


def test_an_edited_outline_comes_back_as_chords(tmp_path: Path) -> None:
    """Scenario "An edited outline comes back as chords": one vertex of the KiCad zone moved by 0.1 mm."""
    board, _ = _kicad(tmp_path)
    text = board.read_text(encoding="utf-8")
    zone_at = text.index("(zone")
    point = re.compile(r"\(xy (\S+) (\S+)\)").search(text, zone_at)
    assert point is not None
    moved = f"(xy {float(point.group(1)) + 0.1:.6f} {point.group(2)})"
    board.write_text(text[: point.start()] + moved + text[point.end() :], encoding="utf-8")
    back = convert(board, to="altium", allow_lossy=True, verify=False)
    ((reason, count),) = _zone_row(back).items()
    assert reason.startswith(ZONE_ARCS_EDITED) and count == 1
    (document,) = _write(back, tmp_path / "back").glob("*.PcbDoc")
    vertices, _ = _polygon(document)
    assert all(v.kind == 0 for v in vertices) and len(vertices) > 8


def test_a_rewrite_keeps_the_polygon(tmp_path: Path) -> None:
    """Scenario "A rewrite keeps the polygon": the read document written again with ``rewrite=True``."""
    (tmp_path / "a").mkdir()
    design = AltiumBackend().read(_source(tmp_path / "a")).design
    written = write_design(design, allow_lossy=True, rewrite=True, pour="outline")
    name = next(n for n in written.files if n.lower().endswith(".pcbdoc"))
    (polygon,) = read_pcbdoc(written.files[name], file=name).polygons
    assert len(polygon.vertices) > 8


def test_import_to_python_expresses_the_zone(tmp_path: Path) -> None:
    """c0427 task 2.4: ``import --to python`` writes the arc polygon as code, no longer ``zone-outline``."""
    (tmp_path / "a").mkdir()
    reply = imported(tmp_path, _source(tmp_path / "a"))
    assert reply.exit_code in (0, 5), reply.error
    kinds = {row["kind"] for row in reply.result.get("unexpressed", [])}
    assert "zone-outline" not in kinds
