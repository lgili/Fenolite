# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The stack-up in the board model (capability design-model, "Stack-up in the board model"; change
c0101): the three additive fields, the helpers and the three ``model.stackup-*`` findings."""

from __future__ import annotations

import dataclasses
import json
import random
from pathlib import Path
from typing import get_args

import pytest

from fenolite.core.ids import new_id
from fenolite.model.board import Board, DielectricKind, Layer, StackKind, StackLayer, Stackup
from fenolite.model.canonical import dumps, loads
from fenolite.model.design import SCHEMA_VERSION, Design

ROOT = Path(__file__).resolve().parents[3]
OLD_BOARD = ROOT / "tests" / "data" / "model" / "v0.2.1" / "blink_2layer.board.json"
SENTENCE = "0.2.x cannot read a model document that carries"
RNG = random.Random(101)


def entry(name: str, kind: StackKind, thickness: int, **more: object) -> StackLayer:
    return StackLayer(id=new_id("sly", RNG), name=name, kind=kind, thickness=thickness, **more)  # type: ignore[arg-type]


def four_layers() -> Stackup:
    return Stackup(
        id=new_id("stk", RNG),
        layers=(
            entry("F.Mask", "soldermask", 10_000),
            entry("F.Cu", "copper", 35_000),
            entry("dielectric 1", "dielectric", 200_000, dielectric_kind="prepreg"),
            entry("In1.Cu", "copper", 17_500),
            entry("dielectric 2", "dielectric", 1_200_000, dielectric_kind="core"),
            entry("In2.Cu", "copper", 17_500),
            entry("dielectric 3", "dielectric", 200_000, dielectric_kind="prepreg"),
            entry("B.Cu", "copper", 35_000),
            entry("B.Mask", "soldermask", 10_000),
        ),
    )


def design_of(stackup: Stackup, copper: tuple[str, ...] = ()) -> Design:
    design = Design.new("stack", seed=7)
    assert design.board is not None
    layers = tuple(
        Layer(id=new_id("lay", RNG), name=name, kind="copper", ordinal=k) for k, name in enumerate(copper)
    )
    return dataclasses.replace(
        design, board=dataclasses.replace(design.board, layers=layers, stackup=stackup)
    )


def codes(design: Design) -> list[str]:
    return sorted(i.code for i in design.validate() if i.code.startswith("model.stackup-"))


def test_old_documents_still_load() -> None:
    """A ``board.json`` written before the change holds none of the three keys and loads with the
    defaults."""
    old = Stackup(
        id=new_id("stk", RNG),
        layers=(
            entry("F.Cu", "copper", 35_000),
            entry("core", "dielectric", 1_500_000, material="FR4", epsilon_r="4.5"),
            entry("B.Cu", "copper", 35_000),
        ),
        finish="ENIG",
    )
    text = dumps(Board(id=new_id("brd", RNG), stackup=old))
    assert not {"dielectric_kind", "color", "impedance_controlled"} & set(text.replace('"', " ").split())
    board = loads(text, Board)
    assert board.stackup is not None and not board.stackup.impedance_controlled
    assert all(e.dielectric_kind is None and e.color == "" for e in board.stackup.layers)
    assert dumps(board) == text


def test_v021_document_loads_and_serialises_to_its_bytes() -> None:
    """The ``board.json`` that the code of release 0.2.1 wrote for ``examples/blink_2layer`` (the base of
    this change; c0126's 0.2.0 fixture is not on the branch) loads and dumps to its own bytes, and the
    documents say that the other direction does not hold."""
    text = OLD_BOARD.read_bytes().decode("utf-8")
    for key in ("dielectric_kind", "color", "impedance_controlled"):
        assert f'"{key}"' not in text
    board = loads(text, Board)
    assert board.stackup is None
    assert dumps(board).encode("utf-8") == OLD_BOARD.read_bytes()
    assert SCHEMA_VERSION == "0"
    for name in ("docs/design-model.md", "CHANGELOG.md"):
        assert SENTENCE in " ".join((ROOT / name).read_text(encoding="utf-8").split()), name


def test_new_keys_are_written_only_when_set() -> None:
    stackup = Stackup(
        id=new_id("stk", RNG),
        layers=(entry("d", "dielectric", 1, dielectric_kind="core", color="Green"),),
        impedance_controlled=True,
    )
    data = json.loads(dumps(stackup))
    assert data["impedance_controlled"] is True
    assert data["layers"][0]["dielectric_kind"] == "core" and data["layers"][0]["color"] == "Green"
    assert loads(dumps(stackup), Stackup) == stackup


def test_thickness_depth_and_between() -> None:
    stackup = four_layers()
    assert stackup.thickness() == 1_725_000
    assert stackup.depth("In1.Cu") == (245_000, 262_500)
    assert stackup.depth("F.Mask") == (0, 10_000)
    between = stackup.between("F.Cu", "In1.Cu")
    assert [e.name for e in between] == ["dielectric 1"] and between[0].dielectric_kind == "prepreg"
    assert [e.name for e in stackup.between("F.Cu", "In2.Cu")] == ["dielectric 1", "In1.Cu", "dielectric 2"]
    with pytest.raises(ValueError, match="does not lie above"):
        stackup.between("In1.Cu", "F.Cu")
    with pytest.raises(ValueError):
        stackup.between("F.Cu", "F.Cu")
    with pytest.raises(KeyError):
        stackup.depth("In9.Cu")
    with pytest.raises(KeyError):
        stackup.between("F.Cu", "nope")


def test_valid_stackup_gives_no_finding() -> None:
    assert codes(design_of(four_layers(), ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"))) == []
    assert codes(design_of(four_layers())) == []  # a board without layers: the names are not compared


def test_copper_entries_out_of_table_order() -> None:
    stackup = four_layers()
    layers = list(stackup.layers)
    layers[3], layers[5] = layers[5], layers[3]
    design = design_of(
        dataclasses.replace(stackup, layers=tuple(layers)), ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
    )
    found = [i for i in design.validate() if i.code.startswith("model.stackup-")]
    assert [(i.code, i.severity, i.where) for i in found] == [("model.stackup-copper", "error", stackup.id)]


def test_mixed_gap_and_bad_decimal() -> None:
    stackup = Stackup(
        id=new_id("stk", RNG),
        layers=(
            entry("F.Cu", "copper", 35_000),
            entry("dielectric 1", "dielectric", 1_000_000, dielectric_kind="core", epsilon_r="4,5"),
            entry("dielectric 1", "dielectric", 100_000, dielectric_kind="prepreg"),
            entry("B.Cu", "copper", 35_000),
        ),
    )
    found = [i for i in design_of(stackup, ("F.Cu", "B.Cu")).validate() if i.code.startswith("model.stackup")]
    assert sorted((i.code, i.severity) for i in found) == [
        ("model.stackup-order", "error"),
        ("model.stackup-value", "error"),
    ]


def _with(stackup: Stackup, index: int, **changes: object) -> Stackup:
    layers = list(stackup.layers)
    layers[index] = dataclasses.replace(layers[index], **changes)  # type: ignore[arg-type]
    return dataclasses.replace(stackup, layers=tuple(layers))


def _without(stackup: Stackup, *indexes: int) -> Stackup:
    return dataclasses.replace(
        stackup, layers=tuple(e for k, e in enumerate(stackup.layers) if k not in indexes)
    )


ORDER_CASES = {
    "mask between copper": lambda s: _with(s, 2, kind="soldermask", dielectric_kind=None),
    "two masks on one side": lambda s: dataclasses.replace(s, layers=(s.layers[0], *s.layers)),
    "dielectric above the first copper": lambda s: dataclasses.replace(s, layers=(s.layers[2], *s.layers)),
    "dielectric below the last copper": lambda s: dataclasses.replace(s, layers=(*s.layers, s.layers[2])),
    "neighbouring copper": lambda s: _without(s, 2),
    "kind on a copper entry": lambda s: _with(s, 1, dielectric_kind="core"),
}
VALUE_CASES = {
    "negative": lambda s: _with(s, 0, thickness=-1),
    "copper of 0": lambda s: _with(s, 1, thickness=0),
    "dielectric of 0": lambda s: _with(s, 2, thickness=0),
    "exponent": lambda s: _with(s, 2, epsilon_r="4e0"),
    "sign": lambda s: _with(s, 2, loss_tangent="+0.02"),
    "epsilon of zero": lambda s: _with(s, 2, epsilon_r="0.0"),
    "loss with a comma": lambda s: _with(s, 2, loss_tangent="0,02"),
}


@pytest.mark.parametrize("case", sorted(ORDER_CASES))
def test_order_findings(case: str) -> None:
    assert codes(design_of(ORDER_CASES[case](four_layers()))) == ["model.stackup-order"]


@pytest.mark.parametrize("case", sorted(VALUE_CASES))
def test_value_findings(case: str) -> None:
    assert codes(design_of(VALUE_CASES[case](four_layers()))) == ["model.stackup-value"]


def test_values_that_pass() -> None:
    """A mask of thickness 0 passes, and so does a loss tangent of 0, which KiCad writes for solder masks
    (design, "Found on 2026-10-07")."""
    ok = _with(_with(four_layers(), 0, thickness=0, loss_tangent="0"), 2, epsilon_r="4", loss_tangent="0.02")
    assert codes(design_of(ok)) == []


def test_no_copper_entry() -> None:
    stackup = Stackup(id=new_id("stk", RNG), layers=(entry("F.Mask", "soldermask", 10_000),))
    assert codes(design_of(stackup)) == ["model.stackup-copper"]


def test_schema_lists_the_new_keys() -> None:
    schema = json.loads((ROOT / "schemas" / "fenolite.model.v0" / "board.json").read_text(encoding="utf-8"))
    text = json.dumps(schema)
    assert sorted(get_args(DielectricKind)) == ["core", "prepreg"]
    assert '"dielectric_kind"' in text and '"color"' in text and '"impedance_controlled"' in text
    assert '["core", "prepreg"]' in text
