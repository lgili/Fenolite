# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Interaction tests of the viewer page (capability viewer-visual-tests; change c0191): selection,
measurement, unit switch and cross-probe, by mouse and key events on the canvas of the page of the authored
`blink` project."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest
from _visual import job, run

pytestmark = pytest.mark.needs_browser

EVENTS = """
const r = cv.getBoundingClientRect();
const at = (x, y) => {
  const [X, Y] = w2s(x, y);
  return { clientX: r.left + X, clientY: r.top + Y, bubbles: true, view: window };
};
const click = (x, y) => {
  cv.dispatchEvent(new MouseEvent("mousedown", at(x, y)));
  cv.dispatchEvent(new MouseEvent("mouseup", at(x, y)));
};
const key = k => window.dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true }));
const pad = label => S.pads.find(p => p.label === label);
const settle = () => new Promise(ok => setTimeout(ok, 50));
"""


def _act(pages: dict[str, Path], tmp_path: Path, script: str) -> Any:
    (reply,) = run(
        [job("interaction", pages["blink_project"], tmp_path, script=EVENTS + script, shot="")], tmp_path
    )
    assert reply["errors"] == [], reply["errors"]
    return reply["result"]


def test_selection(pages: dict[str, Path], tmp_path: Path) -> None:
    found = _act(
        pages, tmp_path, 'const p = pad("R1-1"); click(p.x, p.y); await settle(); return $("info").innerText;'
    )
    assert "R1" in found and "Net:" in found


def test_measurement_snaps_to_pad_centres(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
    const a = pad("R1-1"), b = pad("R1-2"); key("m");
    click(a.x + 0.01, a.y); click(b.x, b.y - 0.01); await settle();
    return { text: $("coord").textContent, d: Math.hypot(a.x - b.x, a.y - b.y) };
    """
    found = _act(pages, tmp_path, script)
    assert f"{found['d']:.3f} mm" in found["text"]  # snapped to the two centres, not the clicks
    assert not math.isclose(found["d"], 0)


def test_unit_switch(pages: dict[str, Path], tmp_path: Path) -> None:
    script = 'key("q"); await settle(); return { unit: $("bUnit").textContent, one: fmtLen(25.4) };'
    assert _act(pages, tmp_path, script) == {"unit": "mil", "one": "1000.00 mil"}


def test_cross_probe(pages: dict[str, Path], tmp_path: Path) -> None:
    script = """
    const p = pad("U1-1"); const e = at(p.x, p.y);
    cv.dispatchEvent(new MouseEvent("dblclick", e));
    for (let k = 0; k < 100 && !(S.kind === "schematic" && SCH.selComp >= 0); k++) await settle();
    return { doc: DOC.name, kind: S.kind, ref: SCH.selComp >= 0 ? S.comps[SCH.selComp].ref : null };
    """
    assert _act(pages, tmp_path, script) == {"doc": "blink.SchDoc", "kind": "schematic", "ref": "U1"}
