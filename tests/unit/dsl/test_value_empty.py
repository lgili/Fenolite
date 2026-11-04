# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Explicitly empty part values (capability design-dsl, "Explicitly empty part values"; change c0364)."""

from __future__ import annotations

import re
import runpy
from pathlib import Path

from _buildhelp import blink, blink_variant, build

from fenolite.dsl import Part, to_model
from fenolite.dsl.convert import empty_value_ids
from fenolite.model.canonical import dumps


def _built_value(tmp_path: Path, new: str) -> str:
    """The Value of R1 in the board that the blink builds with R1's ``value="330"`` replaced by ``new``."""
    script = blink_variant(tmp_path, 'value="330"', new)
    design = runpy.run_path(str(script))["design"]
    board = build(design, project_dir=script.parent).files["blink.kicad_pcb"].decode("utf-8")
    start = board.index('(property "Reference" "R1"')
    found = re.search(r'\(property "Value" "([^"]*)"', board[start:])
    assert found is not None
    return found.group(1)


def test_empty_value_stays_empty(tmp_path: Path) -> None:
    """Scenario "An empty value under a symbol with a Value"."""
    assert _built_value(tmp_path / "empty", 'value=""') == ""


def test_no_value_takes_the_symbol_value(tmp_path: Path) -> None:
    """Scenario "No value given"."""
    assert _built_value(tmp_path / "none", "") == "Mini_R"


def test_empty_values_name_only_the_parts_given_an_empty_value(tmp_path: Path) -> None:
    script = blink_variant(tmp_path, 'value="330"', 'value=""')
    design = runpy.run_path(str(script))["design"]
    r1 = next(c for c in to_model(design).circuit.components if c.ref == "R1")
    assert empty_value_ids(design) == {r1.id}
    assert empty_value_ids(blink()) == frozenset()


def test_existing_designs_keep_their_canonical_json(tmp_path: Path) -> None:
    """Scenario "Existing designs keep their digests": the model holds no flag."""
    script = blink_variant(tmp_path, 'value="330"', 'value=""')
    design = runpy.run_path(str(script))["design"]
    assert "value_empty" not in dumps(to_model(design))
    assert not Part("R9", "Mini:Mini_R", footprint="Mini:Mini_R_0603").value_empty
