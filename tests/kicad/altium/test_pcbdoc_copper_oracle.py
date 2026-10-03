# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper of the PCB document against ``kicad-cli pcb import`` (capability altium-pcb-writer, "Copper
oracle"; change c0038; hypothesis ``H-A-PCB-CU-KICAD``).

The routed sample's ``routed.PcbDoc`` and the plane variant ``p0`` are imported with ``kicad-cli pcb import
--format altium`` and read back with ``backends.kicad.pcb.read_board``. KiCad moves the board on its sheet,
so every position is compared relative to the outline's corner, within 10 nm. ``pcb import`` exists from
10.0 only (S-0166).

What the import cannot show, and so is not compared here:

- **Net classes and rules.** ``pcb import`` writes no project file, and KiCad 10 keeps net classes there.
- **A plane's net.** KiCad maps the stack by chain position: a plane of the chain becomes a copper layer of
  type ``power``. It makes zones only from split-plane records, and Fenolite writes none, so the net of
  the plane is not in the imported board.

A pass checks only what KiCad's importer reads; it settles no Altium row.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest
from _altium_copper import NAME, PLANE, at, plane_model, routed_build, routed_model
from _resources import kicad_cli, kicad_cli_major

from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.model.board import Zone
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad

TOLERANCE = 10
ALLOWED_WARNING = re.compile(r"Layer 'Internal Plane \d+' could not be mapped and will be skipped\.")
"""The only warnings ``pcb-copper.md`` lists: one per internal plane that is outside the stack."""
LAYER_ROW = re.compile(r'\((\d+) "([^"]+\.Cu)" (\w+)')


@dataclass(frozen=True)
class Imported:
    code: int
    stdout: str
    report: dict[str, object]
    board: Design
    text: str


def priority_model() -> Design:
    """The sample with one more zone of priority 2 on ``F.Cu``, authored for the priority check."""
    model = routed_model()
    assert model.board is not None
    vin = next(net.id for net in model.circuit.nets if net.name == "VIN")
    first = Zone(
        id="zon_00000000-0000-4000-8000-0000000000aa",
        outline=(at(2, 20), at(8, 20), at(8, 27), at(2, 27)),
        layers=("F.Cu",),
        net_id=vin,
        priority=2,
    )
    return dataclasses.replace(
        model, board=dataclasses.replace(model.board, zones=(*model.board.zones, first))
    )


MODELS = {
    "sample": (routed_model, {}),
    "plane": (plane_model, {"planes": PLANE}),
    "priority": (priority_model, {}),
}


@cache
def imported(name: str) -> tuple[Imported, Design]:
    cli = kicad_cli()
    assert cli is not None
    if kicad_cli_major() == 9:
        pytest.skip("no `pcb import` before 10.0")
    make, kwargs = MODELS[name]
    model = make()
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        output = routed_build(root / "build", model, **kwargs)
        assert not [found for found in output.issues if found.severity == "error"]
        source, target, report = root / f"{NAME}.PcbDoc", root / "b.kicad_pcb", root / "r.json"
        source.write_bytes(output.files[f"{NAME}.PcbDoc"])
        env = {**os.environ, "KICAD_CONFIG_HOME": str(root / "config")}
        proc = subprocess.run(
            [cli, "pcb", "import", "--format", "altium", "--report-format", "json",
             "--report-file", str(report), "-o", str(target), str(source)],
            capture_output=True, text=True, timeout=300, env=env, check=False,
        )  # fmt: skip
        assert target.is_file(), proc.stdout + proc.stderr
        found = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
        text = target.read_text(encoding="utf-8")
        result = Imported(proc.returncode, proc.stdout + proc.stderr, found, read_board(target), text)
    return result, model


def corner_of_model(model: Design) -> Point:
    assert model.board is not None and model.board.outline is not None
    points = model.board.outline.points
    return Point(min(p.x for p in points), min(p.y for p in points))


def corner_of_import(board: Design) -> Point:
    assert board.board is not None
    points = [p for g in board.board.graphics if g.layer == "Edge.Cuts" for p in g.points]
    assert points
    return Point(min(p.x for p in points), min(p.y for p in points))


