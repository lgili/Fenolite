# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The flattened Altium panel (capability altium-pcb-writer, "Flattened panel documents"; capability
altium-build, "Panel project of an Altium board"; capability board-panels, "Panel evidence"; change
c0173)."""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import re
import runpy
from collections import Counter
from functools import cache
from pathlib import Path

import pytest
from _panels import PANELS, build_board, committed_board, run, script_for

from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import PadRecord, RegionRecord, TrackRecord
from fenolite.backends.kicad import fpitems
from fenolite.backends.kicad.outline import edge_outline
from fenolite.convert import pads
from fenolite.core.coords import Point
from fenolite.dsl import Panel, to_model
from fenolite.model.board import Zone
from fenolite.model.design import Design
from fenolite.model.panel import Panel as ModelPanel
from fenolite.panel.altium import flat_files
from fenolite.panel.build import PanelOutput, altium_panel, read_source
from fenolite.panel.layout import PanelLayout, layout

MM = 1_000_000
ROUTE, VCUT = 57, 58
"""Mechanical 1 and 2: the layers named ``Route Tool Path`` and ``V-Cut``."""


@cache
def flat(name: str) -> PanelOutput:
    panel = runpy.run_path(str(PANELS / f"{name}.py"))["panel"]
    assert isinstance(panel, Panel)
    return altium_panel(to_model(panel), committed_board(10))


def test_flattened_panel_document() -> None:
    output = flat("tabs")
    assert not output.refused and output.form == "flat"
    assert [i.code for i in output.notes] == ["altium.panel-flattened"]
    data = output.files["tabs.PcbDoc"]
    doc = read_pcbdoc(data)
    design = import_board(doc, file="tabs.PcbDoc", sha256=hashlib.sha256(data).hexdigest())
    outline = edge_outline(design)
    assert outline is not None and not outline.cutouts
    points = outline.points
    xs, ys = [p.x for p in points], [p.y for p in points]
    assert len(points) == 4  # the panel's rectangle, within the 2.54 nm unit of a document
    assert abs(max(xs) - min(xs) - 180 * MM) <= 2 and abs(max(ys) - min(ys) - 76 * MM) <= 2
    refs = Counter(c.ref for c in design.circuit.components if c.ref)  # the import names no free pad
    assert refs == Counter({"R1": 8, "R2": 8, "D1": 8})
    lines = Counter(t.prefix.layer for t in doc.tracks if isinstance(t, TrackRecord))
    assert lines[ROUTE] == sum(len(ring) for ring in output.layout.routes) and lines[VCUT] == 0
    free = [p for p in doc.pads if isinstance(p, PadRecord) and p.prefix.component is None]
    holes = [p for p in free if p.hole]
    bites = sum(len(t.holes) for t in output.layout.tabs)
    assert len(holes) == bites + 4
    assert all(not p.plated for p in holes)
    assert len([p for p in free if not p.hole]) == 3, "the three fiducials"
    board = open_compound(data).read("Board6/Data").decode("latin-1")
    assert "LAYER57NAME=Route Tool Path" in board and "LAYER58NAME=V-Cut" in board


def test_flattened_panel_holes_have_no_copper() -> None:
    doc = read_pcbdoc(flat("tabs").files["tabs.PcbDoc"])
    for pad in doc.pads:
        if isinstance(pad, PadRecord) and pad.prefix.component is None and pad.hole:
            assert not pad.plated and pad.hole in (236_220, 1_181_102)  # 0.6 mm and 3 mm in 1/10 000 mil


def test_score_lines_on_the_v_cut_layer() -> None:
    output = flat("mixed")
    doc = read_pcbdoc(output.files["mixed.PcbDoc"])
    lines = Counter(t.prefix.layer for t in doc.tracks if isinstance(t, TrackRecord))
    assert lines[VCUT] == len(output.layout.score_lines) == 3


def test_flattened_panel_rebuilds_to_the_same_bytes() -> None:
    panel = runpy.run_path(str(PANELS / "mixed.py"))["panel"]
    first = altium_panel(to_model(panel), committed_board(10)).files
    second = altium_panel(to_model(panel), committed_board(10)).files
    assert first == second


def test_panel_project_files(tmp_path: Path) -> None:
    board = build_board(tmp_path / "B", "altium")
    before = board.read_bytes()
    script = script_for("tabs", tmp_path / "S", board)
    script.write_text(
        script.read_text(encoding="utf-8").replace('board="board.PcbDoc"', 'board="../B/board.PcbDoc"'),
        encoding="utf-8",
    )
    (tmp_path / "S" / "board.PcbDoc").unlink()
    out = tmp_path / "P"
    code, envelope, err = run("panel", str(script), "--out", str(out), "--target", "altium", "--confirm")
    assert code == 0, err
    assert (out / "tabs.PcbDoc").is_file() and (out / "tabs.PrjPcb").is_file()
    project = (out / "tabs.PrjPcb").read_text(encoding="ascii")
    assert re.findall(r"\[Document\d+\]\r?\nDocumentPath=([^\r\n]+)", project) == ["tabs.PcbDoc"]
    assert board.read_bytes() == before
    issues = envelope["issues"]
    assert isinstance(issues, list) and "altium.panel-flattened" in [i["code"] for i in issues]


def test_levels_of_a_reply(tmp_path: Path) -> None:
    code, envelope, err = run(
        "panel", str(PANELS / "tabs.py"), "--out", str(tmp_path / "P"), "--target", "altium", "--dry-run"
    )
    assert code == 0, err
    result = envelope["result"]
    evidence = envelope["evidence"]
    assert isinstance(result, dict) and isinstance(evidence, dict)
    assert result["panel"]["form"] == "flat"
    assert evidence["level"] == "ORACLE-VERIFIED" and evidence["hypotheses"] == ["H-A-PANEL-FLAT"]


def _with_ground_zone() -> tuple[ModelPanel, Design, PanelLayout]:
    """The panel ``tabs`` over its board with one ``GND`` zone on the bottom layer, 1 mm inside the board's
    edge (change c0215); the board projected as ``altium_panel`` projects it."""
    model = to_model(runpy.run_path(str(PANELS / "tabs.py"))["panel"])
    board, _ = read_source(committed_board(10))
    board = pads.project(fpitems.with_footprint_items(board).design)
    outline = edge_outline(board)
    assert outline is not None and board.board is not None
    xs, ys = [p.x for p in outline.points], [p.y for p in outline.points]
    (gnd,) = [net.id for net in board.circuit.nets if net.name == "GND"]
    left, top, right, bottom = min(xs) + MM, min(ys) + MM, max(xs) - MM, max(ys) - MM
    ring = (Point(left, top), Point(right, top), Point(right, bottom), Point(left, bottom))
    zone = Zone(id="zone_gnd", outline=ring, layers=("B.Cu",), net_id=gnd)
    board = dataclasses.replace(board, board=dataclasses.replace(board.board, zones=(zone,)))
    return model, board, layout(model, board)


def test_flat_panel_pours_every_copy() -> None:
    """``fenolite panel --target altium`` takes the pour mode (change c0215): ``computed`` pours the zone of
    each copy and reports it; ``outline`` writes the same polygons without a region of poured copper."""
    if importlib.util.find_spec("pyclipper") is None:
        pytest.skip("needs the geo extra")
    model, board, laid = _with_ground_zone()
    results: list[pcbdoc.PcbDocResult] = []
    files, issues = flat_files(model, laid, board, pour="computed", pour_results=results)
    (written,) = results
    assert written.pour is not None and written.pour.poured == len(laid.copies) and not written.pour.refused
    assert [i.code for i in issues if i.code.startswith("altium.zone")] == ["altium.zones-poured"]
    doc = read_pcbdoc(files["tabs.PcbDoc"])
    poured = {
        r.prefix.polygon for r in doc.regions if isinstance(r, RegionRecord) and r.prefix.polygon is not None
    }
    assert poured == set(range(len(laid.copies)))
    outline_files, _ = flat_files(model, laid, board, pour="outline")
    doc = read_pcbdoc(outline_files["tabs.PcbDoc"])
    assert len(doc.polygons) == len(laid.copies)
    assert not [r for r in doc.regions if isinstance(r, RegionRecord) and r.prefix.polygon is not None]
