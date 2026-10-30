# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The base record ``fenolite-base.json`` (capability edit-merge, "Base record form", "Base record
reading"; change c0250)."""

from __future__ import annotations

import json
from types import MappingProxyType

import pytest

from fenolite.lens.edits import BASE_SCHEMA, BaseEntry, BaseRecord, base_record, read_base, write_base

RECORD = BaseRecord(
    "kicad",
    MappingProxyType(
        {
            "R1": MappingProxyType(
                {
                    "footprint": BaseEntry("Mini:Mini_R_0603", "Mini:Mini_R_0603"),
                    "position": BaseEntry((120_000_000, 110_000_000), (120_000_000, 110_000_000)),
                    "rotation": BaseEntry((0, "top"), (0, "top")),
                    "value": BaseEntry("330", "4k7"),
                }
            ),
            "U2": MappingProxyType({"position": BaseEntry(None, (1, 2))}),
        }
    ),
)


def test_canonical_text() -> None:
    text = write_base(RECORD)
    data = json.loads(text)
    assert data["schema"] == BASE_SCHEMA and data["target"] == "kicad"
    assert data["parts"]["R1"]["value"] == {"code": "330", "out": "4k7"}
    assert data["parts"]["R1"]["rotation"] == {"code": [0, "top"], "out": [0, "top"]}
    assert data["parts"]["U2"]["position"] == {"code": None, "out": [1, 2]}
    assert text == json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    assert not isinstance(json.loads(text, parse_float=lambda _: pytest.fail("a float")), float)


def test_round_trip() -> None:
    back = read_base(write_base(RECORD), target="kicad")
    assert back.present and back.issues == ()
    assert {p: dict(e) for p, e in back.parts.items()} == {p: dict(e) for p, e in RECORD.parts.items()}
    assert write_base(back) == write_base(RECORD)


def test_record_of_another_target() -> None:
    found = read_base(
        write_base(RECORD).replace('"kicad"', '"altium"'), target="kicad", file="B/fenolite-base.json"
    )
    assert not found.present and found.parts == {}
    (problem,) = found.issues
    assert problem.code == "edit.base-invalid" and problem.severity == "warning"
    assert "B/fenolite-base.json" in problem.message


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        json.dumps({"schema": "fenolite.base.v9", "target": "kicad", "parts": {}}),
        json.dumps({"schema": BASE_SCHEMA, "target": "kicad", "parts": {}, "date": "today"}),
        json.dumps({"schema": BASE_SCHEMA, "target": "kicad", "parts": {"R 1": {}}}),
        json.dumps(
            {"schema": BASE_SCHEMA, "target": "kicad", "parts": {"R1": {"colour": {"code": 1, "out": 1}}}}
        ),
        json.dumps({"schema": BASE_SCHEMA, "target": "kicad", "parts": {"R1": {"value": {"out": "1"}}}}),
        json.dumps(
            {
                "schema": BASE_SCHEMA,
                "target": "kicad",
                "parts": {"R1": {"position": {"code": None, "out": [1.5, 2]}}},
            }
        ),
        json.dumps(
            {
                "schema": BASE_SCHEMA,
                "target": "kicad",
                "parts": {"R1": {"rotation": {"code": None, "out": [0, "left"]}}},
            }
        ),
        json.dumps(
            {"schema": BASE_SCHEMA, "target": "kicad", "parts": {"R1": {"value": {"code": 3, "out": "1"}}}}
        ),
    ],
)
def test_malformed_records_are_no_record(text: str) -> None:
    found = read_base(text, target="kicad")
    assert not found.present and [i.code for i in found.issues] == ["edit.base-invalid"]


def test_base_record_of_a_build() -> None:
    record = base_record(
        {"R1": {"position": None, "value": "330"}},
        {"R1": {"position": (1, 2), "value": "4k7"}, "D1": {"value": "LED"}},
        target="kicad",
    )
    assert list(record.parts) == ["D1", "R1"]
    assert record.parts["R1"]["position"] == BaseEntry(None, (1, 2))
    assert record.parts["R1"]["value"] == BaseEntry("330", "4k7")
    assert record.parts["D1"]["value"] == BaseEntry(None, "LED")
