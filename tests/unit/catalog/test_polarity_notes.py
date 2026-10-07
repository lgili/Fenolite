# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Diode lands whose pad 1 is the cathode (capability fenolite-component-catalog, "Lands numbered against
the generic diode symbols are documented"; change c0144).

The generic symbols ``Diode``, ``Zener_Diode`` and ``LED`` have pin 1 anode and pin 2 cathode. A land that
keeps a manufacturer's numbering with pad 1 at the cathode needs a pin-to-pad map with them, and the
catalog pages say so for each. The four kit samples that put ``Fenolite:LED`` on such a land carry the map
and connect the LED by pin name."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.catalog import get_footprint, get_symbol, list_entries
from fenolite.cli._script import run_design_script
from fenolite.core.ids import derived_id
from fenolite.dsl import to_model

ROOT = Path(__file__).resolve().parents[3]
SOURCES = ROOT / "docs" / "catalog" / "sources.md"
COVERAGE = ROOT / "docs" / "catalog" / "coverage.md"
CATHODE_FIRST = (
    "Fenolite:LED0603_Kingbright_APT1608SURCK",
    "Fenolite:LED0805_Kingbright_APT2012SURCK",
    "Fenolite:SOD128_Nexperia_CFP5",
)
"""The lands whose cathode mark is on the side of pad 1."""
KIT_SAMPLES = ("board6", "flat", "libs", "routed")
WARNING = "pin-to-pad map"


def _cathode_first(lib_id: str) -> bool:
    """Whether the footprint has a cathode mark and its pad 1 lies on the mark's side."""
    footprint = get_footprint(lib_id)
    marks = [graphic for graphic in footprint.graphics if _is_mark(lib_id, graphic.id)]
    pads = {pad.number: pad.position.x for pad in footprint.pads}
    if not marks or set(pads) != {"1", "2"}:
        return False
    return (marks[0].points[0].x < 0) == (pads["1"] < 0)


def _is_mark(lib_id: str, graphic_id: str) -> bool:
    return graphic_id == derived_id("gfx", "fenolite.catalog", f"{lib_id.removeprefix('Fenolite:')}:cathode")


def test_the_generic_diode_symbols_have_the_anode_on_pin_1() -> None:
    for name in ("Diode", "Zener_Diode", "LED"):
        assert [(pin.number, pin.name) for pin in get_symbol(f"Fenolite:{name}").pins] == [
            ("1", "A"),
            ("2", "K"),
        ]


def test_the_cathode_first_lands_are_the_known_ones() -> None:
    """A new land with pad 1 at its cathode mark must be named here, and so gets its warning."""
    found = [entry.lib_id for entry in list_entries(kind="footprint") if _cathode_first(entry.lib_id)]
    assert sorted(found) == sorted(CATHODE_FIRST)


@pytest.mark.parametrize("lib_id", CATHODE_FIRST)
def test_a_cathode_first_land_carries_the_warning(lib_id: str) -> None:
    """Scenario "Warning beside each land": the row of the land in the sources page and the coverage page."""
    name = lib_id.removeprefix("Fenolite:")
    row = next(line for line in SOURCES.read_text(encoding="utf-8").splitlines() if f"`{lib_id}`" in line)
    assert "cathode" in row and WARNING.replace("map", "mapping") in row
    coverage = COVERAGE.read_text(encoding="utf-8")
    lines = coverage.splitlines()
    index = next(i for i, line in enumerate(lines) if f"`{name}`" in line)
    assert any(WARNING in line and "cathode" in line for line in lines[index : index + 3])


@pytest.mark.parametrize("sample", KIT_SAMPLES)
def test_the_kit_led_is_mapped_and_drawn_the_right_way_round(sample: str) -> None:
    """Scenario "Kit LED": the cathode pin is on ``GND`` and on pad 1, the anode pin on pad 2."""
    design = run_design_script(ROOT / "examples" / "kit" / sample / "design.py").design
    part = design.parts["D1"]
    assert part.footprint in CATHODE_FIRST
    number = {key: pin.number for pin in get_symbol("Fenolite:LED").pins for key in (pin.number, pin.name)}
    model = to_model(design)
    d1 = next(component for component in model.circuit.components if component.ref == "D1")
    nets = {
        number[member.pin]: net.name
        for net in model.circuit.nets
        for member in net.members
        if member.component_id == d1.id
    }
    assert nets == {number["K"]: "GND", number["A"]: "LED_A"}
    assert part.pad_map == {number["K"]: "1", number["A"]: "2"}
