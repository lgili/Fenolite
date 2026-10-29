# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Drawn sheets lowered for KiCad (capability drawn-schematic, "Drawn sheets lowered for KiCad"; change
c0276)."""

from __future__ import annotations

import _drawn
import pytest
from _buildhelp import resolver

from fenolite.backends.kicad import drawn as kdrawn
from fenolite.backends.kicad.schgen import GeneratedSchematic
from fenolite.backends.kicad import sch
from fenolite.dsl import to_model
from fenolite.lens.build import _resolve  # pyright: ignore[reportPrivateUsage]
from fenolite.model.drawn_connect import component_path


def _lower(name: str, target: int) -> GeneratedSchematic:
    model = to_model(_drawn.design(name))
    issues: list[object] = []
    parts, _ = _resolve(model, resolver(target, _drawn.folder(name)), issues)  # type: ignore[arg-type]
    symbols = {"Mini:Mini_GND": kdrawn.PowerSymbol(_drawn.library()["Mini:Mini_GND"])}
    return kdrawn.lower_drawn(_drawn.drawn(name), model, parts, name=_drawn.design(name).name,
                              target=target, power_symbols=symbols)  # fmt: skip


@pytest.mark.parametrize("target", [9, 10])
def test_same_contract_as_the_generator(target: int) -> None:
    """Scenario "Same contract as the generator"."""
    lowered = _lower("example", target)
    model = to_model(_drawn.design("example"))
    assert not [i for i in lowered.issues if i.severity == "error"]
    assert set(lowered.paths) == {c.id for c in model.circuit.components}
    u1 = next(c for c in model.circuit.components if c.ref == "U1")
    assert (u1.id, "11") in lowered.pad_nets and lowered.pad_nets[(u1.id, "11")].startswith(
        "unconnected-(U1-"
    )
    assert (u1.id, "17") not in lowered.pad_nets
    assert list(lowered.libraries) == ["Mini"]
    assert {d.name for d in lowered.libraries["Mini"]} == {"Mini_QFP32_IC", "Mini_R", "Mini_GND"}
    assert list(lowered.children) == ["sheets/child.kicad_sch"]
    assert lowered.sheet.pages and not lowered.children["sheets/child.kicad_sch"].pages
    # the build steps after the generator run unchanged: the full build plans every file
    output = _drawn.build("example", target)
    assert "drawn.kicad_pcb" in output.files and output.summary["schematic"]["source"] == "drawn"  # type: ignore[index]


def test_deterministic_ids() -> None:
    """Scenario "Deterministic ids"."""
    first, second = _lower("example", 10), _lower("example", 10)
    assert first == second
    texts = [sch.write_schematic(s.sheet, target=10).text for s in (first, second)]
    assert texts[0] == texts[1]


def test_symbol_ids_follow_component_paths() -> None:
    """A drawn symbol keeps the id the generator gives the same unit, so the board's paths survive a freeze."""
    lowered = _lower("flat", 10)
    model = to_model(_drawn.design("flat"))
    paths = {component_path(c): c.id for c in model.circuit.components}
    assert lowered.paths[paths["U1"]].startswith("/") and lowered.sheet.symbols[0].ref == "U1"
