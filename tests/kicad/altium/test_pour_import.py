# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad's importer reads a computed pour (change c0215; capability altium-pcb-writer, "Poured regions",
scenario "KiCad imports the pour"; hypothesis ``H-A-POUR-KICAD``).

An authored board is written with the pour mode ``computed`` and imported with ``kicad-cli pcb import
--format altium`` (10.0 only, S-0166). Each zone that the engine poured must hold, in the imported board,
fills equal to the written pieces: compared relative to the board's lower-left corner, as an XOR area of at
most 10 nm along the boundary. A pass says what KiCad's importer reads; it settles no Altium row.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
from functools import cache
from pathlib import Path

import pytest
from _altium_pour import FILENAME, Board, clearance, pad, track, via, zone
from _kicad import oracle_env
from _resources import kicad_cli, kicad_cli_major

from fenolite.analysis.fills import unfracture
from fenolite.backends.altium.pour import PourResult, area, pour_reading, read_pour
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.geometry import Polygon
from fenolite.geometry.boolean.clipper import ClipperBackend
from fenolite.model.board import ZoneSettings
from fenolite.model.design import Design

pytestmark = [
    pytest.mark.needs_kicad,
    pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra"),
]
TOLERANCE_NM = 10
BOARD = Board(
    zones=(
        zone("z1", "GND"),
        zone("z2", "VIN", layer="B.Cu", settings=ZoneSettings(connection="solid")),
    ),
    pads=(
        pad("p1", "VIN", 10, 10, shape="circle"),
        pad("p2", "GND", 20, 10, kind="thru_hole", shape="circle", size=(1.6, 1.6), drill=0.8),
        pad("p3", "GND", 30, 10, size=(1.2, 0.8)),
        pad("p4", "VIN", 30, 20, kind="thru_hole", shape="rect", size=(1.6, 1.6), drill=0.8),
    ),
    tracks=(track("t1", "VIN", (5, 20), (15, 20)),),
    vias=(via("v1", "GND", 25, 25),),
    rules=(clearance(0.25),),
)


@cache
def imported() -> tuple[int, dict[str, object], Design, PourResult, tuple[Point, ...]]:
    cli = kicad_cli()
    assert cli is not None
    if kicad_cli_major() == 9:
        pytest.skip("no `pcb import` before 10.0")
    data = BOARD.write().data
    reading = read_pour(data, file=FILENAME)
    edges = reading.edges[0].points if reading.edges else ()
    result = pour_reading(reading)
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        source, target, report = root / FILENAME, root / "b.kicad_pcb", root / "r.json"
        source.write_bytes(data)
        proc = subprocess.run(
            [cli, "pcb", "import", "--format", "altium", "--report-format", "json",
             "--report-file", str(report), "-o", str(target), str(source)],
            capture_output=True, text=True, timeout=300, env=oracle_env(root / "config"), check=False,
        )  # fmt: skip
        assert target.is_file(), proc.stdout + proc.stderr
        found = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
        board = read_board(target)
    return proc.returncode, found, board, result, tuple(edges)


def _corner(points: tuple[Point, ...] | list[Point]) -> Point:
    return Point(min(p.x for p in points), min(p.y for p in points))


def _moved(poly: Polygon, by: Point) -> Polygon:
    def ring(points: tuple[Point, ...]) -> tuple[Point, ...]:
        return tuple(Point(p.x - by.x, p.y - by.y) for p in points)

    return Polygon(ring(poly.outer), tuple(ring(h) for h in poly.holes))


def test_kicad_imports_the_pour() -> None:
    """Scenario "KiCad imports the pour" on an authored board: the import succeeds, and each poured zone holds
    fills equal to the written pieces within 10 nm along their boundary."""
    code, report, board, result, edges = imported()
    assert code == 0 and report.get("errors") == []
    assert board.board is not None
    corner = _corner([p for g in board.board.graphics if g.layer == "Edge.Cuts" for p in g.points])
    mine = _corner(list(edges))
    names = {net.id: net.name for net in board.circuit.nets}
    clipper = ClipperBackend()
    poured = [p for p in result.polygons if p.poured and p.pieces]
    assert len(poured) == 2
    for pour in poured:
        (zone_found,) = [
            z
            for z in board.board.zones
            if z.layers == (pour.layer,) and names.get(z.net_id or "") == pour.net
        ]
        fills: list[Polygon] = []
        for fill in zone_found.fills:
            found = unfracture(fill.polygon)
            assert found is not None
            fills.append(_moved(Polygon(found[0], found[1]), corner))
        written = [_moved(piece, mine) for piece in pour.pieces]
        assert len(fills) == len(written), pour.layer
        difference = sum(area(p) for p in clipper.xor(fills, written))
        boundary = sum(
            abs(a.x - b.x) + abs(a.y - b.y)
            for piece in written
            for ring in piece.rings()
            for a, b in zip(ring, (*ring[1:], ring[0]), strict=True)
        )
        assert difference <= TOLERANCE_NM * boundary, (pour.layer, float(difference), boundary)
