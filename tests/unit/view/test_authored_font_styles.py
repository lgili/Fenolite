# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Execute the authored stroke renderer; these controls do not use native glyph resources."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def test_authored_italic_changes_strokes_and_defaults_stay_exact() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    font = (ROOT / "viewer/src/core/font.ts").read_text().replace("export function", "function")
    draw = (ROOT / "viewer/src/sch/draw.ts").read_text()
    draw = draw[draw.index("export function drawStrokeText") : draw.index("export function drawText")]
    script = (
        font
        + "\n"
        + draw.replace("export function", "function")
        + """
const t = ["", 100, 200, 60, 40, 8, 0, "center", "center", false, "Ab", -1];
const normal = textPolylines(t), explicit = textPolylines(t, false), italic = textPolylines(t, true);
const S = { fonts: [{italic: false}, {italic: true}] }, view = {s: 100};
let points = [];
const ctx = {beginPath() {}, stroke() {},
  moveTo(x,y) {points.push([x,y]);}, lineTo(x,y) {points.push([x,y]);}};
const p = {x:100,y:200,sz:60,gw:40,th:8,rot:0,h:"center",v:"center",s:"Ab",font:0};
drawStrokeText(p, 1); const renderedNormal = points; points = [];
drawStrokeText({...p,font:1}, 1); const renderedItalic = points;
console.log(JSON.stringify({normal, explicit, italic, renderedNormal, renderedItalic}));
"""
    )
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True, timeout=30)
    value = json.loads(result.stdout)
    assert value["normal"] == value["explicit"]
    assert value["normal"] != value["italic"]
    assert value["renderedNormal"] != value["renderedItalic"]
    for normal, italic in zip(value["normal"], value["italic"], strict=True):
        for (x, y), (sx, sy) in zip(normal, italic, strict=True):
            assert sy == y
            assert sx == pytest.approx(x - (y - 200) / 5)
