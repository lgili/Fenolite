# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Refs reach the model (capability design-dsl, "Refs reach the model"; change c0249)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fenolite.cli._script import run_design_script
from fenolite.dsl import Design, DslError, Module, Net, connect, to_model
from fenolite.model import canonical

ROOT = Path(__file__).resolve().parents[3]
BLINK = ROOT / "examples" / "blink_2layer" / "design.py"


def buck() -> Design:
    design = Design("t")
    module = Module("buck")
    design.add(module)
    u = module.part(lib_id="Example:BUCK_6V_2A", footprint="Example:SOT23-6", prefix="U")
    r = design.part("R1", "Fenolite:Resistor", "Fenolite:Chip_0603")
    connect(Net("VIN"), u["1"], r["1"])
    return design


def test_ids_do_not_follow_refs() -> None:
    first = to_model(buck(), refs={"buck/U": "U1"})
    second = to_model(buck(), refs={"buck/U": "U4"})
    refs = {c.properties["fenolite.path"]: c.ref for c in second.circuit.components}
    assert refs == {"R1": "R1", "buck/U": "U4"}
    unref = dataclasses.replace(
        second,
        circuit=dataclasses.replace(
            second.circuit,
            components=tuple(
                dataclasses.replace(c, ref="U1") if c.ref == "U4" else c for c in second.circuit.components
            ),
        ),
    )
    assert canonical.dumps(unref) == canonical.dumps(first)
    assert [c.id for c in first.circuit.components] == [c.id for c in second.circuit.components]


def test_default_assignment_against_an_empty_lock() -> None:
    design = buck()
    part = design.parts["buck/U"]
    assert part.ref is None
    model = to_model(design)
    assert {c.ref for c in model.circuit.components} == {"R1", "U1"} and part.ref == "U1"
    assert to_model(design, refs={"buck/U": "U7"}).circuit.components[1].ref == "U7" and part.ref == "U7"


def test_explicit_refs_win_and_missing_refs_are_refused() -> None:
    design = buck()
    model = to_model(design, refs={"buck/U": "U2", "R1": "R9"})
    assert sorted(c.ref for c in model.circuit.components) == ["R1", "U2"]
    with pytest.raises(DslError, match="buck/U"):
        to_model(buck(), refs={})
    with pytest.raises(DslError, match="ref of buck/U"):
        to_model(buck(), refs={"buck/U": "U 1"})


def test_explicit_designs_keep_their_model() -> None:
    design = run_design_script(BLINK).design
    assert all(p.explicit_ref is not None for p in design.parts.values())
    plain = canonical.dumps(to_model(design))
    assert canonical.dumps(to_model(design, refs={})) == plain
    assert all(part.ref == part.explicit_ref for part in design.parts.values())
