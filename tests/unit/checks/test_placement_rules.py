# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``checks.placement.judge`` on authored layouts (capability placement, "Placement rules judged"; change
c0113). The layouts are built by hand, with round values invented for these tests; the last test judges a
rule on the reading of an Altium document that the test builds."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _altium_built import EXAMPLES, build_altium_example
from _placecheck import MM, Layout

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.placement import PlacementRules, RuleReport, board_box, empty_counts, judge, rules_of
from fenolite.geometry import BBox
from fenolite.model.design import Design
from fenolite.model.rules import PadSelection, ProximityRule, RuleSet

ROUTED = EXAMPLES / "blink_routed" / "design.py"
LED = ProximityRule("led", (PadSelection("D1"),), (PadSelection("R1", "2"),), 5 * MM)


def decoupling(c6: tuple[float, float], *, severity: str = "error") -> RuleReport:
    layout = Layout()
    layout.part("U1", ("7", 10, 10, "VDD"), ("8", 10, 12, "GND"), path="U1")
    layout.part("C5", ("1", 11.5, 10, "VDD"), ("2", 11.5, 11, "GND"), path="C5")
    layout.part("C6", ("1", c6[0], c6[1], "VDD"), ("2", c6[0], c6[1] + 1, "GND"), path="C6")
    design, pads = layout.build()
    rule = ProximityRule(
        "dec",
        (PadSelection("C5", "1"), PadSelection("C6", "1")),
        (PadSelection("U1", "7"),),
        2 * MM,
        severity,  # type: ignore[arg-type]
    )
    return judge(design, PlacementRules((rule,)), pads=pads)


def test_decoupling_rule_met_and_missed() -> None:
    report = decoupling((14, 10))
    (found,) = report.issues
    assert (found.code, found.severity, found.where) == ("placement.too-far", "error", "C6")
    for word in ("dec", "U1-7", "4 mm", "2 mm"):
        assert word in found.message, found.message
    assert report.counts == {"near": {"judged": 2, "failed": 1, "skipped": 0}}
    assert report.judged == 2


def test_decoupling_rule_takes_the_severity_of_the_rule() -> None:
    (found,) = decoupling((14, 10), severity="warning").issues
    assert (found.code, found.severity) == ("placement.too-far", "warning")


def test_distance_equal_to_the_limit_holds() -> None:
    report = decoupling((12, 10))
    assert report.issues == ()
    assert report.counts == {"near": {"judged": 2, "failed": 0, "skipped": 0}}


def test_a_distance_just_above_the_limit_is_printed_above_it() -> None:
    (found,) = decoupling((11, 11.732051)).issues
    assert found.code == "placement.too-far"
    assert "is 2.000001 mm from U1-7" in found.message
    assert "is 2 mm from" not in found.message


def test_any_pad_of_a_part_and_any_anchor_pad_count() -> None:
    layout = Layout()
    layout.part("U1", ("1", 10, 10, "A"), ("2", 30, 10, "B"), path="U1")
    layout.part("Y1", ("1", 20, 20, "A"), ("2", 29, 10, "B"), path="Y1")
    design, pads = layout.build()
    near = ProximityRule(
        "xtal", (PadSelection("Y1"),), (PadSelection("U1", "1"), PadSelection("U1", "2")), MM
    )
    assert judge(design, PlacementRules((near,)), pads=pads).issues == ()
    far = dataclasses.replace(near, anchor=(PadSelection("U1", "1"),))
    (found,) = judge(design, PlacementRules((far,)), pads=pads).issues
    assert found.where == "Y1" and "U1-1" in found.message


def test_a_path_on_both_sides_is_at_distance_zero() -> None:
    layout = Layout()
    layout.part("U1", ("1", 10, 10, "A"), path="ch1/U1")
    layout.part("C1", ("1", 40, 10, "A"), path="ch1/C1")
    design, pads = layout.build()
    rule = ProximityRule(
        "ch1", (PadSelection("ch1/C1"), PadSelection("ch1/U1")), (PadSelection("ch1/U1"),), 15 * MM
    )
    report = judge(design, PlacementRules((rule,)), pads=pads)
    assert [(i.code, i.where) for i in report.issues] == [("placement.too-far", "C1")]
    assert "ch1/C1" in report.issues[0].message
    assert report.counts == {"near": {"judged": 2, "failed": 1, "skipped": 0}}


def test_an_index_picks_one_pad_in_the_footprints_pad_order() -> None:
    layout = Layout()
    layout.part("U1", ("1", 10, 10, "A"), path="U1")
    layout.part("J1", ("S", 40, 10, "A"), ("S", 10.5, 10, "A"), path="J1")
    design, pads = layout.build()

    def issues(index: int | None) -> list[str]:
        rule = ProximityRule("j", (PadSelection("J1", "S", index),), (PadSelection("U1", "1"),), MM)
        return [i.code for i in judge(design, PlacementRules((rule,)), pads=pads).issues]

    assert issues(None) == [] and issues(1) == []
    assert issues(0) == ["placement.too-far"]
    assert issues(2) == ["placement.rule-unresolved"]


