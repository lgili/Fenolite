# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Part heights and height limits in the DSL (capability design-dsl, "Part heights and height limits in the
DSL"; change c0140): what ``Part(height=…)`` and ``Design.height_limit`` record, what they refuse, and
that ``to_model`` puts no height into the circuit."""

from __future__ import annotations

import dataclasses
import runpy
from collections.abc import Callable
from pathlib import Path

import pytest

import fenolite.dsl
from fenolite.dsl import Design, DslError, Part, heights, mm, to_model
from fenolite.model import canonical
from fenolite.model.rules import HeightLimit

BLINK = Path(__file__).resolve().parents[3] / "examples" / "blink_2layer" / "design.py"


def _blink() -> Design:
    return runpy.run_path(str(BLINK))["design"]


def test_a_height_recorded() -> None:
    design = _blink()
    design.add(Part("J1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", height=mm(9)))
    design.height_limit("LID", max=mm(5))
    assert dict(heights(design)) == {"J1": 9_000_000}
    model = to_model(design)
    assert model.rules is not None
    assert model.rules.heights == (HeightLimit("LID", 5_000_000),)
    assert model.circuit is not None
    for component in model.circuit.components:
        assert "height" not in {f.name for f in dataclasses.fields(component)}
    assert fenolite.dsl.heights is heights


def test_a_height_is_no_part_of_the_circuit() -> None:
    plain, tall = _blink(), _blink()
    tall.parts["R1"].height = 9_000_000
    assert canonical.dump_texts(to_model(plain)) == canonical.dump_texts(to_model(tall))
    assert dict(heights(tall)) == {"R1": 9_000_000}


def test_limits_in_area_order_with_a_severity() -> None:
    design = _blink()
    design.height_limit("LID", max="5mm", severity="warning")
    design.height_limit("FAN", max=mm(12))
    rules = to_model(design).rules
    assert rules is not None
    assert rules.heights == (HeightLimit("FAN", 12_000_000), HeightLimit("LID", 5_000_000, "warning"))


def _twice(design: Design) -> None:
    design.height_limit("LID", max=mm(5))
    design.height_limit("LID", max=mm(5))


@pytest.mark.parametrize(
    "call",
    [
        lambda d: Part("R9", "Mini:Mini_R", height=mm(-1)),
        lambda d: Part("R9", "Mini:Mini_R", height=0),
        lambda d: Part("R9", "Mini:Mini_R", height="0mm"),
        lambda d: d.height_limit("L I D", max=mm(5)),
        lambda d: d.height_limit("LID", max=mm(0)),
        lambda d: d.height_limit("LID", max=5),
        lambda d: d.height_limit("LID", max=mm(5), severity="ignore"),
        _twice,
    ],
)
def test_refused_calls(call: Callable[[Design], object]) -> None:
    with pytest.raises(DslError):
        call(_blink())


def test_unchanged_designs() -> None:
    design = _blink()
    assert dict(heights(design)) == {}
    assert design.height_limits == {}
    texts = canonical.dump_texts(to_model(design))
    assert "heights" not in texts["rules.json"]
    assert "bodies" not in "".join(texts.values())
