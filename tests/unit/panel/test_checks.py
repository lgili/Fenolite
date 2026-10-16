# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The panel checks on the fixtures (capability board-panels, "Panel checks"; change c0173)."""

from __future__ import annotations

import dataclasses
import runpy
from functools import cache

from _panels import PANELS, committed_board

from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.dsl import Panel, to_model
from fenolite.model.design import Design
from fenolite.model.panel import Panel as ModelPanel
from fenolite.model.panel import PanelArray, PanelFiducial, TabSpec
from fenolite.panel.checks import check_panel, renamed_nets
from fenolite.panel.layout import layout

MM = 1_000_000


@cache
def board() -> Design:
    return read_board(committed_board(10))


def script(name: str) -> ModelPanel:
    panel = runpy.run_path(str(PANELS / f"{name}.py"))["panel"]
    assert isinstance(panel, Panel)
    return to_model(panel)


def findings(panel: ModelPanel) -> list[tuple[str, str, str]]:
    laid = layout(panel, board())
    return [(i.code, i.severity, i.message) for i in check_panel(panel, laid, board())]


def test_vscore_copper_near_a_score_line() -> None:
    found = [f for f in findings(script("vscore")) if f[0] == "panel.vscore-copper"]
    assert len(found) == 2, found
    assert all(f[1] == "error" and "0.3 mm" in f[2] and "0.45 mm" in f[2] for f in found)
    assert {"copy 1 (row 1, column 1)" in f[2] or "copy 3 (row 2, column 1)" in f[2] for f in found} == {True}


def test_vscore_findings_beside_the_copper() -> None:
    codes = {(f[0], f[1]) for f in findings(script("vscore"))}
    assert ("panel.vscore-thickness", "info") not in codes, "the fixture states its thickness"
    assert all(code != "panel.tab-copper" for code, _ in codes)


def test_tabs_and_mixed_are_clean() -> None:
    for name in ("tabs", "mixed"):
        errors = [f for f in findings(script(name)) if f[1] == "error"]
        assert errors == [], (name, errors)


def test_tabs_has_no_warning() -> None:
    assert findings(script("tabs")) == []


def test_a_gap_too_narrow() -> None:
    panel = script("tabs")
    narrow = dataclasses.replace(panel, array=PanelArray(2, 4, MM, MM))
    found = [f for f in findings(narrow) if f[0] == "panel.gap"]
    assert found and all(f[1] == "error" and "1 mm" in f[2] and "1.2 mm" in f[2] for f in found)


def test_tab_copper_with_an_inset() -> None:
    panel = dataclasses.replace(script("mixed"), tabs=TabSpec(inset=200_000))
    found = [f for f in findings(panel) if f[0] == "panel.tab-copper"]
    assert found and all("0.1 mm" in f[2] and "0.25 mm" in f[2] for f in found), found


def test_fiducials_off_the_rails() -> None:
    panel = dataclasses.replace(script("mixed"), fiducials=(PanelFiducial("F1", Point(20 * MM, 20 * MM)),))
    found = [f for f in findings(panel) if f[0] == "panel.fiducial-place"]
    assert any("not on a rail" in f[2] for f in found)
    assert any("1 fiducial(s) on the top side" in f[2] for f in found)


def test_few_holes_and_a_small_panel() -> None:
    panel = dataclasses.replace(script("mixed"), tabs=TabSpec(holes=3))
    codes = {f[0] for f in findings(panel)}
    assert "panel.tab-count" in codes


def test_renamed_nets() -> None:
    names = renamed_nets(["GND", "VIN"], 2)
    assert list(names) == ["B1/GND", "B1/VIN", "B2/GND", "B2/VIN"]
