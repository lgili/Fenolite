# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The generated definitions of ``Design.hole()``: a footprint and a symbol per hole, in the library
``Fenolite_Holes`` (``docs/dsl.md``, "Holes"; capability design-dsl, "Board holes in the DSL"; change c0102).

A hole is a part: KiCad holds a hole only inside a footprint (``H-K-HOLE-FOOTPRINT``), so the footprint is
what a rebuild finds again. The footprint holds one pad at its origin, unnumbered and not plated, or
numbered ``1`` with copper; the flags that keep it out of the position file and the bill of materials; and
a courtyard on both sides, so the placement guard judges parts on either side (``H-K-HOLE-COURTYARD``).
The symbol has no pin, or one passive pin for a plated hole, and is not in the bill of materials, as the
mounting holes of KiCad's own library. No size is shipped: every length is the script's.
"""

from __future__ import annotations

import dataclasses

from fenolite.core.units import format_length
from fenolite.dsl.errors import DslError
from fenolite.dsl.footprint import Footprint
from fenolite.dsl.symbol import Symbol
from fenolite.dsl.units import Length, as_nm
from fenolite.model.library import FootprintDef, SymbolDef

HOLE_LIBRARY = "Fenolite_Holes"
"""The library of the generated hole footprints and symbols."""
HOLE_FLAGS: tuple[str, ...] = ("exclude_from_pos_files", "exclude_from_bom")
COURTYARD_LAYERS: tuple[str, ...] = ("F.CrtYd", "B.CrtYd")
COURTYARD_STROKE = 50_000
"""The pen of the courtyard, 0.05 mm, as KiCad's library draws courtyards."""
HOLE_SYMBOL = "Hole"
PAD_SYMBOL = "Hole_Pad"
REFERENCE_PREFIX = "H"
SYMBOL_RADIUS = 1_270_000
PIN_LENGTH = 2_540_000


class HoleFootprint(Footprint):
    """An authored footprint with the flags of a hole; ``definition`` adds them to the builder's."""

    @property
    def definition(self) -> FootprintDef:
        return dataclasses.replace(super().definition, flags=HOLE_FLAGS)


@dataclasses.dataclass(frozen=True, slots=True)
class HoleSymbol:
    """The holder of a generated symbol among ``Design.symbols``: the build reads ``definition`` of every
    entry, and the ``Symbol`` builder refuses a symbol without pins."""

    definition: SymbolDef

    @property
    def lib_id(self) -> str:
        return self.definition.lib_id


def _mm(value: int) -> str:
    return format_length(value, "mm").removesuffix("mm")


def _half(value: int) -> int:
    """Half of ``value``, rounded up: a courtyard is never smaller than asked."""
    return (value + 1) // 2


def hole_sizes(
    drill: object, *, length: object = None, pad: object = None, courtyard: object = None
) -> tuple[int, int | None, int | None, int | None]:
    """The four lengths of a hole in nanometres, checked: ``drill`` positive; ``length`` above ``drill``
    (a slot of that overall length); ``pad`` above ``drill`` (the width of its copper); ``courtyard`` at
    least the width of the hole and of its copper. ``DslError`` names the argument at fault."""
    hole = as_nm(drill, name="hole(): drill")
    if hole <= 0:
        raise DslError("hole(): drill must be a positive length")
    slot = None if length is None else as_nm(length, name="hole(): length")
    if slot is not None and slot <= hole:
        raise DslError("hole(): length is the overall length of a slot and must be above drill")
    copper = None if pad is None else as_nm(pad, name="hole(): pad")
    if copper is not None and copper <= hole:
        raise DslError("hole(): pad is the width of the copper and must be above drill")
    yard = None if courtyard is None else as_nm(courtyard, name="hole(): courtyard")
    if yard is not None and yard < (copper or hole):
        raise DslError("hole(): courtyard must be at least the width of the hole and of its copper")
    return hole, slot, copper, yard


def hole_name(hole: int, slot: int | None, copper: int | None, yard: int | None) -> str:
    """``NPTH_<d>mm`` or ``NPTH_Slot_<d>x<l>mm``, ``PTH_…_Pad_<p>mm`` with copper, and ``_Courtyard_<c>mm``
    when the courtyard is given: every size of the definition is in its name."""
    size = f"{_mm(hole)}mm" if slot is None else f"Slot_{_mm(hole)}x{_mm(slot)}mm"
    name = f"NPTH_{size}" if copper is None else f"PTH_{size}_Pad_{_mm(copper)}mm"
    return name if yard is None else f"{name}_Courtyard_{_mm(yard)}mm"


def hole_footprint(
    drill: object, *, length: object = None, pad: object = None, courtyard: object = None
) -> Footprint:
    """The footprint of a hole of ``drill``: round, or a slot of overall length ``length`` along the
    footprint's X axis; not plated, or with copper ``pad`` wide; its courtyard ``courtyard`` wide, by
    default as wide as the copper, or as the hole."""
    hole, slot, copper, yard = hole_sizes(drill, length=length, pad=pad, courtyard=courtyard)
    footprint = HoleFootprint(HOLE_LIBRARY, hole_name(hole, slot, copper, yard))
    width = copper if copper is not None else hole
    long = width if slot is None else slot + width - hole
    zero = Length(0)
    footprint.pad(
        "" if copper is None else "1",
        at=(zero, zero),
        size=(Length(long), Length(width)),
        shape="circle" if slot is None else "oval",
        kind="np_thru_hole" if copper is None else "thru_hole",
        drill=Length(hole),
        drill_shape="round" if slot is None else "slot",
        drill_length=None if slot is None else Length(slot),
    )
    wide = yard if yard is not None else width
    for layer in COURTYARD_LAYERS:
        if slot is None:
            footprint.circle(
                (zero, zero), (Length(_half(wide)), zero), layer=layer, width=Length(COURTYARD_STROKE)
            )
        else:
            x, y = _half(long + wide - width), _half(wide)
            footprint.rect(
                (Length(-x), Length(-y)), (Length(x), Length(y)), layer=layer, width=Length(COURTYARD_STROKE)
            )
    return footprint


def hole_symbol(*, plated: bool) -> SymbolDef:
    """``Fenolite_Holes:Hole``, a symbol without pins, or ``Fenolite_Holes:Hole_Pad`` with one passive pin
    ``1`` for a plated hole; both with the reference prefix ``H`` and outside the bill of materials."""
    name = PAD_SYMBOL if plated else HOLE_SYMBOL
    symbol = Symbol(HOLE_LIBRARY, name, reference=REFERENCE_PREFIX, value=name)
    symbol.circle((Length(0), Length(0)), (Length(SYMBOL_RADIUS), Length(0)))
    # the builder refuses a symbol without pins, so the pin is drawn and then left out for a bare hole
    symbol.pin(
        "1", "1", at=(Length(0), Length(-SYMBOL_RADIUS - PIN_LENGTH)), length=Length(PIN_LENGTH), rotation=90
    )
    definition = symbol.definition
    return dataclasses.replace(
        definition, in_bom=False, on_board=True, pins=definition.pins if plated else ()
    )


__all__ = [
    "COURTYARD_LAYERS",
    "COURTYARD_STROKE",
    "HOLE_FLAGS",
    "HOLE_LIBRARY",
    "HoleFootprint",
    "HoleSymbol",
    "hole_footprint",
    "hole_name",
    "hole_sizes",
    "hole_symbol",
]
