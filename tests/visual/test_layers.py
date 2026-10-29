# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Layers panel in Chromium (change c0269): every layer by its full name in groups, visibility and
opacity,
the shortcuts, and the sheet tabs that stay in the bottom bar."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from _visual import job, run

pytestmark = pytest.mark.needs_browser

HELP = """
const settle = (ms = 50) => new Promise(ok => setTimeout(ok, ms));
const key = (k, extra = {}) => window.dispatchEvent(new KeyboardEvent("keydown", {key: k, bubbles: true,
  ...extra}));
const row = id => $("layerList").querySelector(`.lrow[data-layer="${id}"]`);
"""


def _act(pages: dict[str, Path], name: str, tmp_path: Path, script: str, **extra: Any) -> Any:
    (reply,) = run([job("layers", pages[name], tmp_path, script=HELP + script, shot="", **extra)], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    return reply["result"]


def test_names_are_not_cut(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "Long names are not cut"."""
    script = """
    setDockTab("layers"); await settle();
    const rows = [...$("layerList").querySelectorAll(".lrow")];
    const names = rows.map(r => r.querySelector(".lname").textContent);
    const cut = rows.filter(r => { const n = r.querySelector(".lname");
      return n.scrollWidth > n.clientWidth + 1; }).map(r => r.dataset.layer);
    const panel = $("dockLayers"),
      groups = [...$("layerList").querySelectorAll(".lgTitle")].map(g => g.textContent);
    return {names, want: S.layers.map(l => l.name), cut, overflow: panel.scrollWidth > panel.clientWidth,
      tabs: getComputedStyle($("tabs")).display, tabCount: $("tablist").children.length, groups};
    """
    found = _act(pages, "altium_board", tmp_path, script, width=1440, height=900)
    assert sorted(found["names"]) == sorted(found["want"]) and "Board Outline" in found["names"]
    assert found["cut"] == [] and found["overflow"] is False
    assert found["tabs"] == "none" and found["tabCount"] == 0
    assert found["groups"][0] == "Copper" and "Silkscreen" in found["groups"]


def test_opacity_visibility_and_shortcuts(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "Opacity and shortcuts"."""
    script = """
    setDockTab("layers"); await settle();
    const snap = () => cv.toDataURL();
    const start = snap(), slider = row("F.Cu").querySelector(".lop");
    slider.value = "30"; slider.dispatchEvent(new Event("input", {bubbles: true})); await settle();
    const alpha = S.layers.find(l => l.id === "F.Cu").alpha, faded = snap() !== start;
    st.cur = "F.Cu"; key("S", {shiftKey: true}); await settle();
    const single = st.single, drawn = order().map(e => e[0].id).filter(id => !id.startsWith("View."));
    key("S", {shiftKey: true}); const before = st.cur; key("+"); await settle();
    row("B.Cu").querySelector(".leye").click(); await settle();
    return {alpha, faded, single, drawn, before, after: st.cur,
      current: $("layerList").querySelector(".lrow.cur").dataset.layer,
      hidden: vis.get("B.Cu") === false,
        eye: row("B.Cu").querySelector(".leye").getAttribute("aria-pressed")};
    """
    found = _act(pages, "kicad_board", tmp_path, script)
    assert found["alpha"] == 0.3 and found["faded"]
    assert found["single"] and found["drawn"] == ["F.Cu"]
    assert found["after"] != found["before"] and found["current"] == found["after"]
    assert found["hidden"] and found["eye"] == "false"


def test_sheet_tabs_stay(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
    await openDoc(allDocs().find(d => d.kind === "schematic" && d.viewable));
    return {tabs: getComputedStyle($("tabs")).display, n: $("tablist").children.length,
      layersTab: !!$("dockTab_layers")};
    """
    found = _act(pages, "blink_project", tmp_path, script)
    assert found["tabs"] != "none" and found["n"] >= 2 and found["layersTab"] is False
