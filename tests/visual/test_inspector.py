# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The docked inspector in Chromium (change c0244): a pad's properties beside the drawing, copied and read in
the other unit; its actions (Zoom to, Show in schematic); the bottom sheet of a narrow window; the net
emphasis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from _visual import job, run

pytestmark = pytest.mark.needs_browser

HELP = """
const settle = (ms = 50) => new Promise(ok => setTimeout(ok, ms));
const r = () => cv.getBoundingClientRect();
const click = (x, y) => { const [X, Y] = w2s(x, y), b = r();
  for (const t of ["mousedown", "mouseup"]) cv.dispatchEvent(new MouseEvent(t, {clientX: b.left + X,
    clientY: b.top + Y,
    bubbles: true, view: window})); };
const key = (k, extra = {}) => window.dispatchEvent(new KeyboardEvent("keydown", {key: k, bubbles: true,
  ...extra}));
const sections = () => [...$("info").querySelectorAll(".isect > summary")].map(s => s.textContent);
const rowOf = label => [...$("info").querySelectorAll(".irow")]
  .find(r => r.querySelector(".ik").textContent === label);
"""


def _act(pages: dict[str, Path], name: str, tmp_path: Path, script: str, **extra: Any) -> Any:
    (reply,) = run(
        [job("inspector", pages[name], tmp_path, script=HELP + script, shot="", **extra)], tmp_path
    )
    assert reply["errors"] == [], reply["errors"]
    return reply["result"]


def test_pad_properties_copied_and_in_mil(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "A pad's size, copied"."""
    script = """
    let copied = null; navigator.clipboard.writeText = async t => { copied = t; };
    const p = S.pads.find(p => p.label === "R1-1"); click(p.x, p.y); await settle();
    const found = sections(), size = rowOf("Size").querySelector(".iv").textContent;
    rowOf("Size").querySelector(".icopy").click(); await settle();
    const first = copied; key("q"); await settle();
    const mil = rowOf("Size").querySelector(".iv").textContent;
    $("inspCopyAll").click(); await settle();
    const dock = $("dock").getBoundingClientRect(), wrap = $("wrap").getBoundingClientRect();
    return {found, size, first, mil, all: copied, apart: dock.left >= wrap.right - 0.5, dockWidth: dock.width,
      drill: !!rowOf("Drill")};
    """
    found = _act(pages, "kicad_board", tmp_path, script)
    assert "Pad" in found["found"] and "Part" in found["found"] and "Net" in found["found"]
    assert found["size"].endswith(" mm") and found["first"] == found["size"]
    assert found["mil"].endswith(" mil") and found["mil"] != found["size"]
    assert "Size: " in found["all"] and "Reference: R1" in found["all"]
    assert found["apart"] and found["dockWidth"] == 320 and found["drill"] is False


def test_missing_values_are_left_out_and_zoom_to(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
    const p = S.pads.find(p => p.label === "R1-1"); click(p.x, p.y); await settle();
    fit(); const before = view.s; $("inspZoom").click(); await settle();
    const b = S.comps.find(c => c.ref === "R1").bbox, [x0, y0] = w2s(b[0], b[1]), [x1, y1] = w2s(b[2], b[3]);
    const inside = Math.min(x0, x1) >= 0 && Math.max(x0, x1) <= r().width && Math.min(y0,
      y1) >= 0 && Math.max(y0, y1) <= r().height;
    const rows = [...$("info").querySelectorAll(".irow")].map(r => r.querySelector(".iv").textContent);
    const actions = [...$("info").querySelectorAll(".inspActs button")].map(b => b.textContent);
    return {zoomed: view.s > before, inside,
      zeros: rows.filter(v => /^0(\\.0+)? ?(mm|mil)?$/.test(v)).length, actions};
    """
    found = _act(pages, "kicad_board", tmp_path, script)
    assert found["zoomed"] and found["inside"]
    assert found["zeros"] == 0
    assert {"Zoom to", "Highlight net", "Select part", "Find similar"} <= set(found["actions"])


def test_cross_probe_from_the_inspector(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "Show in schematic"."""
    script = """
    selectCompAt(S.comps.findIndex(c => c.ref === "U1")); await settle();
    const label = $("inspProbe").textContent; $("inspProbe").click();
    for (let k = 0; k < 100 && !(S.kind === "schematic" && SCH.selComp >= 0); k++) await settle();
    const back = $("inspProbe") ? $("inspProbe").textContent : null;
    return {label, doc: DOC.name, ref: SCH.selComp >= 0 ? S.comps[SCH.selComp].ref : null, back,
      title: $("inspTitle").textContent};
    """
    found = _act(pages, "blink_project", tmp_path, script)
    assert found["label"] == "Show in schematic" and found["doc"] == "blink.SchDoc" and found["ref"] == "U1"
    assert found["back"] == "Show on board" and found["title"] == "U1"


def test_narrow_window_bottom_sheet(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "A 390-pixel window"."""
    script = """
    const shown = () => getComputedStyle($("dock")).display !== "none";
    const before = shown(); const p = S.pads.find(p => p.label === "R1-1"); click(p.x, p.y); await settle();
    const d = $("dock").getBoundingClientRect(), opened = shown();
    key("Escape"); await settle();
    return {before, opened, top: d.top, bottom: d.bottom, height: d.height, h: innerHeight,
      canvas: $("wrap").getBoundingClientRect().width, closed: !shown()};
    """
    found = _act(pages, "kicad_board", tmp_path, script, width=390, height=800)
    assert not found["before"] and found["opened"] and found["closed"]
    assert found["height"] <= 0.6 * found["h"] + 1 and abs(found["bottom"] - found["h"]) <= 1
    assert found["canvas"] == 390


def test_ground_net_emphasis(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "A ground net stands out": a GND track keeps its layer colour, another net's track darkens."""
    script = """
    const dpr = window.devicePixelRatio || 1, g = cv.getContext("2d");
    const gnd = S.nets.indexOf("GND"),
      other = S.prims.find(pr => pr[1] === "s" && pr[3] >= 0 && pr[3] !== gnd);
    const track = S.prims.find(pr => pr[1] === "s" && pr[3] === gnd);
    const mid = pr => [(pr[2][0] + pr[2][2]) / 2, (pr[2][1] + pr[2][3]) / 2];
    const px = pr => { const [X, Y] = w2s(...mid(pr)); return [...g.getImageData(Math.round(X * dpr),
      Math.round(Y * dpr), 1, 1).data].slice(0, 3); };
    for (const l of S.layers) vis.set(l.id, l.id === track[0] || l.id === other[0]); st.cur = track[0];
      draw();
    const before = px(other); selectNetAt(gnd); fit(); draw();
    const colour = S.layers.find(l => l.id === track[0]).color;
    return {gnd: gnd >= 0, on: px(track), want: [1, 3, 5].map(i => parseInt(colour.slice(i, i + 2), 16)),
      before, after: px(other)};
    """
    found = _act(pages, "kicad_board", tmp_path, script)
    assert found["gnd"]
    assert all(abs(a - b) <= 3 for a, b in zip(found["on"], found["want"], strict=True)), found
    assert sum(found["after"]) < sum(found["before"]), found
