# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Edge measurement of the viewer page (capability review-tools, scenario "Two pads"; change c0189): the
page's own functions, run in Node, against an authored pair of pads and against the gap `analyze` reports."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

import fenolite.cli.main as cli_main
from fenolite.cli.cmd_view import scene_of
from fenolite.view.export import template

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


def _measure(pairs: list[tuple[list[Any], list[Any]]]) -> list[dict[str, Any]]:
    html = template()
    start, end = html.index("// ---- edge (c0189)"), html.index("// ---- end edge")
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: the measure functions are not run")
    script = html[start:end] + (
        f"const out = {json.dumps(pairs)}.map(([a, b]) => edgeBetween(a, b));"
        "console.log(JSON.stringify(out));"
    )
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, encoding="utf-8", check=True, timeout=60
    )
    return json.loads(done.stdout)


def _rect(x0: float, y0: float, x1: float, y1: float) -> list[Any]:
    return ["F.Cu", "p", [[x0, y0, x1, y0, x1, y1, x0, y1]], 0, 0, ""]


def test_two_pads() -> None:
    """Scenario "Two pads": two rectangular pads 0.2 mm apart (scene units are µm)."""
    (found, touching, track) = _measure(
        [
            ([_rect(0, 0, 500, 400)], [_rect(700, 100, 1200, 300)]),
            ([_rect(0, 0, 500, 400)], [_rect(400, 100, 900, 300)]),
            ([["F.Cu", "s", [0, 1000, 1000, 1000, 200], 0, -1, ""]], [_rect(0, 0, 500, 400)]),
        ]
    )
    assert found["d"] == pytest.approx(200) and found["a"] == [500, 100] and found["b"] == [700, 100]
    assert touching["d"] == 0
    assert track["d"] == pytest.approx(500)  # 1000 - 100 half width - 400


def test_equals_the_gap_analyze_reports(capsys: pytest.CaptureFixture[str]) -> None:
    """The distance equals the clearance `analyze` reports for the same pair within 1 µm (the requirement)."""
    code = cli_main.main([
        "analyze", str(BOARD), "--kinds", "clearance", "--pair", "GND", "VCC", "--json"
    ])  # fmt: skip
    assert code == 0
    (row,) = json.loads(capsys.readouterr().out)["result"]["distances"]
    (gap,) = [g for g in row["gaps"] if g["items"] == ["D1-1", "/kicad_pcb/segment[1]"]]
    scene = scene_of(BOARD)
    pad = [p for p in scene["prims"] if p[0] == gap["layer"] and p[5] == "D1-1"]
    track = [p for p in scene["prims"] if p[0] == gap["layer"] and p[5] == "track 2"]
    assert pad and track
    (found,) = _measure([(pad, track)])
    assert abs(found["d"] * 1000 - gap["low"]) <= 1000  # µm in the scene, nm in the reply
