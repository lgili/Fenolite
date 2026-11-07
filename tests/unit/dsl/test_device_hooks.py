# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Devices filling the hooks of the other circuits-as-code changes: the named ends of c0247 (``part.a``,
``part.b``, ``must_connect_pins``), the prefix of c0249's lock and the block builder of c0251. The example
device is authored for Fenolite and illustrative."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fenolite.catalog.devices import parse_device
from fenolite.dsl import Design, Module, Net, Part, block, connect, to_model
from fenolite.lens.build import must_connect_pins

ROOT = Path(__file__).resolve().parents[3]
BUCK = parse_device((ROOT / "tests" / "data" / "devices" / "example_buck.toml").read_text(encoding="utf-8"))


def test_led_ends_follow_the_anode() -> None:
    design = Design("d")
    d1 = design.part("D1", device="Fenolite:LED_0603")
    assert d1.a == d1.A and d1.b == d1.K and d1.two_terminal
    r1 = design.part("R1", device="Fenolite:R_0603", value="1k")
    assert r1.a == r1.P1 and r1.b == r1.P2  # the ends the record names
    connect(Net("LED"), r1.b, d1.a)
    model = to_model(design)
    assert {c.ref for c in model.circuit.components} == {"D1", "R1"}


def test_device_prefix_feeds_the_lock() -> None:
    design = Design("d")
    led = design.part(device="Fenolite:LED_0603")
    mod = Module("m")
    design.add(mod)
    cap = mod.part(device="Fenolite:C_0603", value="100n")
    other = mod.part(device="Fenolite:C_0603", name="c_out", value="1u")
    assert (led.prefix, led.key, cap.path, other.path) == ("D", "D", "m/C", "m/c_out")
    refs = {c.properties["fenolite.path"]: c.ref for c in to_model(design).circuit.components}
    assert refs == {"D": "D1", "m/C": "C1", "m/c_out": "C2"}


def test_explicit_prefix_wins_over_the_device() -> None:
    part = Part(device="Fenolite:R_0603", prefix="RS", value="10m")
    assert part.prefix == "RS" and part.explicit_ref is None


def test_block_part_from_a_device() -> None:
    @block
    def led(b: Any) -> None:
        b.part("LED", device="Fenolite:LED_0603")

    design = Design("d")
    first = design.use(led, "a")
    design.use(led, "b")
    assert first.part("LED").device is not None
    refs = {c.properties["fenolite.path"]: c.ref for c in to_model(design).circuit.components}
    assert refs == {"a/LED": "D1", "b/LED": "D2"}


def test_must_connect_pins_read_the_device() -> None:
    design = Design("d")
    design.add(Part("U1", "Fenolite:Resistor"))
    component = to_model(design).circuit.components[0]
    assert must_connect_pins(component) == frozenset()
    assert must_connect_pins(component, BUCK) == frozenset({"4"})
