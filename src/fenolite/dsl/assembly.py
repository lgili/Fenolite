# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The generated definitions of the assembly and test features of a script: fiducials, test points and
tooling holes, in the library ``Fenolite_Assembly`` (``docs/dsl.md``, "Assembly and test features";
capability design-dsl, "Fiducials in the DSL", "Test points in the DSL" and "Tooling holes in the DSL";
change c0118).

KiCad's library parts carry no fabrication mark, so each footprint here is generated with the mark on
its pad (``Pad.fab_property``), as ``fenolite.dsl.holes`` generates the hole footprints of c0102. Every
size is the script's: no value is shipped. The clear area around a fiducial or a tooling hole is a
keep-out whose outline (``clear_outline``) is an octagon: a model outline holds points only.
"""

from __future__ import annotations

import dataclasses
import math

from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm, format_length
from fenolite.dsl.errors import DslError
from fenolite.dsl.footprint import Footprint
from fenolite.dsl.holes import COURTYARD_LAYERS, COURTYARD_STROKE, HoleFootprint
from fenolite.dsl.symbol import Symbol
from fenolite.dsl.units import Length, as_nm
from fenolite.model.board import Pad, PadFabProperty
from fenolite.model.library import FootprintDef, FootprintKind, SymbolDef

ASSEMBLY_LIBRARY = "Fenolite_Assembly"
"""The library of the generated fiducial, test-point and tooling-hole footprints and symbols."""
FIDUCIAL_SYMBOL = "Fiducial"
TEST_POINT_SYMBOL = "TestPoint"
FIDUCIAL_FLAGS: tuple[str, ...] = ("exclude_from_bom",)
"""A fiducial is in the position file and not in the bill of materials, as KiCad's library fiducials."""
TEST_POINT_FLAGS: tuple[str, ...] = ("exclude_from_pos_files", "exclude_from_bom")
"""A bare test pad is neither placed nor bought, as KiCad's library test points."""
SYMBOL_RADIUS = 1_270_000
PIN_LENGTH = 2_540_000
_ZERO = Length(0)


class AssemblyFootprint(Footprint):
    """A generated footprint of ``Fenolite_Assembly``: the builder's footprint with its exclusion flags,
    and the unnumbered surface pads of a fiducial, which the builder refuses to an authored footprint."""

    def __init__(self, name: str, *, kind: FootprintKind, flags: tuple[str, ...]) -> None:
        super().__init__(ASSEMBLY_LIBRARY, name, kind=kind)
        self.flags = flags

    def unnumbered_pad(
        self, size: Nm, *, layers: tuple[str, ...], fab_property: PadFabProperty | None
    ) -> None:
        """One unnumbered round ``smd`` pad of ``size`` at the origin, keyed as the builder keys the k-th
        unnumbered pad (``<lib id>:pad::<k>``)."""
        index = sum(p.number == "" for p in self._pads) + 1
        self._pads.append(
            Pad(
                id=derived_id("pad", "fenolite.dsl", f"{self.lib_id}:pad::{index}"),
                number="",
                shape="circle",
                size=Size(size, size),
                position=Point(0, 0),
                kind="smd",
                layers=layers,
                fab_property=fab_property,
            )
        )

    @property
    def definition(self) -> FootprintDef:
        return dataclasses.replace(super().definition, flags=self.flags)


@dataclasses.dataclass(frozen=True, slots=True)
class AssemblySymbol:
    """The holder of a generated symbol among ``Design.symbols``, as ``holes.HoleSymbol``: the build reads
    ``definition`` of every entry."""

    definition: SymbolDef

    @property
    def lib_id(self) -> str:
        return self.definition.lib_id


