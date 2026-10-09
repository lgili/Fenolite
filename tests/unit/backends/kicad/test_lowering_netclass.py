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
    assert set(FLOOR_KEYS) == {"clearance", "track_width", "via_diameter", "via_drill"}
    pair_keys = {"diff_pair_width", "diff_pair_gap", "diff_pair_via_gap"}  # change c0104: no floor entry
    assert set(NETCLASS_KEYS) == set(FLOOR_KEYS) | pair_keys
    assert all(NETCLASS_KEYS[key] == key for key in NETCLASS_KEYS)
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


def test_pair_values_lowered() -> None:
    """Scenario "Pair values lowered" (change c0104): the three pair values are written as the four
    lengths are, a ``None`` keeps the base value, and none has a floor."""
    base: JsonObject = {**BASE, "diff_pair_via_gap": JsonNumber("0.25"), "diff_pair_gap": JsonNumber("0.25")}
    made = NetClass(
        id=derived_id("cls", "test", "usb"),
        name="USB",
        clearance=200_000,
        diff_pair_width=300_000,
        diff_pair_gap=150_000,
    )
    issues: list[Issue] = []
    entry = lower_netclass(made, base=base, floors={"track_width": 200_000}, issues=issues)
    assert entry["diff_pair_width"] == JsonNumber("0.3") and entry["diff_pair_gap"] == JsonNumber("0.15")
    assert entry["diff_pair_via_gap"] == JsonNumber("0.25") and issues == []
    assert entry["name"] == "USB" and entry["track_width"] == BASE["track_width"]
