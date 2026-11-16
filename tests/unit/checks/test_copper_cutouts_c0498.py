# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper next to a cut-out or a keep-out (change c0498, tasks 1.3, 2.1, 2.2 and 2.4; finding F40 of the
proposal). Every board is authored here: a track 0.03 mm from a slot ring under a 0.5 mm edge clearance, in
the rule forms of design D5 step 1, and a track beside a keep-out under Altium's keep-out ``Clearance``."""

from __future__ import annotations

from _coppercheck import Copper, mm

from fenolite.backends.base import EdgeRing
from fenolite.checks.copper import EDGE_CODE, KEEPOUT_CLEARANCE, check_copper
from fenolite.core.coords import Point
from fenolite.model.board import Keepout
from fenolite.model.rules import Selector

BOARD = EdgeRing("board", (Point(0, 0), Point(mm(50), 0), Point(mm(50), mm(30)), Point(0, mm(30))))
SLOT = EdgeRing(
    "cutout 1", (Point(mm(20), mm(10)), Point(mm(30), mm(10)), Point(mm(30), mm(12)), Point(mm(20), mm(12)))
)
"""A free board cut-out (2 × 10 mm) inside the board."""


def bench() -> Copper:
    """A 0.25 mm track whose copper lies 0.03 mm below the slot."""
    copper = Copper()
    copper.track("GND", Point(mm(20), mm(12.155)), Point(mm(30), mm(12.155)), locator="Tracks6/Data#0")
    return copper


def codes(copper: Copper, **more: object) -> list[str]:
    report = check_copper(copper.build(), pads=[], edges=[BOARD, SLOT], **more)  # type: ignore[arg-type]
    return [i.code for i in report.issues]


def test_a_rule_of_scope_all_finds_the_slot() -> None:
    copper = bench()
    copper.rule("BoardOutlineClearance", mm(0.5), kind="edge_clearance")
    assert codes(copper).count(EDGE_CODE) == 1


def test_a_board_minimum_finds_the_slot() -> None:
    assert codes(bench(), min_edge_clearance=mm(0.5)).count(EDGE_CODE) == 1


def test_an_edge_rule_that_selects_nothing() -> None:
    """Scenario "An edge rule that selects nothing" (D5 step 2): F40's silent case before change c0498. An
    edge rule scoped to another net leaves the track's edge limit unset; one ``copper.rules-incomplete``
    (``where`` = ``edge``) now names it, and the report is ``UNVERIFIED``."""
    copper = bench()
    copper.rule("BoardOutlineClearance", mm(0.5), Selector("net", "VCC"), kind="edge_clearance")
    report = check_copper(copper.build(), pads=[], edges=[BOARD, SLOT])
    (said,) = [i for i in report.issues if i.code == "copper.rules-incomplete"]
    assert said.where == "edge" and said.severity == "warning"
    assert (
        said.message.startswith("1 copper item(s) judged against no board edge")
        and "Tracks6/Data#0" in said.message
    )
    assert report.summary["edges"]["unset_items"] == 1  # type: ignore[index]
    assert report.evidence.level.value == "UNVERIFIED"


def test_no_edge_rule_says_nothing() -> None:
    """Without any edge rule or board minimum the board has no edge limit to miss: no warning."""
    assert "copper.rules-incomplete" not in codes(bench())


def keepout_bench(gap: float) -> Copper:
    """A track whose copper lies ``gap`` mm from a keep-out square on F.Cu, and Altium's keep-out
    ``Clearance`` of 0.5 mm (``read.rules.keepout_clearance_rule``: one side ``item_kind keepout``)."""
    copper = Copper()
    edge = mm(10) + mm(0.125) + mm(gap)
    copper.track("GND", Point(mm(5), edge), Point(mm(15), edge), locator="Tracks6/Data#0")
    square = (Point(mm(5), mm(5)), Point(mm(15), mm(5)), Point(mm(15), mm(10)), Point(mm(5), mm(10)))
    copper.keepouts.append(
        Keepout(id="kpo_00000000-0000-4000-8000-0000000c0498", outline=square, layers=("F.Cu",), name="K1")
    )
    copper.rule("keep-out clearance", mm(0.5), Selector("item_kind", "keepout"))
    return copper


def test_a_pour_beside_a_keepout() -> None:
    """Scenario "A pour beside a keep-out": copper 0.03 mm from a keep-out under a 0.5 mm keep-out clearance
    gives one ``copper.keepout-clearance``; at 0.6 mm it gives none."""
    report = check_copper(keepout_bench(0.03).build(), pads=[])
    (found,) = [f for f in report.findings if f.code == KEEPOUT_CLEARANCE]
    assert found.items[0].where == "Tracks6/Data#0" and found.items[1].where == "K1"
    assert abs(found.gap - mm(0.03)) <= 1 and found.clearance == mm(0.5)
    assert "keep-out clearance" in found.message and report.summary["keepout_clearance"] == 1
    assert "copper.clearance" not in [f.code for f in report.findings]  # the rule judges no copper pair
    clear = check_copper(keepout_bench(0.6).build(), pads=[])
    assert (
        KEEPOUT_CLEARANCE not in [f.code for f in clear.findings] and "keepout_clearance" not in clear.summary
    )
