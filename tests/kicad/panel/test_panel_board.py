# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Panel boards on the running ``kicad-cli`` (capability kicad-file-backend, "Panel boards written";
capability board-panels, "Panel evidence"; hypotheses ``H-K-PANEL-LOAD``, ``H-K-PANEL-DRILL``,
``H-K-PANEL-NETS`` and ``H-K-PANEL-GERBER``; change c0173). The boards are those of ``_panelbench``."""

from __future__ import annotations

import _panelbench as pb
import pytest
from _probes import run

pytestmark = pytest.mark.needs_kicad


def test_panels_load_with_the_copies_findings_only() -> None:
    assert run("panel-load") == "absent", {
        n: pb.counts(r) for n in ("tabs", "mixed", "vscore") if (r := pb.panel_report(n))
    }


def test_panel_drill_holds_the_mouse_bites_and_tooling_holes() -> None:
    assert run("panel-drill") == "equal", pb.drill_hits("tabs")


def test_panel_nets_give_no_unconnected_or_shorting_items() -> None:
    assert run("panel-nets") == "absent"


def test_panel_gerber_of_the_score_layer() -> None:
    assert run("panel-gerber") == "equal", pb.gerber_plot()
    print("score layer .FileFunction:", pb.gerber_function())
