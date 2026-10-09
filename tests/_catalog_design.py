# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The catalog blink: a design that names only lib ids of the built-in catalog (change c0077).

Authored for Fenolite with round invented values. A two-pin header feeds a resistor and a LED; every
part is placed and each of the three nets has one scripted track, so the board is complete without a
router and without a zone fill. The acceptance tests of the catalog build it on a machine that has no
KiCad library (``tests/unit/cli/test_catalog_only.py``) and give it to KiCad
(``tests/kicad/build/test_catalog_only.py``).
"""

from __future__ import annotations

from pathlib import Path

from fenolite.dsl import Design, Net, Part, connect, mm

NAME = "catalog_blink"
REFS = ("D1", "J1", "R1")
VALUES = {"D1": "LED", "J1": "IN", "R1": "330"}
FOOTPRINTS = {
    "D1": "Fenolite:Chip_0805",
    "J1": "Fenolite:Header_1x2_P2.5",
    "R1": "Fenolite:Chip_0603",
}
SCRIPT = "from _catalog_design import catalog_blink\n\ndesign = catalog_blink()\n"
"""A design script for ``fenolite build``: ``tests/`` is on the import path of the suites."""


def catalog_blink() -> Design:
    """The three-part design: header, resistor and LED of the catalog, three nets, three tracks."""
    design = Design(NAME)
    design.board(mm(30), mm(20))
    j1 = Part("J1", "Fenolite:Connector_2", footprint=FOOTPRINTS["J1"], value=VALUES["J1"])
    r1 = Part("R1", "Fenolite:Resistor", footprint=FOOTPRINTS["R1"], value=VALUES["R1"])
    d1 = Part("D1", "Fenolite:LED", footprint=FOOTPRINTS["D1"], value=VALUES["D1"])
    design.add(j1, r1, d1)
    vin, gnd, led_a = Net("VIN"), Net("GND"), Net("LED_A")
    connect(vin, j1[1], r1[1])
    connect(led_a, r1[2], d1[1])
    connect(gnd, d1[2], j1[2])
    design.rules.minimum(
        clearance=mm(0.15), track_width=mm(0.15), via_diameter=mm(0.45), via_drill=mm(0.2),
        hole_size=mm(0.3), edge_clearance=mm(0.3),
    )  # fmt: skip
    j1.place(mm(6), mm(10))
    r1.place(mm(14), mm(12))
    d1.place(mm(22), mm(12))
    design.track("vin", j1.pad(1), (mm(8), mm(12)), r1.pad(1), width=mm(0.3))
    design.track("led_a", r1.pad(2), d1.pad(1), width=mm(0.3))
    design.track(
        "gnd", d1.pad(2), (mm(25), mm(12)), (mm(25), mm(6)), (mm(6), mm(6)), j1.pad(2), width=mm(0.3)
    )
    return design


def write_script(folder: Path, append: str = "") -> Path:
    """``design.py`` under ``folder`` that builds the catalog blink; ``append`` adds lines to it. No
    library table is written: the catalog needs none."""
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "design.py"
    script.write_text(SCRIPT + append, encoding="utf-8")
    return script
