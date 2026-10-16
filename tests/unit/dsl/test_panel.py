# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Panel scripts (capability design-dsl, "Panel scripts"; change c0173)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from fenolite.dsl import DslError, Panel, mm, to_model
from fenolite.model.panel import Separation


def test_a_2_by_2_grid() -> None:
    panel = Panel("p", board="board.kicad_pcb")
    panel.grid(2, 2, gap=mm(2))
    panel.separate("tabs", between="columns")
    model = to_model(panel)
    assert (model.array.rows, model.array.cols, model.array.gap_x) == (2, 2, 2_000_000)
    assert model.separations == (Separation("columns", "tabs"),)
    assert model.source.backend == "kicad"


@pytest.mark.parametrize(
    ("call", "word"),
    [
        (lambda p: p.grid(0, 2), "rows"),
        (lambda p: p.grid(2, 2, rot=45), "rot"),
        (lambda p: p.separate("laser", between="rows"), "method"),
        (lambda p: p.tabs(drill=mm(0)), "drill"),
        (lambda p: p.separate("tabs", between="diagonal"), "between"),
        (lambda p: p.grid(2, 2, gap=2), "gap"),
        (lambda p: p.tabs(drill=mm(0.6), inset=mm(0.3)), "inset"),
        (lambda p: p.fiducial("F 1", mm(1), mm(1)), "ref"),
        (lambda p: p.fiducials(copper=mm(2), mask=mm(1)), "mask"),
        (lambda p: p.rails(top=-1), "top"),
    ],
)
def test_refused_panel_calls(call: Callable[[Panel], None], word: str) -> None:
    panel = Panel("p", board="board.kicad_pcb")
    before = to_model(panel)
    with pytest.raises(DslError, match=word):
        call(panel)
    assert to_model(panel) == before, "a refused call recorded something"


def test_board_files() -> None:
    assert to_model(Panel("p", board="../b/board.PcbDoc")).source.backend == "altium"
    with pytest.raises(DslError, match="board"):
        Panel("p", board="board.brd")
    with pytest.raises(DslError, match="absolute"):
        Panel("p", board="/tmp/board.kicad_pcb")


def test_arranged_once() -> None:
    panel = Panel("p", board="b.kicad_pcb")
    panel.grid(1, 2)
    with pytest.raises(DslError, match="once"):
        panel.fit(mm(100), mm(100))


def test_fit_and_limits() -> None:
    panel = Panel("p", board="b.kicad_pcb", limits={"gap": mm(1), "tab_holes": 6})
    panel.fit(mm(100), mm(80), rot="auto")
    model = to_model(panel)
    assert model.fit is not None and model.fit.auto_rotate and model.fit.width == 100_000_000
    assert (model.limits.gap, model.limits.tab_holes) == (1_000_000, 6)
    with pytest.raises(DslError, match="limit"):
        Panel("p", board="b.kicad_pcb", limits={"nonsense": mm(1)})
    with pytest.raises(DslError, match="tab_holes"):
        Panel("p", board="b.kicad_pcb", limits={"tab_holes": mm(1)})


def test_rails_default_top_and_bottom() -> None:
    panel = Panel("p", board="b.kicad_pcb")
    panel.rails()
    frame = to_model(panel).frame
    assert (frame.top, frame.bottom, frame.left, frame.right) == (5_000_000, 5_000_000, 0, 0)
