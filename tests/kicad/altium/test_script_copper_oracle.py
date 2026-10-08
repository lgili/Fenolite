# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper that a design script declares reaches the Altium document (capability altium-build, "Script
copper oracle"; change c0053; hypothesis ``H-A-PCB-CU-KICAD``).

``fenolite build examples/blink_routed/design.py --target altium`` writes ``blink_routed.PcbDoc``;
``kicad-cli pcb import --format altium`` turns that document into a KiCad board, read with
``backends.kicad.pcb.read_board``. The expected copper is what the script declares: its intents resolved by
``lens.build.build_design``, never the document as Fenolite reads it. Every position is compared relative
to each board's outline corner, within 10 nm. ``pcb import`` exists from 10.0 only (S-0166).

Not compared, and why:

- **Net classes.** ``pcb import`` writes no project file, where KiCad 10 keeps net classes.
- **Uuids.** The document holds none of the script copper's uuids; KiCad gives the imported items new ones.

A pass checks only what KiCad's importer reads; it settles no Altium row.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest
from _kicad import oracle_env
from _resources import kicad_cli, kicad_cli_major

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver
from fenolite.backends.kicad.pcb import read_board
from fenolite.cli._script import run_design_script
from fenolite.core.coords import Point
from fenolite.dsl import copper, placements, to_model
from fenolite.lens.build import build_design
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "examples" / "blink_routed" / "design.py"
NAME = "blink_routed"
TOLERANCE = 10


@dataclass(frozen=True)
class RoundTrip:
    code: int
    stdout: str
    report: dict[str, object]
    declared: Design
    back: Design
    envelope: dict[str, object]


def declared() -> Design:
    """What the script declares: its model with the copper intents resolved, in memory."""
    design = run_design_script(SCRIPT).design
    built = build_design(
        to_model(design),
        placements(design),
        name=NAME,
        copper=design.copper,  # type: ignore[arg-type]
        resolver=LibraryResolver(LibraryConfig(target_major=10, project_dir=SCRIPT.parent)),
        copper_intents=copper(design),
    )
    assert built.files and not [found for found in built.issues if found.severity == "error"]
    return built.design


@cache
def round_trip() -> RoundTrip:
    cli = kicad_cli()
    assert cli is not None
    if kicad_cli_major() == 9:
        pytest.skip("no `pcb import` before 10.0")
    root = Path(tempfile.mkdtemp(prefix="fenolite-script-copper-"))
    out = root / "B"
    argv = ["build", str(SCRIPT), "--out", str(out), "--target", "altium", "--confirm", "--json"]
    stdout, stderr = io.StringIO(), io.StringIO()
    saved = os.environ.get("KICAD_CONFIG_HOME")
    os.environ["KICAD_CONFIG_HOME"] = str(root / "config")
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = stdout, stderr
    try:
        code = cli_main.main(argv)
        expected = declared()
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        if saved is None:
            del os.environ["KICAD_CONFIG_HOME"]
        else:
            os.environ["KICAD_CONFIG_HOME"] = saved
    assert code == 0, stderr.getvalue() + stdout.getvalue()
    envelope = json.loads(stdout.getvalue())
    assert envelope["result"]["copper"]["source"] == "script"
    target, report = root / "back.kicad_pcb", root / "r.json"
    proc = subprocess.run(
        [cli, "pcb", "import", "--format", "altium", "--report-format", "json",
         "--report-file", str(report), "-o", str(target), str(out / f"{NAME}.PcbDoc")],
        capture_output=True, text=True, timeout=300, check=False,
        env=oracle_env(root / "config"),
    )  # fmt: skip
    assert target.is_file(), proc.stdout + proc.stderr
    found = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
    return RoundTrip(
        proc.returncode, proc.stdout + proc.stderr, found, expected, read_board(target), envelope
    )


def corner(design: Design) -> Point:
    """The outline's top-left corner: of the ``Edge.Cuts`` graphics, else of ``Board.outline``."""
    assert design.board is not None
    points = [p for g in design.board.graphics if g.layer == "Edge.Cuts" for p in g.points]
    if not points and design.board.outline is not None:
        points = list(design.board.outline.points)
    assert points
    return Point(min(p.x for p in points), min(p.y for p in points))


def rel(point: Point, origin: Point) -> tuple[int, int]:
    return (point.x - origin.x, point.y - origin.y)


def close(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return abs(a[0] - b[0]) <= TOLERANCE and abs(a[1] - b[1]) <= TOLERANCE


def nets(design: Design) -> dict[str, str]:
    return {net.id: net.name for net in design.circuit.nets}


def test_import_has_no_error_and_two_copper_layers() -> None:
    trip = round_trip()
    assert trip.code == 0, trip.stdout
    assert trip.report.get("errors") == []
    assert not [
        line for line in trip.stdout.splitlines() if line.startswith("Error:") or "Error during" in line
    ]
    back = trip.back.board
    assert back is not None
    assert [layer.name for layer in back.layers if layer.kind == "copper"] == ["F.Cu", "B.Cu"]


def test_script_to_altium_and_back() -> None:
    """Scenario "Script to Altium and back": the imported copper equals the script's, item for item."""
    trip = round_trip()
    source, back = trip.declared.board, trip.back.board
    assert source is not None and back is not None
    here, there = corner(trip.declared), corner(trip.back)
    names, got = nets(trip.declared), nets(trip.back)
    assert (len(source.tracks), len(source.arcs), len(source.vias), len(source.zones)) == (11, 0, 7, 0)
    summary = trip.envelope["result"]["copper"]  # type: ignore[index]
    assert (summary["tracks"], summary["vias"]) == (11, 7)  # type: ignore[index]
    assert {names[t.net_id or ""] for t in source.tracks} == {"LED_DRV", "LED_A", "GND"}
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
            and all(any(close(rel(p, there), e) for p in (t.start, t.end)) for e in ends)
        ]
        assert len(found) == 1, (track.layer, ends)
    assert len(back.vias) == len(source.vias)
    for via in source.vias:
        found_vias = [
            v
            for v in back.vias
            if close(rel(v.position, there), rel(via.position, here))
            and got.get(v.net_id or "") == names.get(via.net_id or "")
            and (v.diameter, v.drill, v.via_type, set(v.layers))
            == (via.diameter, via.drill, "through", {"F.Cu", "B.Cu"})
        ]
        assert len(found_vias) == 1, rel(via.position, here)
    assert len(back.arcs) == 0 and len(back.zones) == 0


def test_footprints_are_at_the_placements_of_the_script() -> None:
    trip = round_trip()
    source, back = trip.declared.board, trip.back.board
    assert source is not None and back is not None
    here, there = corner(trip.declared), corner(trip.back)
    refs = {c.id: c.ref for c in trip.declared.circuit.components}
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
