# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An empty ``Value`` that ``sch export netlist`` lists as ``~`` stays empty (``parity_inputs.sheet_values``,
change c0470; ``docs/formats/kicad/schematic.md``, H-K-SCH-COMPONENTS-2)."""

from __future__ import annotations

from fenolite.backends.kicad.parity_inputs import NETLIST_EMPTY_VALUE, sheet_values
from fenolite.core.coords import Point
from fenolite.model.circuit import Component
from fenolite.model.schematic import SchematicSheet, SymbolInstance, SymbolUse


def _symbol(ref: str, value: str, *, used_as: str = "") -> SymbolInstance:
    uses = (SymbolUse("demo", "/root", used_as),) if used_as else ()
    return SymbolInstance(
        id=f"sym-{ref}", lib_ref="Demo:R", position=Point(0, 0), ref=ref, value=value, uses=uses
    )


def test_a_tilde_of_the_netlist_is_the_empty_value_of_the_sheet() -> None:
    sheet = SchematicSheet(
        id="sheet",
        name="root",
        symbols=(_symbol("R1", ""), _symbol("R2", "~"), _symbol("R?", "", used_as="R4")),
    )
    components = [
        Component(id=f"c{n}", ref=f"R{n}", value=value)
        for n, value in (
            (1, NETLIST_EMPTY_VALUE),
            (2, NETLIST_EMPTY_VALUE),
            (3, NETLIST_EMPTY_VALUE),
            (4, "~"),
        )
    ]
    found = {c.ref: c.value for c in sheet_values(components, [sheet])}
    # R1 is empty on its sheet; R2 holds a literal tilde; R3 is on no sheet; R4 is empty through its use
    assert found == {"R1": "", "R2": "~", "R3": "~", "R4": ""}
