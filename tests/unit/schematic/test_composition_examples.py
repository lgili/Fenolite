# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Executable before/after example proves identical circuitry and declared block order."""

import runpy
from pathlib import Path

from fenolite.backends.altium.project import plan_sheet, write_project
from fenolite.backends.altium.verification import verify
from fenolite.dsl import schematic_composition, to_model
from fenolite.lens.altium import generic_pins

EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "schematic_blocks"


def test_examples_preserve_circuit_and_compose_in_declared_order():
    before = runpy.run_path(str(EXAMPLE / "grid.py"))["design"]
    after = runpy.run_path(str(EXAMPLE / "design.py"))["design"]
    assert to_model(before).circuit == to_model(after).circuit
    intent = schematic_composition(after)
    model = generic_pins(to_model(after))
    planned = plan_sheet(model, name="signal_chain", composition=intent)
    assert planned.composition is not None
    assert [b.key for b in planned.composition.blocks] == ["input", "core", "output"]
    old = write_project(model, name="signal_chain")
    new = write_project(model, name="signal_chain", composition=intent)
    verify(
        {"signal_chain.SchDoc": old["signal_chain.SchDoc"]},
        {"signal_chain.SchDoc": new["signal_chain.SchDoc"]},
    )
