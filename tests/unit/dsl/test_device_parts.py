# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Parts placed from devices (change c0248; capability design-dsl, "Device parts in the DSL" to "Device
parts in the model"). The example device is authored for Fenolite and illustrative."""

from __future__ import annotations

import hashlib
import runpy
from pathlib import Path

import pytest

from fenolite.catalog.devices import device_digest, parse_device
from fenolite.dsl import Design, DslError, Module, Part, ohm, to_model
from fenolite.model import canonical

ROOT = Path(__file__).resolve().parents[3]
BUCK = parse_device((ROOT / "tests" / "data" / "devices" / "example_buck.toml").read_text(encoding="utf-8"))
BLINK_DIGEST = "1b54c15a7e1a97e00bca5408e586168b22ba4782a4eda219f39d9e7b79aea946"
"""The digest of the model texts of ``examples/blink_2layer/design.py`` before change c0248 (computed at its
base commit 3cabfe5a with the same function)."""


def _digest(texts: dict[str, str]) -> str:
    return hashlib.sha256("".join(f"{k}\n{v}" for k, v in sorted(texts.items())).encode()).hexdigest()


def _component(design: Design, ref: str):  # noqa: ANN202 - a model component
    return next(c for c in to_model(design).circuit.components if c.ref == ref)


def test_neither_or_both() -> None:
    with pytest.raises(DslError, match="exactly one of lib_id and device"):
        Part("U1")
    with pytest.raises(DslError, match="exactly one of lib_id and device"):
        Part("U1", "Fenolite:Resistor", device="Fenolite:R_0603")


def test_unknown_device() -> None:
    with pytest.raises(DslError, match="Fenolite:R_0603"):
        Part("R1", device="Fenolite:R_0630")


def test_created_in_a_module() -> None:
    design = Design("d")
    power = Module("power")
    design.add(power)
    c1 = power.part("C1", device="Fenolite:C_0603")
    assert c1.path == "power/C1" and design.parts["power/C1"] is c1
    assert c1.device is not None and c1.device.id == "Fenolite:C_0603"


def test_design_part_without_a_device() -> None:
    design = Design("d")
    r1 = design.part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="330")
    assert design.parts["R1"] is r1 and r1.device is None and r1.value == "330"


def test_a_part_from_a_device() -> None:
    design = Design("d")
    design.devices(BUCK)
    u1 = design.part("U1", device="Example:BUCK_6V_2A")
    assert u1.device is BUCK
    component = _component(design, "U1")
    assert component.lib_symbol_ref == "Example:Buck_6pin"
    assert component.lib_footprint_ref == "Fenolite:SOT23_6_TI_DBV0006A"
    assert component.value == "EXB6202"
    assert component.properties["MPN"] == "EXB6202" and component.properties["Manufacturer"] == "Example Semi"
    assert component.properties["fenolite.device"] == "Example:BUCK_6V_2A"
    assert component.properties["fenolite.device.sha256"] == device_digest(BUCK)
    assert ("2", "EP") in component.pin_pad_map and component.pin_pad_map == BUCK.pad_map


def test_footprint_given_with_a_device() -> None:
    with pytest.raises(DslError, match="device names the footprint"):
        Part("R1", device="Fenolite:R_0603", footprint="Fenolite:Chip_0805")
    with pytest.raises(DslError, match="device names the pad_map"):
        Part("R1", device="Fenolite:R_0603", pad_map={"1": "2", "2": "1"})


def test_a_generic_device_takes_a_value() -> None:
    design = Design("d")
    design.part("R1", device="Fenolite:R_0603", value=ohm("4k7"))
    component = _component(design, "R1")
    assert component.value == "4.7kΩ" and component.lib_footprint_ref == "Fenolite:Chip_0603"
    assert "MPN" not in component.properties and "Manufacturer" not in component.properties


def test_conflicting_mpn() -> None:
    design = Design("d")
    design.devices(BUCK)
    with pytest.raises(DslError, match="MPN"):
        design.part("U1", device="Example:BUCK_6V_2A", properties={"mpn": "OTHER"})
    same = design.part("U1", device="Example:BUCK_6V_2A", properties={"MPN": "EXB6202", "Note": "x"})
    assert dict(same.properties) == {"MPN": "EXB6202", "Manufacturer": "Example Semi", "Note": "x"}


def test_reserved_names_stay_reserved() -> None:
    with pytest.raises(DslError, match="reserved prefix"):
        Part("R1", device="Fenolite:R_0603", properties={"fenolite.device": "x"})


def test_designs_without_devices_are_unchanged() -> None:
    namespace = runpy.run_path(str(ROOT / "examples" / "blink_2layer" / "design.py"))
    texts = canonical.dump_texts(to_model(namespace["design"]))
    assert _digest(texts) == BLINK_DIGEST
    assert "fenolite.device" not in "".join(texts.values())
