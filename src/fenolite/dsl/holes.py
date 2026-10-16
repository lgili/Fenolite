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

The footprint is built by ``fenolite.model.holes`` (change c0170), which a conversion to KiCad uses for a
model ``Hole``; this module checks the script's lengths, wraps the definition for ``Design.footprints`` and
re-exports the model's names, so a script's footprints keep their bytes.
"""

from __future__ import annotations

import dataclasses

from fenolite.dsl.errors import DslError
from fenolite.dsl.footprint import Footprint
from fenolite.dsl.symbol import Symbol
from fenolite.dsl.units import Length, as_nm
from fenolite.model import holes as model_holes
from fenolite.model.holes import COURTYARD_LAYERS, COURTYARD_STROKE, HOLE_FLAGS, HOLE_LIBRARY, hole_name
from fenolite.model.library import FootprintDef, SymbolDef

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


class GeneratedHoleFootprint(HoleFootprint):
    """A hole footprint built by ``fenolite.model.holes.hole_footprint``, held as ``Design.footprints``
    holds an authored one: its ``definition`` is the model's, unchanged."""

    def __init__(self, definition: FootprintDef) -> None:
        super().__init__(definition.library, definition.name)
        self._pads = list(definition.pads)
        self._graphics = list(definition.graphics)
        self._generated = definition

    @property
    def definition(self) -> FootprintDef:
        return self._generated


def hole_footprint(
    drill: object, *, length: object = None, pad: object = None, courtyard: object = None
) -> Footprint:
    """The footprint of a hole of ``drill``: round, or a slot of overall length ``length`` along the
    footprint's X axis; not plated, or with copper ``pad`` wide; its courtyard ``courtyard`` wide, by
    default as wide as the copper, or as the hole (``fenolite.model.holes.hole_footprint`` of the checked
    lengths)."""
    hole, slot, copper, yard = hole_sizes(drill, length=length, pad=pad, courtyard=courtyard)
    return GeneratedHoleFootprint(model_holes.hole_footprint(hole, length=slot, pad=copper, courtyard=yard))


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
    "GeneratedHoleFootprint",
    "HoleFootprint",
    "HoleSymbol",
    "hole_footprint",
    "hole_name",
    "hole_sizes",
    "hole_symbol",
]
