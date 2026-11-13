# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A lossy refusal lists what is lost (capability conversion, "A lossy refusal lists what is lost";
change c0495, (d)). The design and the report are authored for Fenolite."""

from __future__ import annotations

import dataclasses

from fenolite.convert import LossyConversionError, lossy_issue, lost_examples
from fenolite.convert.report import ConversionReport
from fenolite.core.coords import Point
from fenolite.model.board import Board, Graphic
from fenolite.model.design import Design


def _design() -> Design:
    lines = tuple(
        Graphic(
            id=f"g{k}", layer="Mech.20", kind="line", points=(Point(0, 0), Point(1_000_000, k)), width=100_000
        )
        for k in range(5)
    )
    design = Design.new("lossy", seed=0)
    return dataclasses.replace(design, board=Board(id="brd", graphics=lines))


def test_drawings_on_layers_kicad_lacks() -> None:
    """Scenario "Drawings on layers KiCad lacks": the message names the kind, its count and each reason
    with its count, and the issue holds the same counts as the report."""
    lost = {
        "drawing": {
            "on a mechanical layer with no KiCad layer": ("g0", "g1", "g2"),
            "dimension": ("g3", "g4"),
        }
    }
    report = ConversionReport.of(source={"drawing": 7}, lost=lost)
    (row,) = [row for row in report.rows if row.lost]
    error = LossyConversionError((lossy_issue(row),), report, lost_examples(_design(), report))
    message = str(error)
    assert "would lose 5 item(s) of the source" in message
    assert "drawing: 5 (2 dimension, 3 on a mechanical layer with no KiCad layer)" in message or (
        "drawing: 5 (3 on a mechanical layer with no KiCad layer, 2 dimension)" in message
    )
    assert "for example Mech.20 line, Mech.20 line, Mech.20 line" in message
    (found,) = error.issues
    assert found.code == "convert.lossy" and found.where == "drawing"
    assert "5 of 7 drawing item(s)" in found.message
