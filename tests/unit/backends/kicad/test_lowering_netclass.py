# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net classes lowered to the project file (capability rules-model, "Net classes lower to the project
file"; change c0010)."""

from __future__ import annotations

from fenolite.backends.kicad._json import JsonNumber, JsonObject
from fenolite.backends.kicad.lowering import FLOOR_KEYS, NETCLASS_KEYS, lower_netclass
from fenolite.backends.kicad.proerrors import ISSUE_CODES
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.circuit import NetClass

BASE: JsonObject = {
    "bus_width": JsonNumber("12"),
    "clearance": JsonNumber("0.2"),
    "name": "Default",
    "priority": JsonNumber("2147483647"),
    "track_width": JsonNumber("0.2"),
    "via_diameter": JsonNumber("0.6"),
    "via_drill": JsonNumber("0.3"),
    "wire_width": JsonNumber("6"),
}


def cls(**fields: object) -> NetClass:
    return NetClass(id=derived_id("cls", "test", "hv"), name="HV", **fields)  # type: ignore[arg-type]


def test_keys() -> None:
    assert set(NETCLASS_KEYS) == set(FLOOR_KEYS) == {"clearance", "track_width", "via_diameter", "via_drill"}
    assert FLOOR_KEYS["via_drill"] == "min_through_hole_diameter"


def test_hv_class_lowered() -> None:
    entry = lower_netclass(cls(clearance=2_000_000, track_width=500_000), base=BASE, floors={})
    assert entry["name"] == "HV" and entry["clearance"] == JsonNumber("2")
    assert entry["track_width"] == JsonNumber("0.5") and entry["via_diameter"] == JsonNumber("0.6")
    assert {k: v for k, v in entry.items() if k not in ("name", "clearance", "track_width")} == {
        k: v for k, v in BASE.items() if k not in ("name", "clearance", "track_width")
    }
    assert list(entry) == list(BASE) and BASE["name"] == "Default"


def test_value_below_the_floor() -> None:
    issues: list[Issue] = []
    entry = lower_netclass(cls(clearance=500_000), base=BASE, floors={"clearance": 1_500_000}, issues=issues)
    assert entry["clearance"] == JsonNumber("0.5")
    assert [i.code for i in issues] == ["kicad.project.below-floor"] and issues[0].severity == "warning"
    for part in ("HV", "clearance", "0.5", "min_clearance"):
        assert part in issues[0].message


def test_description_has_no_project_key() -> None:
    issues: list[Issue] = []
    entry = lower_netclass(cls(description="mains side"), base=BASE, floors={}, issues=issues)
    assert "description" not in entry
    assert [(i.code, i.severity) for i in issues] == [("kicad.project.unlowered-field", "info")]
    assert all(ISSUE_CODES[i.code] == i.severity for i in issues)
