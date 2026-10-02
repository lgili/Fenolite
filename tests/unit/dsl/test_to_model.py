# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""DSL designs as model designs (capability design-dsl, "DSL to model"; change c0011)."""

from __future__ import annotations

import runpy
from pathlib import Path

from fenolite.core.coords import Point
from fenolite.dsl import DSL_BACKEND, Design, Module, Part, to_model
from fenolite.dsl.convert import key_id
from fenolite.model import canonical
from fenolite.model.design import iter_entities

ROOT = Path(__file__).resolve().parents[3]
BLINK = ROOT / "examples" / "blink_2layer" / "design.py"


def blink() -> Design:
    design = runpy.run_path(str(BLINK))["design"]
    assert isinstance(design, Design)
    return design


def test_blink_in_the_model() -> None:
    model = to_model(blink())
    r1 = model.by_ref["R1"]
    assert (r1.lib_symbol_ref, r1.lib_footprint_ref, r1.pins, r1.path) == (
        "Mini:Mini_R",
        "Mini:Mini_R_0603",
        (),
        "",
    )
    assert r1.properties == {"fenolite.path": "R1"} and r1.value == "330"
    assert model.board is not None and model.board.outline is not None
    mm = 1_000_000
    corners = ((100, 100), (150, 100), (150, 130), (100, 130))
    assert model.board.outline.points == tuple(Point(x * mm, y * mm) for x, y in corners)
    assert model.board.layers == () and model.board.footprints == ()
    assert model.rules is not None and model.rules.rules == () and model.header.name == "blink"
    assert [n.name for n in model.circuit.nets] == ["GND", "LED_A", "LED_DRV", "VIN"]
    assert [i.name for i in model.circuit.interfaces] == ["VIN/GND"]


def test_no_provenance_and_no_absolute_path() -> None:
    model = to_model(blink())
    assert all(e.provenance is None for e in iter_entities(model))
    texts = canonical.dump_texts(model)
    assert set(texts) == {
        "meta.json",
        "circuit.json",
        "board.json",
        "rules.json",
        "manufacturing.json",
        "findings.json",
    }
    for text in texts.values():
        assert str(BLINK.parent) not in text and str(ROOT) not in text


def test_modules_in_the_model() -> None:
    d, power = Design("t"), Module("power")
    power.add(Part("C1", "Mini:Mini_R"))
    d.add(power)
    (module,) = to_model(d).circuit.modules
    assert module.path == "power" and module.parent is None
    assert module.component_ids == (key_id("component", "power/C1"),)


def test_no_board_without_board_call() -> None:
    model = to_model(Design("t"))
    assert model.board is not None and model.board.outline is None
    assert DSL_BACKEND == "dsl"


def test_to_model_does_not_change_the_design() -> None:
    design = blink()
    before = (dict(design.parts), dict(design.nets), dict(design.rules.netclasses))
    to_model(design)
    assert (dict(design.parts), dict(design.nets), dict(design.rules.netclasses)) == before