def test_unresolved_and_skipped_rules() -> None:
    layout = Layout()
    layout.part("U1", ("1", 10, 10, "A"), path="U1")
    layout.part("C7", ("1", 60, 10, "A"), path="C7")  # outside the 50 mm × 30 mm box
    design, pads = layout.build()
    rules = PlacementRules(
        (
            ProximityRule("gone", (PadSelection("ch9/C1"),), (PadSelection("U1"),), MM),
            ProximityRule("off", (PadSelection("C7"),), (PadSelection("U1", "1"),), MM),
            ProximityRule("pad", (PadSelection("U1", "9"),), (PadSelection("U1", "1"),), MM),
            ProximityRule("anchor", (PadSelection("U1"),), (PadSelection("U9", "1"),), MM),
        )
    )
    report = judge(design, rules, pads=pads)
    assert [(i.code, i.severity, i.where) for i in report.issues] == [
        ("placement.rule-skipped", "info", "C7"),
        ("placement.rule-unresolved", "error", "U1"),
        ("placement.rule-unresolved", "error", "U9"),
        ("placement.rule-unresolved", "error", "ch9/C1"),
    ]
    by_where = {i.where: i.message for i in report.issues}
    assert "rule off" in by_where["C7"] and "rule gone" in by_where["ch9/C1"]
    assert "pad 9 of U1" in by_where["U1"] and "rule anchor" in by_where["U9"]
    assert report.counts == {"near": {"judged": 0, "failed": 0, "skipped": 1}}
    assert report.judged == 0


def test_an_anchor_off_the_board_skips_the_rule() -> None:
    layout = Layout()
    layout.part("U1", ("1", 70, 10, "A"), path="U1")
    layout.part("C1", ("1", 10, 10, "A"), path="C1")
    design, pads = layout.build()
    rule = ProximityRule("dec", (PadSelection("C1"),), (PadSelection("U1", "1"),), MM)
    report = judge(design, PlacementRules((rule,)), pads=pads)
    assert [(i.code, i.where) for i in report.issues] == [("placement.rule-skipped", "U1")]
    assert report.counts == {"near": {"judged": 0, "failed": 0, "skipped": 1}}


def test_without_a_box_every_footprint_is_on_the_board() -> None:
    layout = Layout(width=None)
    layout.part("U1", ("1", 10, 10, "A"))
    layout.part("C7", ("1", 900, 10, "A"))
    design, pads = layout.build()
    assert board_box(design) is None
    rule = ProximityRule("far", (PadSelection("C7"),), (PadSelection("U1", "1"),), MM)
    report = judge(design, PlacementRules((rule,)), pads=pads)  # the paths fall back to the references
    assert [(i.code, i.where) for i in report.issues] == [("placement.too-far", "C7")]


def test_board_box_from_the_outline_and_from_the_edge_graphics() -> None:
    wanted = BBox(0, 0, 50 * MM, 30 * MM)
    assert board_box(Layout().build()[0]) == wanted
    assert board_box(Layout(edge=True).build()[0]) == wanted


def test_issues_are_sorted_and_the_function_is_pure() -> None:
    layout = Layout()
    layout.part("U1", ("1", 10, 10, "A"), path="U1")
    for n, ref in enumerate(("C3", "C1", "C2")):
        layout.part(ref, ("1", 30 + n, 10, "A"), path=ref)
    design, pads = layout.build()
    rules = PlacementRules(
        (
            ProximityRule("b", (PadSelection("C3"), PadSelection("C1")), (PadSelection("U1"),), MM),
            ProximityRule("a", (PadSelection("C2"), PadSelection("C1")), (PadSelection("U1"),), MM),
        )
    )
    first, second = judge(design, rules, pads=pads), judge(design, rules, pads=tuple(reversed(pads)))
    keys = [(i.code, i.where, i.message) for i in first.issues]
    assert keys == sorted(keys) and [i.where for i in first.issues] == ["C1", "C1", "C2", "C3"]
    assert first == second


def test_rules_of_a_model_and_no_rules() -> None:
    design = Design.new("rules", seed=0)
    assert not rules_of(design) and not rules_of(None)
    assert design.rules is not None
    held = dataclasses.replace(design, rules=RuleSet(id=design.rules.id, proximity=(LED,)))
    assert rules_of(held) == PlacementRules((LED,)) and bool(rules_of(held))
    empty = judge(design, PlacementRules(), pads=())
    assert empty.issues == () and empty.counts == empty_counts()
    assert empty_counts() == {"near": {"judged": 0, "failed": 0, "skipped": 0}}


def test_a_board_read_from_an_altium_document(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A board read from an Altium document": the same verdict as on the KiCad build."""
    code, folder, error = build_altium_example(monkeypatch, tmp_path, ROUTED)
    assert code == 0, error
    backend = AltiumBackend()
    reading = backend.read_documents(backend.documents(folder / "blink_routed.PcbDoc")).pcb
    assert reading is not None
    altium = judge(reading.design, PlacementRules((LED,)), pads=backend.board_pads(reading.design))
    assert [(i.code, i.severity, i.where) for i in altium.issues] == [("placement.too-far", "error", "D1")]

    import fenolite.cli.main as cli_main

    out = tmp_path / "kicad"
    assert cli_main.main(["build", str(ROUTED), "--out", str(out), "--confirm", "--json"]) == 0
    board = read_board(out / "blink_routed.kicad_pcb")
    kicad = judge(board, PlacementRules((LED,)), pads=KicadBackend().board_pads(board))
    assert [(i.code, i.where) for i in kicad.issues] == [("placement.too-far", "D1")]
    assert kicad.counts == altium.counts == {"near": {"judged": 1, "failed": 1, "skipped": 0}}
