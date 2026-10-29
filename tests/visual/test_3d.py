# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The 3D view's controls in Chromium (change c0244, scenario "The view cube"): the 2D-only controls are
hidden in 3D, the dock shows the 3D panel instead of Layers, and the cube's Front face turns the camera to the
front."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from _visual import job, run

pytestmark = pytest.mark.needs_browser


def test_view_cube_front_face(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
    const settle = (ms = 50) => new Promise(ok => setTimeout(ok, ms));
    set3D(true); await settle(200);
    const hidden = ["bMeasure", "bMark", "bFlip", "dockTab_layers"].filter(id => !$(id));
    const tab = !!$("dockTab_3d"), cube = getComputedStyle($("cube")).display;
    const face = cubeHits.find(h => h.view === "front"), b = $("cube").getBoundingClientRect();
    const cx = face.poly.reduce((s, p) => s + p[0], 0) / 4, cy = face.poly.reduce((s, p) => s + p[1], 0) / 4;
    $("cube").dispatchEvent(new MouseEvent("click", {clientX: b.left + cx, clientY: b.top + cy,
      bubbles: true}));
    await settle(450);
    setDockTab("3d"); await settle();
    const toggles = [...$("dock3d").querySelectorAll("input[type=checkbox]")].map(i => i.id);
    return {mode: st.mode3d, hidden, tab, cube, yaw: V3.cam.yaw, pitch: V3.cam.pitch, toggles};
    """
    (reply,) = run([job("cube", pages["kicad_board"], tmp_path, script=script, shot="")], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    found = reply["result"]
    assert found["mode"] is True, "WebGL is needed for this test"
    assert sorted(found["hidden"]) == ["bFlip", "bMark", "bMeasure", "dockTab_layers"]
    assert found["tab"] and found["cube"] == "block"
    assert math.isclose(found["yaw"], -math.pi / 2, abs_tol=1e-3) and math.isclose(
        found["pitch"], 0, abs_tol=1e-3
    )
    assert found["toggles"] == ["c3bodies", "c3board", "c3silk", "c3copper"]
