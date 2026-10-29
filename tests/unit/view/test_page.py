# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The packaged viewer page (capability board-viewer, "Viewer page"): self-contained, and a standalone page
carries its tree and scenes unchanged."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from fenolite.backends import registry
from fenolite.backends.altium.read.sch import read_schematic
from fenolite.backends.base import BoardFrame
from fenolite.view.export import DATA_MARK, LIVE_MARK, embedded, page, template
from fenolite.view.project import load_tree
from fenolite.view.scene import build_scene
from fenolite.view.schematic import build_schematic_scene

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
SHEET = ROOT / "tests" / "data" / "altium" / "hier" / "altium_hier.SchDoc"


def test_template_is_self_contained() -> None:
    html = template()
    assert DATA_MARK in html and LIVE_MARK in html
    assert re.search(r"https?://", html) is None, "the page loads nothing from the network"
    for element in ("tree", "tablist", "ls", "cv", "gl", "status"):
        assert f'id="{element}"' in html, element


def test_standalone_page_round_trips() -> None:
    """Scenario "Standalone page round-trips"."""
    backend = registry.for_path(BOARD)
    assert backend is not None and isinstance(backend, BoardFrame)
    scene = build_scene(backend.read(BOARD).design, backend, name=BOARD.name, data=BOARD.read_bytes())
    scene["texts"].append(["F.SilkS", 0, 0, 1000, 667, 150, 0.0, "left", "bottom", False, "</script>", -1])
    tree = load_tree(BOARD).to_json()
    html = page(tree, {"doc1": scene}, open_id="doc1")
    assert '</script>"' not in html
    data = embedded(html)
    assert data is not None
    assert data["project"] == tree and data["scenes"]["doc1"] == scene and data["open"] == "doc1"
    assert re.search(r"https?://", html.replace(tree["name"], "")) is None


def test_schematic_scene_round_trips() -> None:
    """Scenario "A schematic scene round-trips through the export" (c0177)."""
    data = SHEET.read_bytes()
    scene = build_schematic_scene(read_schematic(data, file=SHEET.name), name=SHEET.name, data=data)
    tree = load_tree(SHEET).to_json()
    html = page(tree, {"doc1": scene}, open_id="doc1")
    back = embedded(html)
    assert back is not None and back["scenes"]["doc1"] == scene
    assert re.search(r"https?://", html.replace(tree["name"], "")) is None


def test_schematic_interaction_is_in_the_page() -> None:
    """Scenario "The page holds the interaction" (c0177)."""
    html = template()
    for name in ("drawSch", "navList", "sheetTabs", "selNet", "crossProbe", "schDouble", "toMMsch"):
        assert name in html, name
    # c0245: the Navigator is a docked panel that applies to sheets; board-only controls keep their class
    assert 'panel("navigator"' in html and "isSch() && !LIB" in html and "board-only" in html


def test_the_page_reads_the_theme() -> None:
    """Scenario "The page reads the theme" (c0178)."""
    html = template()
    for name in ("S.theme", "sheet.workspace", 'sheet.text === "stroke"', "drawStrokeText", "l.alpha"):
        assert name in html, name


def test_units() -> None:
    """Scenario "Unit conversions" (c0179): the page's own conversion functions, run in Node when it is
    installed."""
    html = template()
    for name in (
        "function fmtLen",
        "function fmtNm",
        'id="bUnit"',
        "function snap(",
        "function measureClick",
    ):
        assert name in html, name
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: the definitions are checked, not run")
    start = html.index("const MIL_MM")
    end = html.index("function fmtPair")
    code = html[start:end].replace("let UNIT = (() =>", "let UNIT = 'mm'; const _u = (() =>")
    script = code + (
        "const out = []; UNIT = 'mm'; out.push(fmtLen(1.2), fmtNm(254000));"
        "UNIT = 'mil'; out.push(fmtLen(1.2), fmtNm(254000)); console.log(JSON.stringify(out));"
    )
    done = subprocess.run(
        [node, "-e", "const localStorage = { getItem: () => null };" + script],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    assert json.loads(done.stdout) == ["1.200 mm", "0.254 mm", "47.24 mil", "10.00 mil"]


def test_libraries_in_the_page() -> None:
    html = template()
    for name in ("function loadLibrary", "function openItem", 'id="libList"', "function toUnits", "padInfo"):
        assert name in html, name


def test_live_page_has_no_data() -> None:
    html = page(live=True)
    assert "const LIVE = true;" in html and embedded(html) is None


def test_review_panels_in_the_page() -> None:
    """Change c0187: the Components and Nets panels, the filter, Find similar, highlight modes and links."""
    html = template()
    for name in (
        'id="compList"',
        'id="netList"',
        'id="hlMode"',
        'id="bSimilar"',
        "function vlist",
        "function clearQuery",
    ):
        assert name in html, name
    assert "HL_ALPHA[st.hl]" in html and 'rel="noopener noreferrer"' in html


def test_check_findings_in_the_page() -> None:
    """Change c0188: markers and the Messages panel of `--check`."""
    html = template()
    for name in (
        'id="msgTable"',
        "function drawCheck",
        "function buildMessages",
        "function checkToMM",
        "SEV_COLOR",
    ):
        assert name in html, name


def test_snap() -> None:
    """Scenario "Snap targets in the page" (change c0193): the measurement snaps to points, then edges, unless
    Alt is held, and the findings are listed by group with the body models drawn in 3D."""
    html = template()
    for name in (
        "function snapEdge(",
        "function buildEdges(",
        "function buildFindings(",
        "function buildMeshes(",
        "function pick3D(",
    ):
        assert name in html, name
    assert "snap(x, y, e.altKey)" in html and "measureClick(e.offsetX, e.offsetY, e.altKey)" in html
