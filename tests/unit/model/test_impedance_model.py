# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Impedance targets in the rules model (capability design-model, "Impedance targets in the rules model";
change c0105)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import _schema
import pytest

from fenolite.model import Design, canonical
from fenolite.model.circuit import NetClass
from fenolite.model.rules import ImpedanceTarget, RuleSet, TraceGeometry

RST = "rst_00000000-0000-4000-8000-000000000001"
CLS_USB = "cls_00000000-0000-4000-8000-0000000000a1"
CLS_SE = "cls_00000000-0000-4000-8000-0000000000a2"
IMP_A = "imp_00000000-0000-4000-8000-0000000000b1"
IMP_B = "imp_00000000-0000-4000-8000-0000000000b2"


def _usb90(**changes: object) -> ImpedanceTarget:
    target = ImpedanceTarget(
        id=IMP_A,
        name="USB90",
        kind="differential",
        netclass_ids=(CLS_USB,),
        ohms="90",
        tolerance_percent="10",
        layers=(TraceGeometry("F.Cu", ("In1.Cu",), 200_000, 150_000),),
    )
    return dataclasses.replace(target, **changes)  # type: ignore[arg-type]


def _design(*targets: ImpedanceTarget) -> Design:
    design = Design.new("imp", seed=3)
    assert design.rules is not None
    classes = (NetClass(id=CLS_USB, name="USB90"), NetClass(id=CLS_SE, name="SE50"))
    return dataclasses.replace(
        design,
        circuit=dataclasses.replace(design.circuit, netclasses=classes),
        rules=dataclasses.replace(design.rules, impedance=targets),
    )


def _codes(design: Design) -> list[str]:
    return [i.message for i in design.validate() if i.code == "model.impedance-invalid"]


def test_target_round_trip(tmp_path: Path) -> None:
    design = _design(_usb90())
    canonical.dump_dir(design, tmp_path)
    loaded = canonical.load_dir(tmp_path)
    assert loaded.rules is not None and loaded.rules.impedance == (_usb90(),)
    data = json.loads((tmp_path / "rules.json").read_text(encoding="utf-8"))
    assert data["impedance"][0]["name"] == "USB90"
    assert data["impedance"][0]["layers"] == [
        {"layer": "F.Cu", "references": ["In1.Cu"], "width": 200000, "gap": 150000}
    ]
    assert _schema.validate(data, _schema.load("fenolite.model.v0/rules.json")) == []
    assert _codes(design) == []


def test_rules_file_of_an_older_build() -> None:
    older = '{\n  "id": "' + RST + '"\n}\n'
    loaded = canonical.loads(older, RuleSet)
    assert loaded.impedance == ()
    assert _schema.validate(json.loads(older), _schema.load("fenolite.model.v0/rules.json")) == []
    assert canonical.dumps(loaded) == older
    assert "impedance" not in canonical.dumps(RuleSet(id=RST))


def test_targets_keep_their_order() -> None:
    second = _usb90(id=IMP_B, name="AAA", netclass_ids=(CLS_SE,))
    rules = RuleSet(id=RST, impedance=(_usb90(), second))
    assert canonical.loads(canonical.dumps(rules), RuleSet).impedance == (_usb90(), second)


def test_one_class_two_targets() -> None:
    found = _codes(_design(_usb90(name="A"), _usb90(id=IMP_B, name="B")))
    assert len(found) == 1
    assert "A" in found[0] and "B" in found[0] and "USB90" in found[0]


@pytest.mark.parametrize(
    ("changes", "words"),
    [
        ({"netclass_ids": ("cls_00000000-0000-4000-8000-0000000000ff",)}, "names no net class"),
        ({"ohms": "9e1"}, "not a positive decimal"),
        ({"ohms": "0"}, "not a positive decimal"),
        ({"tolerance_percent": "100"}, "below 100"),
        ({"layers": (TraceGeometry("F.Cu", ("In1.Cu",), 200_000),)}, "needs a gap"),
        ({"kind": "single"}, "takes no gap"),
        ({"layers": (TraceGeometry("F.Cu", ("In1.Cu",), 0, 150_000),)}, "not above 0"),
        ({"layers": (TraceGeometry("F.Cu", ("F.Cu",), 200_000, 150_000),)}, "its own reference"),
        ({"layers": (TraceGeometry("F.Cu", (), 200_000, 150_000),)}, "one or two"),
        (
            {"layers": (TraceGeometry("F.Cu", ("In1.Cu",), 2, 1), TraceGeometry("F.Cu", ("In1.Cu",), 2, 1))},
            "given 2 times",
        ),
    ],
)
def test_invalid_targets(changes: dict[str, object], words: str) -> None:
    found = _codes(_design(_usb90(**changes)))
    assert found and all("USB90" in text for text in found), found
    assert any(words in text for text in found), found


def test_two_targets_of_one_name() -> None:
    found = _codes(_design(_usb90(), _usb90(id=IMP_B, netclass_ids=(CLS_SE,))))
    assert found == ["2 impedance targets are named 'USB90'"]