def close(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return abs(a[0] - b[0]) <= TOLERANCE and abs(a[1] - b[1]) <= TOLERANCE


def relative(point: Point, corner: Point) -> tuple[int, int]:
    return (point.x - corner.x, point.y - corner.y)


def check_import(name: str, *, tracks: int, vias: int, zones: int, plane_warnings: int) -> None:
    result, _model = imported(name)
    assert result.code == 0, result.stdout
    assert result.report.get("errors") == []
    statistics = result.report.get("statistics")
    assert isinstance(statistics, dict)
    assert (statistics.get("tracks"), statistics.get("vias"), statistics.get("zones")) == (
        tracks,
        vias,
        zones,
    )
    assert statistics.get("footprints") == 3
    lines = result.stdout.splitlines()
    assert not [line for line in lines if line.startswith("Error:") or "Error during" in line]
    warnings = [line for line in lines if "Warning:" in line]
    assert all(ALLOWED_WARNING.search(line) for line in warnings), warnings
    assert len(warnings) == plane_warnings
    assert result.report.get("warnings") in ([], None)


def check_copper(name: str) -> None:
    """Every track, arc, via and zone layer of the model is in the imported board, and nothing else."""
    result, model = imported(name)
    assert model.board is not None and result.board.board is not None
    board = result.board.board
    here, there = corner_of_model(model), corner_of_import(result.board)
    names = {net.id: net.name for net in model.circuit.nets}
    got_names = {net.id: net.name for net in result.board.circuit.nets}
    planes = MODELS[name][1].get("planes", {})
    assert len(board.tracks) == len(model.board.tracks)
    for track in model.board.tracks:
        ends = {relative(track.start, here), relative(track.end, here)}
        found = [
            t
            for t in board.tracks
            if t.layer == track.layer
            and got_names.get(t.net_id or "") == names[track.net_id or ""]
            and t.width == track.width
            and all(any(close(relative(p, there), e) for e in ends) for p in (t.start, t.end))
        ]
        assert len(found) == 1, (track.layer, names[track.net_id or ""], ends)
    assert len(board.arcs) == len(model.board.arcs)
    for arc in model.board.arcs:
        ends = {relative(arc.start, here), relative(arc.end, here)}
        found_arcs = [
            a
            for a in board.arcs
            if a.layer == arc.layer
            and got_names.get(a.net_id or "") == names[arc.net_id or ""]
            and a.width == arc.width
            and close(relative(a.mid, there), relative(arc.mid, here))
            and all(any(close(relative(p, there), e) for e in ends) for p in (a.start, a.end))
        ]
        assert len(found_arcs) == 1, (arc.layer, ends)
    assert len(board.vias) == len(model.board.vias)
    for via in model.board.vias:
        found_vias = [
            v
            for v in board.vias
            if close(relative(v.position, there), relative(via.position, here))
            and got_names.get(v.net_id or "") == names[via.net_id or ""]
        ]
        assert len(found_vias) == 1
        (got,) = found_vias
        assert (got.via_type, got.layers) == ("through", ("F.Cu", "B.Cu"))
        assert (got.diameter, got.drill) == (via.diameter, via.drill)
    wanted = [
        (layer, names[zone.net_id or ""], [relative(p, here) for p in zone.outline])
        for zone in model.board.zones
        for layer in zone.layers
        if layer not in planes
    ]
    assert len(board.zones) == len(wanted)
    for layer, net, outline in wanted:
        found_zones = [
            z
            for z in board.zones
            if z.layers == (layer,)
            and got_names.get(z.net_id or "") == net
            and len(z.outline) == len(outline)
            and all(any(close(relative(p, there), q) for q in outline) for p in z.outline)
        ]
        assert len(found_zones) == 1, (layer, net)
        assert found_zones[0].fills == ()  # the polygons are unpoured: KiCad gets no fill


def layer_rows(name: str) -> list[tuple[str, str]]:
    result, _model = imported(name)
    return [(layer, kind) for _number, layer, kind in LAYER_ROW.findall(result.text)]


def test_import_of_the_routed_sample() -> None:
    """Scenario "Import of the routed sample": four copper layers and the sample's copper, no error."""
    check_import("sample", tracks=6, vias=3, zones=2, plane_warnings=16)
    assert layer_rows("sample") == [
        ("F.Cu", "signal"),
        ("In1.Cu", "signal"),
        ("In2.Cu", "signal"),
        ("B.Cu", "signal"),
    ]
    check_copper("sample")


def test_import_of_the_plane_variant() -> None:
    """Scenario "Import of the plane variant": ``In1.Cu`` is a ``power`` layer by its position in the chain,
    and the variant's track on ``In2.Cu`` (written on Mid-Layer 2) is found with its net and ends. The
    plane's net is not imported (see the module text)."""
    check_import("plane", tracks=5, vias=3, zones=1, plane_warnings=15)
    assert layer_rows("plane") == [
        ("F.Cu", "signal"),
        ("In1.Cu", "power"),
        ("In2.Cu", "signal"),
        ("B.Cu", "signal"),
    ]
    check_copper("plane")
    result, _model = imported("plane")
    assert result.board.board is not None
    nets = {net.id: net.name for net in result.board.circuit.nets}
    inner = [
        (t.layer, nets.get(t.net_id or "")) for t in result.board.board.tracks if t.layer.startswith("In")
    ]
    assert inner == [("In2.Cu", "LED_A")]
    assert not [z for z in result.board.board.zones if "In1.Cu" in z.layers]


def test_zone_priority_of_the_sample_and_of_a_higher_zone() -> None:
    """The zone of higher model priority gets the higher KiCad priority; among the polygons of one zone the
    one poured first (the lower pour index) does."""
    check_import("priority", tracks=6, vias=3, zones=3, plane_warnings=16)
    check_copper("priority")
    result, _model = imported("priority")
    assert result.board.board is not None
    priority = {zone.layers[0]: zone.priority for zone in result.board.board.zones}
    assert priority["F.Cu"] > priority["In1.Cu"] > priority["B.Cu"]
