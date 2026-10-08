# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The design of change c0143: parts of the built-in catalog (library ``Fenolite``) and a ``Power``
interface whose nets no power-output pin drives, so the sheet needs power flags. Authored for Fenolite
with round invented values; the regulator's ``IN`` and ``GND`` pins are power inputs fed from a header."""

from __future__ import annotations

from fenolite.catalog import get_footprint, get_symbol
from fenolite.dsl import Design, Net, Part, Power, connect, mm

NAME = "regpower"
SHEET = f"{NAME}.kicad_sch"
SYMBOLS = ("Fenolite:Connector_2", "Fenolite:Linear_Regulator")
FOOTPRINTS = ("Fenolite:Header_1x2_P2.54", "Fenolite:SOT223_3_Diodes")
FLAGGED = ("GND", "VIN")
"""The nets of the power interface: each gets one flag."""


def regulator_design(*, power: bool = True) -> Design:
    """A two-pin header that feeds a linear regulator of the catalog; ``power`` declares the supply."""
    design = Design(NAME)
    design.board(mm(30), mm(20))
    j1 = Part("J1", SYMBOLS[0], footprint=FOOTPRINTS[0], value="IN")
    u1 = Part("U1", SYMBOLS[1], footprint=FOOTPRINTS[1], value="REG")
    design.add(j1, u1)
    vin, gnd, vout = Net("VIN"), Net("GND"), Net("VOUT")
    connect(vin, j1[1], u1["IN"])
    connect(gnd, j1[2], u1["GND"])
    connect(vout, u1["OUT"])
    if power:
        design.add(Power(vin, gnd))
    j1.place(mm(8), mm(10))
    u1.place(mm(20), mm(10))
    return design


def catalog_definitions() -> dict[str, dict[str, object]]:
    """The ``authored_symbols`` and ``authored_footprints`` of a build of the design: the definitions of
    its catalog ids, as ``fenolite build`` passes them."""
    return {
        "authored_symbols": {lib_id: get_symbol(lib_id) for lib_id in SYMBOLS},
        "authored_footprints": {lib_id: get_footprint(lib_id) for lib_id in FOOTPRINTS},
    }
