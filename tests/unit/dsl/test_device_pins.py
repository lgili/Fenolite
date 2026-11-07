# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Checked pin access on device parts (change c0248; capability design-dsl, "Checked pin access on device
parts", "Closest pin names", "Attribute access never hides the part" and "Device ends and pads by
function"). The example device is authored for Fenolite and illustrative."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from fenolite.catalog.devices import parse_device
from fenolite.dsl import Design, DslError, Net, Part, PinNameError, connect, to_model
from fenolite.dsl.devices import end_handle, must_connect_pins, shadowed
from fenolite.dsl.part import PinHandle

ROOT = Path(__file__).resolve().parents[3]
BUCK = parse_device((ROOT / "tests" / "data" / "devices" / "example_buck.toml").read_text(encoding="utf-8"))
MESSAGE = (
    "part U1 (device Example:BUCK_6V_2A) has no pin 'VINN'; closest: VIN; pins: BST, EN, FB, GND, SW, VIN"
)


def _buck() -> tuple[Design, Part]:
    design = Design("d")
    design.devices(BUCK)
    return design, design.part("U1", device="Example:BUCK_6V_2A")


def test_pin_by_function() -> None:
    design, u1 = _buck()
    vin = Net("VIN")
    connect(vin, u1.VIN)
    net = next(n for n in to_model(design).circuit.nets if n.name == "VIN")
    assert [member.pin for member in net.members] == ["VIN"]
    assert u1.VIN == u1["VIN"] == PinHandle(u1, "VIN")
    assert u1["5"] == u1[5] == PinHandle(u1, "5")


def test_non_device_parts_are_unchanged() -> None:
    r1 = Part("R1", "Mini:Mini_R")
    assert r1["X"] == PinHandle(r1, "X")
    with pytest.raises(AttributeError) as caught:
        r1.X  # noqa: B018 - the access is the test
    assert not isinstance(caught.value, DslError)


def test_a_typo_names_the_closest_pin() -> None:
    _, u1 = _buck()
    with pytest.raises(PinNameError) as caught:
        u1.VINN  # noqa: B018 - the access is the test
    assert str(caught.value) == MESSAGE
    assert isinstance(caught.value, DslError) and isinstance(caught.value, AttributeError)
    assert not hasattr(u1, "VINN")


def test_wrong_case() -> None:
    _, u1 = _buck()
    with pytest.raises(PinNameError, match="closest: VIN;"):
        u1["vin"]
    with pytest.raises(PinNameError, match="has no pin '7'"):
        u1[7]


def test_part_attributes_win() -> None:
    _, u1 = _buck()
    assert u1.place.__func__ is Part.place  # type: ignore[attr-defined]
    assert u1.ref == "U1"


def test_private_names() -> None:
    _, u1 = _buck()
    with pytest.raises(AttributeError) as caught:
        u1._missing  # noqa: B018, SLF001 - the access is the test
    assert not isinstance(caught.value, DslError)
    assert copy.copy(u1).device is BUCK


def test_dir_lists_the_functions() -> None:
    _, u1 = _buck()
    names = dir(u1)
    assert {"BST", "EN", "FB", "GND", "SW", "VIN", "place"} <= set(names)
    assert "VIN" not in dir(Part("R1", "Mini:Mini_R"))


def test_device_part_checked_at_the_call() -> None:
    _, u1 = _buck()
    vin = Net("VIN")
    with pytest.raises(DslError) as caught:
        connect(vin, u1["VIM"])
    assert "VIM" in str(caught.value) and "closest: VIN" in str(caught.value)


def test_long_pin_lists_are_cut() -> None:
    pins = "\n".join(f'F{index:02d} = "{index}"' for index in range(1, 31))
    record = parse_device(
        "schema = 'fenolite.device.v0'\nid = 'Proj:Many'\nsummary = 'many pins'\nsymbol = 'Proj:S'\n"
        f"footprint = 'Proj:F'\nref_prefix = 'U'\nevidence = 'UNVERIFIED'\n[pins]\n{pins}\n"
    )
    design = Design("d")
    design.devices(record)
    many = design.part("U1", device="Proj:Many")
    with pytest.raises(PinNameError) as caught:
        many.ZZZ  # noqa: B018 - the access is the test
    text = str(caught.value)
    assert "closest" not in text and text.endswith("F24, …") and "F25" not in text


def test_led_pads_follow_the_anode() -> None:
    design = Design("d")
    d1 = design.part("D1", device="Fenolite:LED_0603")
    assert d1.pad("A").number == "2" and d1.pad("K").number == "1"
    assert d1.pad("1").number == "1"  # a pad number stays a pad number
    assert end_handle(d1, 0) == d1.A and end_handle(d1, 1) == d1.K
    assert end_handle(Part("R1", "Mini:Mini_R"), 0) is None
    with pytest.raises(PinNameError, match="has no pad or pin 'X'"):
        d1.pad("X")
    with pytest.raises(DslError, match="index"):
        d1.pad("A", index=1)


def test_buck_pad_by_function() -> None:
    _, u1 = _buck()
    assert u1.pad("GND").number == "2" and u1.pad("GND", index=1).number == "EP"


def test_must_connect_and_shadowed() -> None:
    assert must_connect_pins(BUCK) == ("4",) and must_connect_pins(None) == ()
    record = parse_device(
        "schema = 'fenolite.device.v0'\nid = 'Proj:Odd'\nsummary = 'odd names'\nsymbol = 'Proj:S'\n"
        "footprint = 'Proj:F'\nref_prefix = 'U'\nevidence = 'UNVERIFIED'\n[pins]\nplace = '1'\nOUT = '2'\n"
    )
    assert shadowed(record) == ("place",)
    design = Design("d")
    design.devices(record)
    odd = design.part("U1", device="Proj:Odd")
    assert odd["place"] == PinHandle(odd, "place") and callable(odd.place)
