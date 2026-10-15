# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored intent declarations preserve the circuit and reject conflicting requests."""

import pytest

from fenolite.dsl import Design, Part, schematic_composition, to_model
from fenolite.dsl.errors import DslError
from fenolite.model import canonical


def parts():
    design = Design("CompositionIntent")
    a, b = Part("R1", "Example:R"), Part("R2", "Example:R")
    design.add(a, b)
    return design, a, b


def test_declarations_are_immutable_and_do_not_mutate_the_model():
    design, a, b = parts()
    before = canonical.dump_texts(to_model(design))
    design.schematic_layout()
    design.schematic_block("output", members=[b], after="input")
    design.schematic_block("input", members=[a], anchor=a)
    intent = schematic_composition(design)
    assert intent is not None and [b.key for b in intent.blocks] == ["input", "output"]
    assert canonical.dump_texts(to_model(design)) == before


@pytest.mark.parametrize("problem", ["duplicate", "anchor", "unknown", "cycle", "foreign", "disabled"])
def test_invalid_declarations(problem):
    design, a, b = parts()
    if problem != "disabled":
        design.schematic_layout()
    design.schematic_block("a", members=[a], after="b" if problem == "cycle" else None)
    if problem == "anchor":
        design.schematic_block("b", members=[b], anchor=a)
    elif problem == "unknown":
        design.schematic_block("b", members=[b], after="missing")
    elif problem == "cycle":
        design.schematic_block("b", members=[b], after="a")
    elif problem == "duplicate":
        design.schematic_block("b", members=[a])
    elif problem == "foreign":
        design.schematic_block("b", members=[Part("R3", "Example:R")])
    with pytest.raises(DslError):
        schematic_composition(design)


def test_unsupported_target_and_cli_enable():
    design, a, _ = parts()
    assert schematic_composition(design) is None
    design.schematic_block("input", members=[a])
    assert schematic_composition(design, target="altium", enabled=True) is not None
    with pytest.raises(DslError):
        schematic_composition(design, target="kicad", enabled=True)


@pytest.mark.parametrize("flow", ["sideways", "", "LEFT"])
def test_invalid_flow(flow):
    with pytest.raises(DslError):
        Design("InvalidFlow").schematic_layout(flow=flow)
