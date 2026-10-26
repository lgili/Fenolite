# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper-to-edge clearance on the running ``kicad-cli`` (capability kicad-oracle, "Edge clearance agrees
with KiCad"; hypotheses H-K-EDGE-CENTRE, H-K-EDGE-RESOLVE and H-K-EDGE-AGREE; change c0169).

The boards are those of ``_edgebench``."""

from __future__ import annotations

import _edgebench as eb
import pytest
from _probes import major, run

pytestmark = pytest.mark.needs_kicad


def test_centre_measures_to_the_edge_line() -> None:
    assert run("edge-centre-047") == "present", "copper 0.47 mm from the edge is not reported against 0.5 mm"
    assert run("edge-centre-052") == "absent", "copper 0.52 mm from the edge is reported"


def test_centre_does_not_count_the_edge_stroke() -> None:
    # the slot's edge is drawn 0.1 mm wide: counted, its half would bring 0.548 mm under 0.5 mm
    for label in ("0548", "0552", "060"):
        assert run(f"edge-centre-{label}") == "absent", label


@pytest.mark.parametrize("rule", sorted(eb.RESOLVE_RULES))
def test_resolve_rule_governs_over_the_board_minimum(rule: str) -> None:
    # the project's minimum is 0.5 mm; a board-wide rule governs below and above it
    minimum = float(eb.RESOLVE_RULES[rule])
    for gap, value in eb.RESOLVE_GAPS.items():
        wanted = "present" if value < minimum else "absent"
        assert run(f"edge-resolve-{rule}-{gap}") == wanted, (rule, gap)


def test_agree_items_equal() -> None:
    assert run("edge-agree") == "equal", eb.agree_sides()
    sides = eb.agree_sides()
    assert sides is not None
    # every item 0.45 mm from a ring is reported, none at 0.55 mm
    wanted = {"T_IN", "A_IN", "V_IN", "P1", "C_IN", "S_IN", "L_IN", "L_TRACK"}
    assert {x for x in sides[1] if not x.startswith("f_")} == wanted


def test_agree_fills() -> None:
    # 10.0.x judges the stored fill as Fenolite does; 9.0.x reports nothing for it (H-K-COPPER-ZONES)
    wanted = "equal" if major() >= 10 else "different"
    assert run("edge-agree-fill") == wanted, eb.agree_sides()
