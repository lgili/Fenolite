# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Port and sheet-entry directions (capability altium-schematic-writer, "Port and sheet-entry
directions"; change c0086): the closed table, the rule on the tree sample, the records, and the switch."""

from __future__ import annotations

import itertools

import pytest
from _altium_tree import documents, tree_build, tree_model

from fenolite.backends.altium.hierarchy import DIRECTIONS, DRIVERS, INPUTS, PIN_CLASSES, direction, pin_class
from fenolite.backends.altium.read.sch import SheetEntry
from fenolite.backends.altium.schdoc import IO_TYPES


def test_the_table_is_closed() -> None:
    assert set(DIRECTIONS) == set(itertools.product(PIN_CLASSES, PIN_CLASSES))
    assert set(DIRECTIONS.values()) == set(IO_TYPES)
    assert IO_TYPES == {"unspecified": 0, "output": 1, "input": 2, "bidirectional": 3}
    for inside, outside in DIRECTIONS:
        if "bidirectional" in (inside, outside):
            assert DIRECTIONS[(inside, outside)] == "bidirectional"
        elif inside == "passive":
            assert DIRECTIONS[(inside, outside)] == "unspecified"
    assert DIRECTIONS[("driver", "driver")] == "bidirectional"
    assert DIRECTIONS[("driver", "input")] == DIRECTIONS[("driver", "passive")] == "output"
    assert {DIRECTIONS[("input", other)] for other in ("driver", "input", "passive")} == {"input"}


@pytest.mark.parametrize(
    ("types", "expected"),
    [
        ((), "passive"),
        (("passive", "free", "unspecified", "no_connect"), "passive"),
        (("input", "passive"), "input"),
        (("power_in",), "input"),
        (("input", "output"), "driver"),
        (("output", "bidirectional"), "bidirectional"),
        *(((kind,), "driver") for kind in sorted(DRIVERS)),
        *(((kind,), "input") for kind in sorted(INPUTS)),
    ],
)
def test_pin_class(types: tuple[str, ...], expected: str) -> None:
    assert pin_class(types) == expected


def test_a_driven_net_and_a_passive_net() -> None:
    """Scenarios "A driven net" and "Passive net": ``SENSE`` has an output pin inside ``io`` and an input
    outside; ``LED_K`` holds only passive pins."""
    model = tree_build().design  # the built model holds the pins of the symbols, with their types
    nets = model.nets_by_name
    assert direction(tree_model(), tree_model().nets_by_name["SENSE"], "io") == "unspecified"  # no pin yet
    assert direction(model, nets["SENSE"], "io") == "output"
    assert direction(model, nets["ALARM"], "io") == "input"  # driven from the top sheet
    assert direction(model, nets["SENSE_IN"], "io") == "input"  # an input inside, a connector outside
    assert direction(model, nets["LED_K"], "io/leds") == "unspecified"


def test_port_and_sheet_entry_carry_one_type() -> None:
    """Scenarios "A driven net" and "Passive net": ``SENSE`` leaves ``io`` as an output on both ends,
    and ``LED_K`` holds no ``IOTYPE`` on either."""
    sheets = documents(tree_build())
    ports = {p.name: p for p in sheets["tree_io.SchDoc"].ports()}
    entries = {e.name: e for e in sheets["tree.SchDoc"].of_type(SheetEntry)}
    assert {name: ports[name].io_type for name in ports} == {
        "ALARM": 2,
        "D[0..3]": 0,
        "SENSE": 1,
        "SENSE_IN": 2,
    }
    assert {name: entries[name].io_type for name in entries} == {name: ports[name].io_type for name in ports}
    leds = {p.name: p for p in sheets["tree_io.leds.SchDoc"].ports()}
    inner = {e.name: e for e in sheets["tree_io.SchDoc"].of_type(SheetEntry)}
    assert leds["LED_K"].io_type == inner["LED_K"].io_type == 0
    assert leds["LED_K"].props is not None and not leds["LED_K"].props.has("IOTYPE")  # zero is left out
    assert inner["LED_K"].props is not None and not inner["LED_K"].props.has("IOTYPE")


def test_directions_off() -> None:
    output = tree_build(directions=False)
    for sheet in documents(output).values():
        assert all(p.io_type == 0 for p in sheet.ports())
        assert all(e.io_type == 0 for e in sheet.of_type(SheetEntry))
    summary = output.summary["schematic"]
    assert isinstance(summary, dict) and summary["directions"] == "off" and summary["directed"] == 0
    on = tree_build().summary["schematic"]
    assert isinstance(on, dict) and on["directions"] == "on" and on["directed"] == 6
