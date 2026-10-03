# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper copied with ``--copper-from`` survives the way back (capability altium-build, "Copper round trip
oracle"; change c0038; hypothesis ``H-A-PCB-CU-ROUNDTRIP``).

The routed sample's KiCad board is written beside its script, ``fenolite build --target altium
--copper-from`` copies its copper into ``routed.PcbDoc``, ``kicad-cli pcb import --format altium`` turns
that document into a KiCad board again, and both boards are read with ``backends.kicad.pcb.read_board``.
Every position is compared relative to each board's outline corner, within 10 nm. ``pcb import`` exists
from 10.0 only (S-0166).

Not compared, and why:

- **Zone fills.** The polygons are written unpoured, so the imported zones have no fill.
- **Net classes.** ``pcb import`` writes no project file, where KiCad 10 keeps net classes.
- **Uuids.** The document holds none of the board's uuids; KiCad gives the imported items new ones.

A pass checks only what KiCad's importer reads; it settles no Altium row.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest
from _altium import blink_tree
from _altium_copper import routed_board_text, routed_script
from _resources import kicad_cli, kicad_cli_major

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad

TOLERANCE = 10


@dataclass(frozen=True)
class RoundTrip:
    code: int
    stdout: str
    report: dict[str, object]
    source: Design
    back: Design
    text: str


@cache
def _folder() -> Path:
    import tempfile

    return Path(tempfile.mkdtemp(prefix="fenolite-copper-from-"))


@cache
def round_trip() -> RoundTrip:
    cli = kicad_cli()
    assert cli is not None
    if kicad_cli_major() == 9:
        pytest.skip("no `pcb import` before 10.0")
    root = _folder()
    project = blink_tree(root / "tree")
    script, board = project / "design.py", project / "routed.kicad_pcb"
    script.write_text(routed_script(), encoding="utf-8")
    board.write_text(routed_board_text(), encoding="utf-8")
    out = root / "B"
    argv = ["build", str(script), "--out", str(out), "--target", "altium", "--copper-from", str(board)]
    stdout, stderr = io.StringIO(), io.StringIO()
    saved = os.environ.get("KICAD_CONFIG_HOME")
    os.environ["KICAD_CONFIG_HOME"] = str(root / "config")
    import sys

    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = stdout, stderr
    try:
        code = cli_main.main([*argv, "--confirm", "--json"])
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        if saved is None:
            del os.environ["KICAD_CONFIG_HOME"]
        else:
            os.environ["KICAD_CONFIG_HOME"] = saved
    assert code == 0, stderr.getvalue() + stdout.getvalue()
    envelope = json.loads(stdout.getvalue())
    assert envelope["result"]["copper"]["source"] == "board"
    target, report = root / "back.kicad_pcb", root / "r.json"
    proc = subprocess.run(
        [cli, "pcb", "import", "--format", "altium", "--report-format", "json",
         "--report-file", str(report), "-o", str(target), str(out / "routed.PcbDoc")],
        capture_output=True, text=True, timeout=300, check=False,
        env={**os.environ, "KICAD_CONFIG_HOME": str(root / "config")},
    )  # fmt: skip
    assert target.is_file(), proc.stdout + proc.stderr
    found = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
    return RoundTrip(
        proc.returncode,
        proc.stdout + proc.stderr,
        found,
        read_board(board),
        read_board(target),
        target.read_text(encoding="utf-8"),
    )


def corner(design: Design) -> Point:
    assert design.board is not None
    points = [p for g in design.board.graphics if g.layer == "Edge.Cuts" for p in g.points]
    assert points
    return Point(min(p.x for p in points), min(p.y for p in points))


def rel(point: Point, origin: Point) -> tuple[int, int]:
    return (point.x - origin.x, point.y - origin.y)


