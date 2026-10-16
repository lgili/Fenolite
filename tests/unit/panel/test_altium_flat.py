# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The flattened Altium panel (capability altium-pcb-writer, "Flattened panel documents"; capability
altium-build, "Panel project of an Altium board"; capability board-panels, "Panel evidence"; change
c0173)."""

from __future__ import annotations

import hashlib
import re
import runpy
from collections import Counter
from functools import cache
from pathlib import Path

from _panels import PANELS, build_board, committed_board, run, script_for

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import PadRecord, TrackRecord
from fenolite.backends.kicad.outline import edge_outline
from fenolite.dsl import Panel, to_model
from fenolite.panel.build import PanelOutput, altium_panel

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