def clear_outline(x: Nm, y: Nm, diameter: Nm) -> tuple[Point, ...]:
    """The octagon that stands for the clear area of ``diameter`` around ``(x, y)``: a keep-out outline
    holds points only.

    Its apothem is ``a = ⌈diameter / 2⌉`` and its corner offset ``b = ⌈√(2a²)⌉ − a``, with the vertices
    ``(x + a, y − b)``, ``(x + a, y + b)``, ``(x + b, y + a)``, ``(x − b, y + a)``, ``(x − a, y + b)``,
    ``(x − a, y − b)``, ``(x − b, y − a)`` and ``(x + b, y − a)`` in this order. It contains the circle of
    ``diameter``: every edge is at least ``diameter / 2`` from the centre. Its corners reach about 8.2 %
    further out than the circle, and its area is about 5.5 % larger. Integers only (``math.isqrt``).
    """
    if type(diameter) is not int or diameter <= 0:
        raise ValueError(
            f"the diameter of a clear area is a positive integer of nanometres, got {diameter!r}"
        )
    a = -(-diameter // 2)
    root = math.isqrt(2 * a * a)
    b = root + (root * root < 2 * a * a) - a
    return (
        Point(x + a, y - b), Point(x + a, y + b), Point(x + b, y + a), Point(x - b, y + a),
        Point(x - a, y + b), Point(x - a, y - b), Point(x - b, y - a), Point(x + b, y - a),
    )  # fmt: skip


def _mm(value: int) -> str:
    """A length as the name of a definition holds it: ``1mm``, ``1.5mm``."""
    return format_length(value, "mm")


def _half(value: int) -> int:
    """Half of ``value``, rounded up: a courtyard is never smaller than asked."""
    return (value + 1) // 2


def _courtyard(footprint: Footprint, width: Nm, *, square: bool, layers: tuple[str, ...]) -> None:
    half = Length(_half(width))
    for layer in layers:
        if square:
            footprint.rect(
                (Length(-half.nm), Length(-half.nm)),
                (half, half),
                layer=layer,
                width=Length(COURTYARD_STROKE),
            )
        else:
            footprint.circle((_ZERO, _ZERO), (half, _ZERO), layer=layer, width=Length(COURTYARD_STROKE))


def fiducial_name(copper: Nm, mask: Nm, clear: Nm, *, local: bool) -> str:
    """``Fiducial_<c>_Mask<m>``, ``Fiducial_Local_…`` for a local one, ``_Clear<k>`` when the clear area
    differs from the mask opening: every size of the definition is in its name."""
    name = f"Fiducial_{'Local_' if local else ''}{_mm(copper)}_Mask{_mm(mask)}"
    return name if clear == mask else f"{name}_Clear{_mm(clear)}"


def fiducial_footprint(copper: Nm, mask: Nm, clear: Nm, *, local: bool) -> AssemblyFootprint:
    """The footprint of a fiducial (design Decision 4): the copper pad ``copper`` wide on ``F.Cu`` and
    ``F.Mask`` with the mark ``fiducial_global`` (``fiducial_local`` when ``local``), the aperture pad
    ``mask`` wide on ``F.Mask`` only, and a courtyard circle of diameter ``clear``. The lengths are
    checked by ``Design.fiducial``."""
    footprint = AssemblyFootprint(
        fiducial_name(copper, mask, clear, local=local), kind="smd", flags=FIDUCIAL_FLAGS
    )
    mark: PadFabProperty = "fiducial_local" if local else "fiducial_global"
    footprint.unnumbered_pad(copper, layers=("F.Cu", "F.Mask"), fab_property=mark)
    footprint.unnumbered_pad(mask, layers=("F.Mask",), fab_property=None)
    _courtyard(footprint, clear, square=False, layers=("F.CrtYd",))
    return footprint


def test_point_name(size: Nm, *, shape: str, drill: Nm | None, courtyard: Nm | None) -> str:
    """``TestPoint_Pad_D<s>`` or ``TestPoint_Pad_<s>x<s>``, ``TestPoint_THTPad_…_Drill<d>`` for a
    through-hole pad, and ``_Courtyard_<c>`` when the courtyard is given."""
    kind = "Pad" if drill is None else "THTPad"
    side = _mm(size).removesuffix("mm")
    body = f"D{_mm(size)}" if shape == "circle" else f"{side}x{_mm(size)}"
    name = f"TestPoint_{kind}_{body}" + ("" if drill is None else f"_Drill{_mm(drill)}")
    return name if courtyard is None else f"{name}_Courtyard_{_mm(courtyard)}"


def test_point_footprint(
    size: Nm, *, shape: str, drill: Nm | None, courtyard: Nm | None
) -> AssemblyFootprint:
    """The footprint of a test point (design Decision 6): pad ``1`` of ``size`` and ``shape`` with the
    mark ``test_point``, SMD on ``F.Cu`` and ``F.Mask``, or plated through-hole on ``*.Cu`` and ``*.Mask``
    with ``drill``; a courtyard ``courtyard`` wide (by default ``size``), round or square as the pad, on
    ``F.CrtYd`` and, for a through-hole pad, ``B.CrtYd``. The lengths are checked by ``Design.test_point``."""
    footprint = AssemblyFootprint(
        test_point_name(size, shape=shape, drill=drill, courtyard=courtyard),
        kind="unspecified",
        flags=TEST_POINT_FLAGS,
    )
    footprint.pad(
        "1",
        at=(_ZERO, _ZERO),
        size=(Length(size), Length(size)),
        shape=shape,
        kind="smd" if drill is None else "thru_hole",
        drill=None if drill is None else Length(drill),
        layers=("F.Cu", "F.Mask") if drill is None else ("*.Cu", "*.Mask"),
        fab_property="test_point",
    )
    layers = ("F.CrtYd",) if drill is None else ("F.CrtYd", "B.CrtYd")
    _courtyard(footprint, courtyard or size, square=shape == "rect", layers=layers)
    return footprint


def tooling_hole_footprint(drill: Nm, clear: Nm | None) -> HoleFootprint:
    """The footprint of a tooling hole (design Decision 7): the not-plated hole of ``hole()`` with its
    courtyards ``clear`` wide (by default ``drill``), named ``ToolingHole_<d>`` with ``_Clear<c>`` in
    ``Fenolite_Assembly``. The library name is the tooling mark: KiCad has no pad mark for it."""
    name = f"ToolingHole_{_mm(drill)}" + ("" if clear is None else f"_Clear{_mm(clear)}")
    hole = HoleFootprint(ASSEMBLY_LIBRARY, name)
    hole.pad(
        "",
        at=(_ZERO, _ZERO),
        size=(Length(drill), Length(drill)),
        shape="circle",
        kind="np_thru_hole",
        drill=Length(drill),
    )
    _courtyard(hole, clear or drill, square=False, layers=COURTYARD_LAYERS)
    return hole


def _symbol_body(symbol: Symbol) -> None:
    symbol.circle((_ZERO, _ZERO), (Length(SYMBOL_RADIUS), _ZERO))
    symbol.pin(
        "1", "1", at=(_ZERO, Length(-SYMBOL_RADIUS - PIN_LENGTH)), length=Length(PIN_LENGTH), rotation=90
    )


def fiducial_symbol() -> SymbolDef:
    """``Fenolite_Assembly:Fiducial``: no pin, reference prefix ``FID``, outside the bill of materials."""
    symbol = Symbol(ASSEMBLY_LIBRARY, FIDUCIAL_SYMBOL, reference="FID", value=FIDUCIAL_SYMBOL)
    # the builder refuses a symbol without pins, so the pin is drawn and then left out
    _symbol_body(symbol)
    return dataclasses.replace(symbol.definition, in_bom=False, on_board=True, pins=())


def test_point_symbol() -> SymbolDef:
    """``Fenolite_Assembly:TestPoint``: one passive pin ``1``, reference prefix ``TP``, outside the bill of
    materials (a bare pad is never bought)."""
    symbol = Symbol(ASSEMBLY_LIBRARY, TEST_POINT_SYMBOL, reference="TP", value=TEST_POINT_SYMBOL)
    _symbol_body(symbol)
    return dataclasses.replace(symbol.definition, in_bom=False, on_board=True)


def check_length(
    call: str, name: str, value: object, *, least: Nm = 1, what: str = "a positive length"
) -> Nm:
    """``value`` as nanometres, at least ``least``; ``DslError`` names ``call`` and the argument."""
    nm = as_nm(value, name=f"{call}: {name}")
    if nm < least:
        raise DslError(f"{call}: {name} must be {what}")
    return nm


__all__ = [
    "ASSEMBLY_LIBRARY",
    "FIDUCIAL_FLAGS",
    "TEST_POINT_FLAGS",
    "AssemblyFootprint",
    "AssemblySymbol",
    "clear_outline",
    "fiducial_footprint",
    "fiducial_name",
    "fiducial_symbol",
    "test_point_footprint",
    "test_point_name",
    "test_point_symbol",
    "tooling_hole_footprint",
]
