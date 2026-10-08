# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The map records of a footprint model (capability altium-schematic-writer, "Pin map records of a
footprint model"; ``H-A-SCHX-PINMAP``; change c0123): which pins get a record 47, its keys, and the map of
a library symbol."""

from __future__ import annotations

import dataclasses

import pytest
from _schbuild import stacked_design, units_design

from fenolite.backends.altium import altsym, project
from fenolite.backends.altium.altsym import map_pins, map_records
from fenolite.backends.altium.schlib import footprint_chain
from fenolite.dsl import to_model
from fenolite.lens.altium import generic_pins
from fenolite.model.circuit import Component, Pin


def component(pairs: tuple[tuple[str, str], ...]) -> Component:
    pins = tuple(Pin(id=f"pin_00000000-0000-4000-8000-00000000000{n}", number=n) for n in "123")
    return Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="U1", pins=pins, pin_pad_map=pairs)


def test_records_of_one_map() -> None:
    """Scenario "Records of one map": a record for each pin whose pads are not the pad of its own
    designator alone, the form the public project sets hold."""
    assert altsym.MAP_RECORDS_FOR_EVERY_PIN is False
    found = map_pins(component((("3", "3"), ("3", "EP"))), ["1", "2", "3"])
    assert found == (("3", ("3", "EP")),)
    assert map_records(found, 7) == [
        [
            ("RECORD", "47"),
            ("OWNERINDEX", "7"),
            ("DESINTF", "3"),
            ("DESIMPCOUNT", "2"),
            ("DESIMP0", "3"),
            ("DESIMP1", "EP"),
        ]
    ]
    # a library record holds no owner key
    assert map_records(found)[0][1] == ("DESINTF", "3")
    # a component without a map has no record, and neither has a map of identity pairs alone
    assert map_pins(component(()), ["1", "2", "3"]) == ()
    assert map_pins(component((("1", "1"),)), ["1", "2", "3"]) == ()
    # the pins are those of the body, in its order; a renamed pad gives a record of one pad
    swapped = map_pins(component((("2", "1"), ("1", "2"))), ["1", "2", "3"])
    assert swapped == (("1", ("2",)), ("2", ("1",)))


def test_a_record_for_every_pin_is_one_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other value of the constant: a record for every pin of a component with a map, an identity
    record for a pin outside it; a component without a map still has none."""
    monkeypatch.setattr(altsym, "MAP_RECORDS_FOR_EVERY_PIN", True)
    found = map_pins(component((("3", "3"), ("3", "EP"))), ["1", "2", "3"])
    assert found == (("1", ("1",)), ("2", ("2",)), ("3", ("3", "EP")))
    swapped = map_pins(component((("2", "1"), ("1", "2"))), ["1", "2", "3"])
    assert swapped == (("1", ("2",)), ("2", ("1",)), ("3", ("3",)))
    assert map_pins(component(()), ["1", "2", "3"]) == ()


def test_the_chain_of_a_footprint_model() -> None:
    plain = footprint_chain("lib.PcbLib", "FP")
    assert [dict(record)["RECORD"] for record in plain] == ["44", "45", "46", "48"]
    mapped = footprint_chain("lib.PcbLib", "FP", (("3", ("3", "EP")), ("1", ("2",))))
    assert [dict(record)["RECORD"] for record in mapped] == ["44", "45", "46", "47", "47", "48"]
    assert dict(mapped[3]) == {
        "RECORD": "47",
        "DESINTF": "3",
        "DESIMPCOUNT": "2",
        "DESIMP0": "3",
        "DESIMP1": "EP",
    }
    assert mapped[:3] == plain[:3] and mapped[-1] == plain[-1]


def test_the_library_holds_the_map_that_every_component_holds() -> None:
    """A library symbol carries the map when every component of it holds the same pads on one footprint,
    and none otherwise; the sheet carries the map of each component in every case."""
    model = generic_pins(to_model(stacked_design()))
    libraries = project.library_symbols(model, name="stacked")
    symbols = {symbol.lib_ref: symbol for found in libraries.values() for symbol in found}
    assert dict(symbols["Mini_DualGate"].pin_pads) == {
        "3": ("3", "23"),
        "5": ("5", "15", "9"),
        "7": ("7", "27"),
        "14": ("14", "24"),
    }
    assert dict(symbols["Mini_R"].pin_pads) == {"1": ("1", "2"), "2": ("3", "4")}
    # the two LEDs hold other maps on other footprints: the library symbol holds none
    assert symbols["Mini_LED"].pin_pads == ()
    specs = {spec.ref: spec for spec in project.part_specs(model, name="stacked")}
    assert dict(specs["D1"].pin_pads) == {"1": ("2",), "2": ("1",)}
    assert dict(specs["D2"].pin_pads) == {"1": ("21", "17")}
    assert dict(specs["U1"].pin_pads) == dict(symbols["Mini_DualGate"].pin_pads)
    # a design without a map: no symbol and no part carries one
    plain = generic_pins(to_model(units_design()))
    components = tuple(dataclasses.replace(c, pin_pad_map=()) for c in plain.circuit.components)
    plain = dataclasses.replace(plain, circuit=dataclasses.replace(plain.circuit, components=components))
    assert all(not s.pin_pads for found in project.library_symbols(plain, name="u").values() for s in found)
    assert all(not spec.pin_pads for spec in project.part_specs(plain, name="u"))