def close(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return abs(a[0] - b[0]) <= TOLERANCE and abs(a[1] - b[1]) <= TOLERANCE


def nets(design: Design) -> dict[str, str]:
    return {net.id: net.name for net in design.circuit.nets}


def test_import_has_no_error_and_four_copper_layers() -> None:
    trip = round_trip()
    assert trip.code == 0, trip.stdout
    assert trip.report.get("errors") == []
    assert not [
        line for line in trip.stdout.splitlines() if line.startswith("Error:") or "Error during" in line
    ]
    for row in ('"F.Cu" signal', '"In1.Cu" signal', '"In2.Cu" signal', '"B.Cu" signal'):
        assert row in trip.text, row


def test_board_to_altium_and_back() -> None:
    """Scenario "Board to Altium and back": the imported copper equals the source board's, item for item."""
    trip = round_trip()
    source, back = trip.source.board, trip.back.board
    assert source is not None and back is not None
    here, there = corner(trip.source), corner(trip.back)
    names, got = nets(trip.source), nets(trip.back)
    assert (len(source.tracks), len(source.arcs), len(source.vias)) == (5, 1, 3)
    assert len(back.tracks) == len(source.tracks)
    for track in source.tracks:
        ends = {rel(track.start, here), rel(track.end, here)}
        found = [
            t
            for t in back.tracks
            if t.layer == track.layer
            and got.get(t.net_id or "") == names.get(track.net_id or "")
            and t.width == track.width
            and all(any(close(rel(p, there), e) for e in ends) for p in (t.start, t.end))
        ]
        assert len(found) == 1, (track.layer, ends)
    assert len(back.arcs) == len(source.arcs)
    for arc in source.arcs:
        ends = {rel(arc.start, here), rel(arc.end, here)}
        found_arcs = [
            a
            for a in back.arcs
            if a.layer == arc.layer
            and got.get(a.net_id or "") == names.get(arc.net_id or "")
            and a.width == arc.width
            and close(rel(a.mid, there), rel(arc.mid, here))
            and all(any(close(rel(p, there), e) for e in ends) for p in (a.start, a.end))
        ]
        assert len(found_arcs) == 1
    assert len(back.vias) == len(source.vias)
    for via in source.vias:
        found_vias = [
            v
            for v in back.vias
            if close(rel(v.position, there), rel(via.position, here))
            and got.get(v.net_id or "") == names.get(via.net_id or "")
            and (v.diameter, v.drill, v.via_type, set(v.layers))
            == (via.diameter, via.drill, "through", set(via.layers))
        ]
        assert len(found_vias) == 1
    wanted = [
        (layer, names.get(zone.net_id or ""), [rel(p, here) for p in zone.outline])
        for zone in source.zones
        for layer in zone.layers
    ]
    assert len(wanted) == 2 and len(back.zones) == len(wanted)
    for layer, net, outline in wanted:
        found_zones = [
            z
            for z in back.zones
            if z.layers == (layer,)
            and got.get(z.net_id or "") == net
            and len(z.outline) == len(outline)
            and all(any(close(rel(p, there), q) for q in outline) for p in z.outline)
        ]
        assert len(found_zones) == 1, (layer, net)


def test_footprints_are_at_the_placements_of_the_source() -> None:
    trip = round_trip()
    source, back = trip.source.board, trip.back.board
    assert source is not None and back is not None
    here, there = corner(trip.source), corner(trip.back)
    refs = {c.id: c.ref for c in trip.source.circuit.components}
    back_refs = {c.id: c.ref for c in trip.back.circuit.components}
    placed = {
        refs[f.component_id]: (rel(f.position, here), f.rotation % 360_000_000, f.side)
        for f in source.footprints
    }
    found = {
        back_refs[f.component_id]: (rel(f.position, there), f.rotation % 360_000_000, f.side)
        for f in back.footprints
    }
    assert sorted(found) == sorted(placed) == ["D1", "R1", "U1"]
    for ref, (position, rotation, side) in placed.items():
        assert close(found[ref][0], position), ref
        assert found[ref][1:] == (rotation, side), ref
