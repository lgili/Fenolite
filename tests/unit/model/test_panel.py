# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The panel model (capability design-model, "Panels in the model"; change c0173)."""

from __future__ import annotations

import json

import pytest
from _schema import load, validate

from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model import canonical
from fenolite.model.panel import (
    FiducialSet,
    Panel,
    PanelArray,
    PanelFiducial,
    PanelFrame,
    PanelHole,
    PanelLimits,
    PanelSource,
    Separation,
    TabSpec,
    ToolingSet,
)
from fenolite.panel import ids

MM = 1_000_000


def _panel() -> Panel:
    return Panel(
        id=ids.panel_id(),
        name="p",
        source=PanelSource("../board/board.kicad_pcb", "ab" * 32, "kicad"),
        array=PanelArray(2, 4, gap_x=2 * MM, gap_y=3 * MM),
        frame=PanelFrame(top=5 * MM, bottom=5 * MM),
        separations=(Separation("columns", "tabs"), Separation("rows", "vscore")),
        tabs=TabSpec(holes=6),
        fiducials=(PanelFiducial("F1", Point(10 * MM, 3 * MM)),),
        tooling_holes=(PanelHole("T1", Point(5 * MM, 2_500_000)),),
        fiducial_set=FiducialSet(sides=("top", "bottom")),
        tooling_set=ToolingSet(),
        limits=PanelLimits(gap=MM),
    )


def test_a_panel_round_trips() -> None:
    panel = _panel()
    text = canonical.dumps(panel)
    again = canonical.loads(text, Panel)
    assert again == panel
    assert canonical.dumps(again) == text
    problems = validate(json.loads(text), load("fenolite.model.v0/panel.json"))
    assert problems == []


def test_defaults_are_omitted() -> None:
    data = canonical.to_data(Panel(id=ids.panel_id(), name="p", source=PanelSource("b.kicad_pcb")))
    assert data == {"id": ids.panel_id(), "name": "p", "source": {"path": "b.kicad_pcb"}}


def test_a_rotation_that_is_no_quarter_turn() -> None:
    with pytest.raises(ValueError, match="rotation"):
        PanelArray(rotation=45_000_000)
    assert PanelArray(rotation=270_000_000).rotation == 270_000_000


@pytest.mark.parametrize(
    ("make", "word"),
    [
        (lambda: PanelArray(rows=0), "rows"),
        (lambda: PanelArray(gap_x=-1), "gap_x"),
        (lambda: TabSpec(drill=0), "drill"),
        (lambda: TabSpec(drill=600_000, inset=300_000), "inset"),
        (lambda: PanelFiducial("F", Point(0, 0), copper=2 * MM, mask=MM), "mask"),
        (lambda: Separation("diagonal", "tabs"), "between"),  # type: ignore[arg-type]
        (lambda: PanelLimits(gap=-5), "gap"),
    ],
)
def test_bad_values_are_refused(make: object, word: str) -> None:
    with pytest.raises(ValueError, match=word):
        make()  # type: ignore[operator]


def test_an_edge_set_separated_twice() -> None:
    with pytest.raises(ValueError, match="separated twice"):
        Panel(
            id=ids.panel_id(),
            name="p",
            source=PanelSource("b.kicad_pcb"),
            separations=(Separation("rows", "tabs"), Separation("rows", "vscore")),
        )


def test_key_rows() -> None:
    assert ids.copy_id(1, 2) == derived_id("pcy", "panel", "copy:1.2")
    assert ids.panel_id() == derived_id("pnl", "panel", "panel")
    assert ids.tab_id("x1.1", 2) == derived_id("ptb", "panel", "tab:x1.1:2")
    assert ids.vscore_id("y", 1) == derived_id("pvs", "panel", "vscore:y:1")
    assert ids.fiducial_id("PFID1") == derived_id("pfd", "panel", "fiducial:PFID1")
    assert ids.tooling_id("PTH1") == derived_id("ptl", "panel", "tooling:PTH1")
    assert {prefix for prefix, _ in ids.KEYS.values()} == {"pnl", "pcy", "ptb", "pvs", "pfd", "ptl"}


def test_method_of_an_unnamed_edge_set() -> None:
    panel = _panel()
    assert (panel.method("columns"), panel.method("rows"), panel.method("rails")) == ("tabs", "vscore", "tabs")
