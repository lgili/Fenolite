# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Value ranges in the circuit model (capability design-model, "Value range object in the model" to "Value
ranges on components"; change c0246). The values are round numbers chosen for these tests."""

from __future__ import annotations

import dataclasses
import json
from fractions import Fraction
from pathlib import Path

import _schema
import pytest

from fenolite.core.errors import FormatError
from fenolite.model import Component, Design
from fenolite.model.canonical import dump_dir, dumps, load_dir, loads
from fenolite.model.circuit import Circuit, Decimal10, ValueRange

TEN_K_1PCT = ValueRange("ohm", Decimal10(99, 2), Decimal10(1, 4), Decimal10(101, 2))

OLD_CIRCUIT = """{
  "components": [
    {
      "id": "cmp_cd613e30-d8f1-4adf-91b7-584a2265b1f5",
      "ref": "R1",
      "value": "10kΩ",
      "lib_symbol_ref": "Mini:Mini_R"
    }
  ]
}
"""
"""A ``circuit.json`` in the form written before change c0246."""


@pytest.mark.parametrize(
    "build",
    [
        lambda: ValueRange("ohm"),
        lambda: ValueRange("ohm", low=Decimal10(2, 0), high=Decimal10(1, 0)),
        lambda: ValueRange("ohm", low=Decimal10(1, 0), nominal=Decimal10(5, 0), high=Decimal10(2, 0)),
        lambda: ValueRange("uohm", low=Decimal10(1, 0)),  # pyright: ignore[reportArgumentType]
        lambda: ValueRange("ohm", low=(1, 0)),  # pyright: ignore[reportArgumentType]
    ],
)
def test_refused_ranges(build: object) -> None:
    with pytest.raises(ValueError):
        build()  # pyright: ignore[reportCallIssue]


@pytest.mark.parametrize(
    ("m", "e"), [(10, 0), (0, 3), (10**15, 0), (-(10**15), 0), (1, 31), (1, -31), (True, 0), (1, 1.0)]
)
def test_refused_pairs(m: object, e: object) -> None:
    with pytest.raises(ValueError):
        Decimal10(m, e)  # pyright: ignore[reportArgumentType]


def test_decimal_values() -> None:
    assert Decimal10(99, 2).fraction() == 9900 and Decimal10(-333, -3).fraction() == Fraction(-333, 1000)
    assert Decimal10(0, 0).fraction() == 0 and Decimal10(10**15 - 1, 30).fraction() == (10**15 - 1) * 10**30
    assert ValueRange("volt", low=Decimal10(-5, 0)).high is None


def test_value_range_is_the_last_field_of_a_component() -> None:
    assert [f.name for f in dataclasses.fields(Component)][-1] == "value_range"
    assert Component(id="cmp_x", ref="R1").value_range is None


def test_ranges_survive_the_canonical_round_trip(tmp_path: Path) -> None:
    design = Design.new("ranges", seed=3)
    component = dataclasses.replace(loads(OLD_CIRCUIT, Circuit).components[0], value_range=TEN_K_1PCT)
    design = dataclasses.replace(design, circuit=Circuit(components=(component,)))
    dump_dir(design, tmp_path)
    loaded = load_dir(tmp_path)
    assert loaded.circuit.components[0].value_range == TEN_K_1PCT
    data = json.loads((tmp_path / "circuit.json").read_text(encoding="utf-8"))
    assert data["components"][0]["value_range"] == {
        "unit": "ohm",
        "low": {"m": 99, "e": 2},
        "nominal": {"m": 1, "e": 4},
        "high": {"m": 101, "e": 2},
    }
    assert _schema.validate(data, _schema.load("fenolite.model.v0/circuit.json")) == []


def test_circuits_without_ranges_are_unchanged() -> None:
    loaded = loads(OLD_CIRCUIT, Circuit)
    assert all(component.value_range is None for component in loaded.components)
    assert dumps(loaded) == OLD_CIRCUIT


def test_a_bad_stored_range_is_a_format_error() -> None:
    data = json.loads(OLD_CIRCUIT)
    data["components"][0]["value_range"] = {"unit": "ohm", "low": {"m": 10, "e": 0}}
    with pytest.raises(FormatError):
        loads(json.dumps(data), Circuit)


def test_schema_is_regenerated() -> None:
    schema = _schema.load("fenolite.model.v0/circuit.json")
    component = schema["$defs"]["Component"]
    assert "value_range" in component["properties"] and "value_range" not in component["required"]
    assert set(schema["$defs"]["ValueRange"]["properties"]) == {"unit", "low", "nominal", "high"}
