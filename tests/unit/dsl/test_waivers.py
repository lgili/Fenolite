# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Waivers in the DSL (capability design-dsl, "Waivers in the DSL"; change c0114)."""

from __future__ import annotations

import pytest

from fenolite.checks.drc_json import RESERVED_SUFFIXES
from fenolite.checks.waivers import COPPER_CODES
from fenolite.dsl import Design, DslError, Part, mm, to_model
from fenolite.dsl.design import DRC_VERDICTS, WAIVED_COPPER
from fenolite.model.findings import Waiver


def design_with(*refs: str) -> tuple[Design, dict[str, Part]]:
    design = Design("waived")
    parts = {ref: Part(ref, "Mini:Mini_R", footprint="Mini:Mini_R_0603") for ref in refs}
    design.add(*parts.values())
    return design, parts


def test_model_holds_the_waiver() -> None:
    """Scenario "A waiver reaches the model"."""
    design, _ = design_with("J1")
    design.waive("copper.clearance", "J1-3", "J1-4", reason="fixed by the mating connector", name="pitch")
    assert to_model(design).findings.waivers == (
        Waiver(
            name="pitch",
            code="copper.clearance",
            items=("J1-3", "J1-4"),
            reason="fixed by the mating connector",
            min_gap=None,
        ),
    )


def test_model_without_a_waiver_has_none() -> None:
    design, _ = design_with("J1")
    assert to_model(design).findings.waivers == ()


def test_default_name_and_parts() -> None:
    """Scenario "Default name and parts": the waivers are sorted by name and a ``Part`` gives its
    reference."""
    design, parts = design_with("TP1", "U1")
    design.waive("kicad.drc.via-dangling", "*", reason="test point")
    design.waive("kicad.drc.courtyards-overlap", parts["TP1"], "U1", reason="stacked by design")
    waivers = to_model(design).findings.waivers
    assert [waiver.name for waiver in waivers] == [
        "kicad.drc.courtyards-overlap:TP1,U1",
        "kicad.drc.via-dangling:*",
    ]
    assert waivers[0].items == ("TP1", "U1")


def test_min_gap_is_a_length_in_nanometres() -> None:
    design, _ = design_with("J1")
    design.waive("copper.clearance", "J1-3", "*", reason="keep-out of the shield", min_gap=mm(0.15))
    (waiver,) = to_model(design).findings.waivers
    assert waiver.min_gap == 150_000 and waiver.reason == "keep-out of the shield"


@pytest.mark.parametrize(
    ("args", "kwargs", "message"),
    [
        (("copper.short", "R1-1", "R2-*"), {}, "exact names only"),
        (("kicad.drc.shorting-items", "R1-?", "R2-1"), {}, "exact names only"),
        (("copper.clearance", "J1-3", "*"), {}, "needs min_gap"),
        (("kicad.drc.rules-not-loaded", "x"), {}, "not a finding"),
        (("kicad.drc.parity-unchecked", "x"), {}, "not a finding"),
        (("kicad.drc.rules-unchecked", "x"), {}, "not a finding"),
        (("parity.net-conflict", "x"), {}, "only copper and DRC findings"),
        (("kicad.erc.pin-not-connected", "x"), {}, "only copper and DRC findings"),
        (("kicad.drc.Silk_Overlap", "x"), {}, "not a finding"),
        (("copper.rules-incomplete", "a", "b"), {}, "not a finding"),
        (("kicad.drc.silk-overlap", "R1"), {"min_gap": mm(0.1)}, "min_gap belongs to copper.clearance"),
        (("copper.clearance", "A", "B"), {"min_gap": mm(0)}, "positive length"),
        (("copper.clearance", "A", "B"), {"reason": " "}, "one non-empty line"),
        (("copper.clearance", "A", "B"), {"reason": "one\ntwo"}, "one non-empty line"),
        (("copper.clearance", "A", "B"), {"name": ""}, "name of a waiver"),
        (("copper.clearance", "A"), {}, "two items"),
        (("copper.short", "A", "B", "C"), {}, "two items"),
        (("kicad.drc.silk-overlap",), {}, "one or two items"),
        (("copper.clearance", "A", "B, C"), {}, "without ', '"),
        (("copper.clearance", "A", 3), {}, "a Part or the name"),
        (("copper.clearance", "A", ""), {}, "a Part or the name"),
    ],
)
def test_refused_waivers(args: tuple[object, ...], kwargs: dict[str, object], message: str) -> None:
    """Scenario "Refused waivers": each call raises ``DslError`` naming the rule it broke, before anything
    is built."""
    design, _ = design_with("R1")
    options: dict[str, object] = {"reason": "accepted", **kwargs}
    with pytest.raises(DslError, match=message):
        design.waive(*args, **options)  # type: ignore[arg-type]
    assert design.waivers == {}


def test_refused_twice() -> None:
    design, _ = design_with("R1")
    design.waive("copper.clearance", "A", "B", reason="first")
    with pytest.raises(DslError, match="already recorded"):
        design.waive("copper.clearance", "A", "B", reason="second")
    design.waive("copper.clearance", "A", "C", reason="named", name="one")
    with pytest.raises(DslError, match="already recorded"):
        design.waive("copper.short", "X", "Y", reason="named again", name="one")
    assert sorted(design.waivers) == ["copper.clearance:A,B", "one"]


def test_code_sets_are_those_of_the_checks() -> None:
    """``dsl`` imports no check, so it spells the two sets itself; they are the checks' own."""
    assert WAIVED_COPPER == COPPER_CODES and DRC_VERDICTS == RESERVED_SUFFIXES
