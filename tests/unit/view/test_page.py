# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The packaged viewer page (capability board-viewer, "Viewer page"): self-contained, and a standalone page
carries its tree and scenes unchanged."""

from __future__ import annotations

import re
from pathlib import Path

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
    assert 'class="sch-only"' in html and "board-only" in html


def test_live_page_has_no_data() -> None:
    html = page(live=True)
    assert "const LIVE = true;" in html and embedded(html) is None
