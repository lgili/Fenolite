# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Level 6 compares rules (capability design-equivalence, "Level 6 compares rules"; change c0278)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from _cases import two_layer

from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.equivalence import LevelResult, Tolerances, compare_designs
from fenolite.checks.equivalence.model import EXACT
from fenolite.checks.equivalence.rules import fields
from fenolite.core.ids import derived_id
from fenolite.model.circuit import NetClass
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector

ROOT = Path(__file__).resolve().parents[4]
FOUR = ROOT / "tests" / "data" / "kicad" / "board" / "stackup_four.kicad_pcb"


def level6(a: Design, b: Design, tolerances: Tolerances = EXACT) -> LevelResult:
    report = compare_designs(a, b, level=6, tolerances=tolerances)
    assert [level.level for level in report.levels] == [1, 2, 3, 4, 5, 6]
    return report.levels[-1]


def ruled(seed: str = "a", clearance: int = 200_000) -> Design:
    """The two-layer design with a class ``Default`` on its first net, a class ``PWR`` and a custom rule,
    every id derived from ``seed``."""
    design = two_layer()
    classes = (
        NetClass(
            id=derived_id("cls", seed, "default"), name="Default", clearance=clearance, track_width=250_000
        ),
        NetClass(id=derived_id("cls", seed, "pwr"), name="PWR", clearance=300_000, native_ids={"x": seed}),
    )
    nets = list(design.circuit.nets)
    nets[0] = dataclasses.replace(nets[0], netclass_id=classes[1].id)
    rule = Rule(
        id=derived_id("rul", seed, "one"),
        name="gnd_clearance",
        kind="clearance",
        selector_a=Selector("net", "GND"),
        min=200_000,
        native_ids={"y": seed},
    )
    circuit = dataclasses.replace(design.circuit, netclasses=classes, nets=tuple(nets))
    return dataclasses.replace(
        design, circuit=circuit, rules=RuleSet(id=derived_id("rst", seed, "r"), rules=(rule,))
    )


def test_a_design_against_itself() -> None:
    result = level6(ruled(), ruled())
    assert (result.name, result.differences) == ("rules", ())
    assert result.summary["netclasses"] == 2 and result.summary["rules"] == 2


def test_a_clearance_changed() -> None:
    result = level6(ruled(), ruled(clearance=200_001))
    assert [(d.kind, d.where, d.field, d.a, d.b) for d in result.differences] == [
        ("netclass-field", "Default", "clearance", "200000", "200001")
    ]
    assert level6(ruled(), ruled(clearance=200_001), Tolerances(length_nm=1)).differences == ()


def test_ids_do_not_matter() -> None:
    assert level6(ruled("a"), ruled("b")).differences == ()


def test_members_and_missing() -> None:
    a, b = ruled(), ruled()
    nets = tuple(dataclasses.replace(net, netclass_id=None) for net in b.circuit.nets)
    b = dataclasses.replace(
        b, circuit=dataclasses.replace(b.circuit, nets=nets, netclasses=b.circuit.netclasses[:1])
    )
    b = dataclasses.replace(b, rules=RuleSet(id="rst-none"))
    found = [(d.kind, d.where) for d in level6(a, b).differences]
    assert found == [("netclass-missing", "PWR"), ("rule-missing", "gnd_clearance")]


def test_dielectric_thickness() -> None:
    four = read_board(FOUR.read_text(encoding="utf-8"), file=FOUR.name)
    assert four.board is not None and four.board.stackup is not None
    base = two_layer()
    assert base.board is not None
    a = dataclasses.replace(base, board=dataclasses.replace(base.board, stackup=four.board.stackup))
    layers = list(four.board.stackup.layers)
    index = next(k for k, layer in enumerate(layers) if layer.name == "dielectric 2")
    layers[index] = dataclasses.replace(layers[index], thickness=layers[index].thickness + 100_000)
    stack = dataclasses.replace(four.board.stackup, layers=tuple(layers))
    b = dataclasses.replace(base, board=dataclasses.replace(base.board, stackup=stack))
    assert [(d.kind, d.where, d.field) for d in level6(a, b).differences] == [
        ("stackup-field", "dielectric 2", "thickness")
    ]
    assert level6(a, a).differences == ()


def test_layer_table() -> None:
    a = two_layer()
    assert a.board is not None
    layers = tuple(layer for layer in a.board.layers if layer.kind != "courtyard")
    b = dataclasses.replace(a, board=dataclasses.replace(a.board, layers=layers))
    found = level6(a, b).differences
    assert found and {d.kind for d in found} == {"layer-missing"}
    assert all(d.where.startswith("courtyard:") and d.a and not d.b for d in found)


def test_fields_leave_identity_out() -> None:
    cls = NetClass(id="ncl-1", name="X", clearance=5, native_ids={"k": "v"})
    assert fields(cls, skip=("name",)) == {
        "clearance": 5,
        "track_width": None,
        "via_diameter": None,
        "via_drill": None,
        "description": "",
        "diff_pair_width": None,
        "diff_pair_gap": None,
        "diff_pair_via_gap": None,
    }
