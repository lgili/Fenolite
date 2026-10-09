# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placement rules in the DSL (capability design-dsl, "Placement rules in the DSL"; change c0113): what
``Design.near`` records, what it refuses at the call, and what ``to_model`` writes."""

from __future__ import annotations

import runpy
from collections.abc import Callable
from pathlib import Path

import pytest

from fenolite.dsl import Design, DslError, Module, Net, Part, connect, mm, to_model
from fenolite.model import canonical
from fenolite.model.rules import PadSelection, ProximityRule

BLINK = Path(__file__).resolve().parents[3] / "examples" / "blink_2layer" / "design.py"


def _blink() -> tuple[Design, Part, Part, Part]:
    design = Design("blink")
    design.board(mm(50), mm(30))
    u1 = Part("U1", "Mini:Mini_QFP32_IC")
    r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603")
    d1 = Part("D1", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm")
    design.add(u1, r1, d1)
    connect(Net("LED_DRV"), u1[1], r1[1])
    connect(Net("LED_A"), r1[2], d1[2])
    return design, u1, r1, d1


def _proximity(design: Design) -> tuple[ProximityRule, ...]:
    rules = to_model(design).rules
    assert rules is not None
    return rules.proximity


def test_decoupling_rule_recorded() -> None:
    design, u1, r1, _ = _blink()
    design.near("dec", r1.pad(2), (u1.pad(1), u1.pad(9)), within=mm(3))
    assert _proximity(design) == (
        ProximityRule(
            "dec", (PadSelection("R1", "2"),), (PadSelection("U1", "1"), PadSelection("U1", "9")), 3_000_000
        ),
    )


def test_recorded_sides_take_parts_pads_lists_and_an_index() -> None:
    design, u1, r1, d1 = _blink()
    design.near("xtal", [r1, d1.pad(1, index=0)], u1, within="5mm", severity="warning")
    assert _proximity(design) == (
        ProximityRule(
            "xtal",
            (PadSelection("R1"), PadSelection("D1", "1", 0)),
            (PadSelection("U1"),),
            5_000_000,
            "warning",
        ),
    )


def test_rules_are_written_in_key_order_and_repeats_are_dropped() -> None:
    design, u1, r1, d1 = _blink()
    design.near("z", r1, u1, within=mm(1))
    design.near("a/b", (d1, d1), (u1.pad(1), u1.pad(1)), within=mm(2))
    found = _proximity(design)
    assert [rule.name for rule in found] == ["a/b", "z"]
    assert found[0].parts == (PadSelection("D1"),) and found[0].anchor == (PadSelection("U1", "1"),)


def test_module_expanded_in_path_order() -> None:
    design = Design("channels")
    ch1, fb = Module("ch1"), Module("fb")
    u1, c1, r1 = Part("U1", "Mini:Mini_QFP32_IC"), Part("C1", "Mini:Mini_R"), Part("R1", "Mini:Mini_R")
    fb.add(r1)
    ch1.add(u1, c1, fb)
    design.add(ch1)
    design.near("ch1", ch1, u1, within=mm(15))
    (rule,) = _proximity(design)
    assert rule.parts == (PadSelection("ch1/C1"), PadSelection("ch1/U1"), PadSelection("ch1/fb/R1"))
    assert rule.anchor == (PadSelection("ch1/U1"),)
    assert rule.within == 15_000_000 and rule.severity == "error"


Call = Callable[[Design, Part, Part], None]


@pytest.mark.parametrize(
    ("call", "needle"),
    [
        (lambda d, r1, u1: d.near("a b", r1, u1, within=mm(1)), "must match"),
        (lambda d, r1, u1: d.near("k", (), u1, within=mm(1)), "names nothing"),
        (lambda d, r1, u1: d.near("k", r1, [], within=mm(1)), "names nothing"),
        (lambda d, r1, u1: d.near("k", r1[1], u1, within=mm(1)), "part.pad(<number>)"),
        (lambda d, r1, u1: d.near("k", r1, (u1, u1[9]), within=mm(1)), "part.pad(<number>)"),
        (lambda d, r1, u1: d.near("k", r1, u1, within=mm(0)), "above 0"),
        (lambda d, r1, u1: d.near("k", r1, u1, within=mm(-1)), "above 0"),
        (lambda d, r1, u1: d.near("k", r1, u1, within=mm(1), severity="ignore"), "severity"),
        (lambda d, r1, u1: d.near("k", "R1", u1, within=mm(1)), "takes a part.pad"),
        (lambda d, r1, u1: d.near("k", r1, 7, within=mm(1)), "takes a part.pad"),
    ],
)
def test_refused_calls(call: Call, needle: str) -> None:
    design, u1, r1, _ = _blink()
    with pytest.raises(DslError) as caught:
        call(design, r1, u1)
    assert needle in str(caught.value)
    assert design.near_rules == {}


def test_refused_second_call_of_one_key() -> None:
    design, u1, r1, _ = _blink()
    design.near("dup", r1, u1, within=mm(1))
    with pytest.raises(DslError, match="declared twice"):
        design.near("dup", r1, u1, within=mm(1))
    assert list(design.near_rules) == ["dup"]


def test_parts_and_modules_outside_the_design_are_named_by_to_model() -> None:
    design, u1, r1, _ = _blink()
    stranger = Part("C9", "Mini:Mini_R")
    design.near("far", stranger.pad(1), u1, within=mm(1))
    with pytest.raises(DslError, match="part C9 is not in the design"):
        to_model(design)
    design, u1, r1, _ = _blink()
    design.near("far", r1, Module("lost"), within=mm(1))
    with pytest.raises(DslError, match="module lost is not in the design"):
        to_model(design)
    design, u1, r1, _ = _blink()
    empty = Module("empty")
    design.add(empty)
    design.near("far", empty, u1, within=mm(1))
    with pytest.raises(DslError, match="module empty holds no part"):
        to_model(design)


def test_near_adds_no_anchor_attribute() -> None:
    design, u1, r1, _ = _blink()
    design.near("dec", r1, u1, within=mm(1))
    assert not hasattr(design, "anchor") and not hasattr(r1, "anchor")


def test_unchanged_designs_write_no_proximity_key() -> None:
    design = runpy.run_path(str(BLINK))["design"]
    assert design.near_rules == {}
    texts = canonical.dump_texts(to_model(design))
    assert "proximity" not in texts["rules.json"]
    model = to_model(design)
    assert model.rules is not None and model.rules.proximity == ()


# --- placement keep-outs: ``footprints`` in ``rule_area(forbid=…)`` (change c0113) ----------------------

SQUARE = [(mm(29), mm(6)), (mm(35), mm(6)), (mm(35), mm(12)), (mm(29), mm(12))]
"""A 6 mm × 6 mm square over ``R1`` of the blink, which stands at (32, 9) mm."""


def test_antenna_keepout_in_the_model_the_board_and_the_guard() -> None:
    """Scenario "Antenna keep-out": the model, the board text of the KiCad build, and the finding of the
    build's placement guard on the planned bytes (``cmd_build`` reports it as a warning)."""
    from _buildhelp import blink, build

    from fenolite.cli.cmd_build import placement_guard

    for target in (9, 10):
        design = blink()
        area = design.rule_area("ANT", SQUARE, layers=("F.Cu",), forbid=("footprints",))
        assert area.forbid == ("footprints",)
        board = to_model(design).board
        assert board is not None
        (keepout,) = board.keepouts
        assert keepout.name == "ANT" and keepout.no_footprints and keepout.layers == ("F.Cu",)
        assert not (keepout.no_tracks or keepout.no_vias or keepout.no_pads or keepout.no_copper_pour)
        files = dict(build(design, target).files)
        assert files["blink.kicad_pcb"].decode("utf-8").count("(footprints not_allowed)") == 1
        issues, summary = placement_guard(files, name="blink")
        assert [(i.code, i.severity, i.where) for i in issues] == [("place.keepout", "warning", "R1")]
        assert "ANT" in issues[0].message and summary["counts"] == {"place.keepout": 1}


def test_keepout_on_the_other_face_judges_no_part() -> None:
    from _buildhelp import blink, build

    from fenolite.cli.cmd_build import placement_guard

    design = blink()
    design.rule_area("ANT", SQUARE, layers=("B.Cu",), forbid=("footprints",))  # R1 is on the top side
    issues, _ = placement_guard(dict(build(design, 10).files), name="blink")
    assert not [i for i in issues if i.code.startswith("place.keepout")]
