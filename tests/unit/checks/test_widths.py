# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper narrower than the governing ``track_width`` rule (``checks.widths``; change c0403). Authored
benches: nets, classes, rules and widths are made up for these tests."""

from __future__ import annotations

from _coppercheck import Copper, mm

from fenolite.checks.codes import ISSUE_CODES
from fenolite.checks.widths import TRACK_WIDTH, track_width_findings
from fenolite.core.coords import Point
from fenolite.model.board import Keepout
from fenolite.model.rules import Selector

A, B = Point(mm(1), mm(1)), Point(mm(9), mm(1))


def board_minimum(made: Copper, minimum: float = 0.2) -> None:
    """The board-wide rule that ``design.rules.minimum(track_width=...)`` gives."""
    made.rule("min_track_width", mm(minimum), kind="track_width")


def test_track_below_a_board_wide_rule() -> None:
    made = Copper()
    board_minimum(made)
    made.track("VIN", A, B, width=162_000)
    made.track("VIN", B, Point(mm(9), mm(4)), width=150_000)
    made.track("VIN", A, Point(mm(1), mm(4)), width=mm(0.2))  # equal to the min: clean
    made.arc("GND", A, Point(mm(5), mm(3)), B, width=100_000)
    made.track("LED", A, B, width=mm(0.3))
    found = track_width_findings(made.build())
    assert [(i.code, i.severity, i.where) for i in found] == [
        (TRACK_WIDTH, "error", "GND"),
        (TRACK_WIDTH, "error", "VIN"),
    ]
    vin = found[1]
    assert "2 track(s) or arc(s)" in vin.message and "0.15mm" in vin.message
    assert "0.2mm min of track_width rule 'min_track_width'" in vin.message
    assert ISSUE_CODES[TRACK_WIDTH] == ("error", "warning")


def test_class_rule_of_higher_priority_allows_a_narrower_width() -> None:
    made = Copper()
    made.netclass("Fine", None)
    board_minimum(made)
    made.rule("fine_width", mm(0.1), Selector("netclass", "Fine"), priority=1, kind="track_width")
    made.net("SIG", "Fine")
    made.track("SIG", A, B, width=mm(0.12))
    made.track("OTHER", A, B, width=mm(0.12))
    found = track_width_findings(made.build())
    assert [i.where for i in found] == ["OTHER"]


def test_layer_limited_rule_only_on_its_layer() -> None:
    made = Copper()
    made.rule("outer_width", mm(0.3), layers=("B.Cu",), kind="track_width")
    made.track("SIG", A, B, width=mm(0.2), layer="F.Cu")
    design = made.build()
    assert track_width_findings(design) == ()
    made.track("SIG", A, B, width=mm(0.2), layer="B.Cu")
    (found,) = track_width_findings(made.build())
    assert found.where == "SIG" and "outer_width" in found.message and "1 track(s)" in found.message


def test_ignore_severity_silences_the_item() -> None:
    made = Copper()
    board_minimum(made)
    made.rule("free", mm(0.2), Selector("net", "TEST*"), priority=1, severity="ignore", kind="track_width")
    made.track("TEST1", A, B, width=mm(0.05))
    assert track_width_findings(made.build()) == ()


def test_warning_rule_gives_a_warning_and_other_kinds_are_not_width_rules() -> None:
    made = Copper()
    made.rule("soft", mm(0.2), severity="warning", kind="track_width")
    made.rule("gap", mm(0.5))  # a clearance rule: no width limit
    made.track(None, A, B, width=mm(0.1))
    (found,) = track_width_findings(made.build())
    assert found.severity == "warning" and found.where == "<no net>"


def test_ids_limit_the_judgement_and_the_code_is_the_callers() -> None:
    made = Copper()
    board_minimum(made)
    made.track("A", A, B, width=mm(0.1))
    added = made.track("B", A, B, width=mm(0.1))
    design = made.build()
    assert [i.where for i in track_width_findings(design)] == ["A", "B"]
    found = track_width_findings(design, ids={added.id}, code="route.width-below-minimum", hint="h")
    assert [(i.code, i.where, i.hint) for i in found] == [("route.width-below-minimum", "B", "h")]


def test_area_rule_selects_the_copper_inside_the_area() -> None:
    made = Copper()
    made.keepouts.append(
        Keepout(
            id="kpo_00000000-0000-4000-8000-000000000001",
            outline=(Point(0, 0), Point(mm(10), 0), Point(mm(10), mm(5)), Point(0, mm(5))),
            layers=("F.Cu", "B.Cu"),
            name="HV",
        )
    )
    made.rule("hv_width", mm(0.5), Selector("area", "HV"), kind="track_width")
    made.track("IN", A, B, width=mm(0.3))
    made.track("OUT", Point(mm(1), mm(20)), Point(mm(9), mm(20)), width=mm(0.3))
    assert [i.where for i in track_width_findings(made.build())] == ["IN"]


def test_no_rules_no_findings() -> None:
    made = Copper()
    made.track("SIG", A, B, width=1)
    assert track_width_findings(made.build()) == ()
