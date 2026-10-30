# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Builder for project-authored symbol definitions: one or several units, hidden pins, alternates,
derived symbols (change c0261), and symbols generated from pin tables (``Symbol.from_pins``)."""

from __future__ import annotations

import re
from collections.abc import Sequence

from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.dsl.errors import DslError
from fenolite.dsl.units import as_nm, as_udeg
from fenolite.model.library import (
    PinAlternate,
    PinTable,
    SymbolDef,
    SymbolGraphic,
    SymbolPin,
    SymbolUnit,
)

_IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")
_TYPES = frozenset(
    (
        "input",
        "output",
        "bidirectional",
        "tri_state",
        "passive",
        "free",
        "unspecified",
        "power_in",
        "power_out",
        "open_collector",
        "open_emitter",
        "no_connect",
    )
)
_SHAPES = frozenset(
    (
        "line",
        "inverted",
        "clock",
        "inverted_clock",
        "input_low",
        "clock_low",
        "output_low",
        "edge_clock_high",
        "non_logic",
    )
)


def _alternates(lib_id: str, number: str, given: object) -> tuple[PinAlternate, ...]:
    if not isinstance(given, (tuple, list)):
        raise DslError(f"symbol {lib_id}: pin {number} alternates must be a tuple of (name, etype[, shape])")
    found: list[PinAlternate] = []
    for item in given:  # pyright: ignore[reportUnknownVariableType]
        parts: tuple[object, ...] = tuple(item) if isinstance(item, (tuple, list)) else ()  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
        name, etype, shape = (*parts, "line")[:3] if len(parts) in (2, 3) else ("", "", "")
        if not isinstance(name, str) or not name or etype not in _TYPES or shape not in _SHAPES:
            raise DslError(
                f"symbol {lib_id}: pin {number} alternate {item!r} must be (name, etype) or "
                "(name, etype, shape)"
            )
        if any(alt.name == name for alt in found):
            raise DslError(f"symbol {lib_id}: pin {number} repeats the alternate {name!r}")
        found.append(PinAlternate(name, etype, shape))  # type: ignore[arg-type]
    return tuple(found)


def _unit_number(lib_id: str, value: object, low: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < low:
        raise DslError(f"symbol {lib_id}: unit {value!r} must be an integer of at least {low}")
    return value


class DerivedSymbol:
    """A symbol derived from a base (``Symbol.derive``): the base's drawing and pins, its own properties.
    ``definition`` is the derived ``SymbolDef`` as KiCad writes it (``extends`` set, no pins)."""

    def __init__(self, base: Symbol, definition: SymbolDef) -> None:
        self.base = base
        self.library, self.name = definition.library, definition.name
        self._definition = definition

    @property
    def lib_id(self) -> str:
        return f"{self.library}:{self.name}"

    @property
    def definition(self) -> SymbolDef:
        return self._definition


class Symbol:
    """Author a symbol. Pins use exact DSL lengths and KiCad's 0/90/180/270-degree rotations; a pin belongs
    to unit 1 unless it names another (0 is common to every unit)."""

    def __init__(
        self,
        library: str,
        name: str,
        *,
        reference: str,
        value: str = "",
        footprint: str = "",
        description: str = "",
    ) -> None:
        for label, text in (("library", library), ("symbol name", name)):
            if not isinstance(text, str) or not _IDENT.fullmatch(text):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise DslError(f"unsafe {label} {text!r}")
        if (
            not isinstance(reference, str)  # pyright: ignore[reportUnnecessaryIsInstance]
            or not reference
            or not isinstance(value, str)  # pyright: ignore[reportUnnecessaryIsInstance]
            or not isinstance(footprint, str)  # pyright: ignore[reportUnnecessaryIsInstance]
            or not isinstance(description, str)  # pyright: ignore[reportUnnecessaryIsInstance]
        ):
            raise DslError(
                "symbol reference, value, footprint and description must be text; reference is non-empty"
            )
        self.library, self.name = library, name
        self.reference, self.value, self.footprint, self.description = (
            reference,
            value,
            footprint,
            description,
        )
        self._pins: list[SymbolPin] = []
        self._graphics: list[SymbolGraphic] = []
        self._units: dict[int, str] = {}
        self._generated: tuple[SymbolDef, tuple[SymbolDef, ...], tuple[Issue, ...]] | None = None

    @classmethod
    def from_pins(
        cls, table: PinTable, *, library: str, footprint: str = "", fp_filters: Sequence[str] = ()
    ) -> Symbol:
        """The symbol generated from a parsed pin table (``fenolite.catalog.pins.read_pins``) by
        ``fenolite.catalog.generate.symbol.generate_symbol``. It is finished: ``pin``, ``unit`` and
        ``graphic`` raise ``DslError``, since a generated symbol is changed in its table. ``variants`` holds
        the table's derived symbols and ``issues`` the generator's findings."""
        from fenolite.catalog.generate.symbol import generate_symbol

        if not isinstance(table, PinTable):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"Symbol.from_pins() takes a PinTable (read_pins), not {table!r}")
        if not isinstance(footprint, str) or isinstance(fp_filters, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError("Symbol.from_pins(): footprint is text and fp_filters a sequence of text")
        made = generate_symbol(table, library=library, footprint=footprint, fp_filters=tuple(fp_filters))
        base = made[0]
        symbol = cls(
            library,
            table.name,
            reference=base.reference,
            value=base.value,
            footprint=footprint,
            description=base.description,
        )
        symbol._generated = made
        return symbol

    @property
    def generated(self) -> bool:
        """Whether the symbol comes from a pin table (``from_pins``)."""
        return self._generated is not None

    @property
    def issues(self) -> tuple[Issue, ...]:
        """The findings of the generator (``symbol.units-split``, ``symbol.bus-split``,
        ``symbol.bus-gap``)."""
        return self._generated[2] if self._generated is not None else ()

    @property
    def variants(self) -> tuple[DerivedSymbol, ...]:
        """The derived symbols of the pin table's ``[[variant]]`` rows (empty for an authored symbol)."""
        if self._generated is None:
            return ()
        return tuple(DerivedSymbol(self, definition) for definition in self._generated[1])

    def _authored(self, call: str) -> None:
        if self._generated is not None:
            raise DslError(
                f"symbol {self.lib_id} is generated from a pin table: change the table instead of "
                f"calling {call}()"
            )

    def unit(self, number: int, name: str = "") -> None:
        """Declare unit ``number`` (1, 2, …) with an optional ``name``; a pin of an undeclared unit declares
        it unnamed."""
        self._authored("unit")
        number = _unit_number(self.lib_id, number, 1)
        if not isinstance(name, str) or (name and not name.isprintable()):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"symbol {self.lib_id}: unit name must be printable text")
        if number in self._units:
            raise DslError(f"symbol {self.lib_id}: unit {number} is declared twice")
        self._units[number] = name

    def derive(
        self, name: str, *, value: str = "", footprint: str = "", description: str = "", datasheet: str = ""
    ) -> DerivedSymbol:
        """A symbol derived from this one: its drawing and pins, and only its own properties. KiCad resolves
        ``extends`` within one library, so the derived symbol is in this symbol's library."""
        if not isinstance(name, str) or not _IDENT.fullmatch(name) or name == self.name:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"symbol {self.lib_id}: unsafe or repeated derived symbol name {name!r}")
        own: dict[str, str] = {}
        for key, text in (
            ("Value", value),
            ("Footprint", footprint),
            ("Datasheet", datasheet),
            ("Description", description),
        ):
            if not isinstance(text, str):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise DslError(f"symbol {self.lib_id}: derived {key.lower()} must be text")
            if text:
                own[key] = text
        lib_id = f"{self.library}:{name}"
        definition = SymbolDef(
            id=derived_id("sym", "dsl", lib_id),
            native_ids={"dsl": lib_id},
            name=name,
            library=self.library,
            extends=self.name,
            properties=own,
        )
        return DerivedSymbol(self, definition)

    @property
    def lib_id(self) -> str:
        return f"{self.library}:{self.name}"

    def pin(
        self,
        number: str,
        name: str,
        *,
        etype: str = "passive",
        at: tuple[object, object],
        length: object,
        rotation: object = 0,
        shape: str = "line",
        unit: int = 1,
        hidden: bool = False,
        alternates: Sequence[tuple[str, ...]] = (),
    ) -> None:
        self._authored("pin")
        unit = _unit_number(self.lib_id, unit, 0)
        if not isinstance(hidden, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"symbol {self.lib_id}: pin hidden must be true or false")
        if hidden and etype == "power_in":
            raise DslError(
                f"symbol {self.lib_id}: pin {number!r} is a power input and cannot be hidden: a hidden power "
                "input connects by name in one target and not in the other"
            )
        if not isinstance(number, str) or not number or any(p.number == number for p in self._pins):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"symbol {self.lib_id}: pin number {number!r} must be non-empty and unique")
        if not isinstance(name, str) or not name or etype not in _TYPES or shape not in _SHAPES:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"symbol {self.lib_id}: invalid pin name, electrical type or shape")
        x, y = as_nm(at[0], name="pin x"), as_nm(at[1], name="pin y")
        n = as_nm(length, name="pin length")
        angle = as_udeg(rotation, name="pin rotation")
        if n <= 0 or angle not in (0, 90_000_000, 180_000_000, 270_000_000):
            raise DslError(
                "symbol pin length must be positive and rotation must be 0, 90, 180 or 270 degrees"
            )
        alts = _alternates(self.lib_id, number, alternates)
        self._pins.append(SymbolPin(number, name, etype, Point(x, y), shape, angle, n, unit, 1, hidden, alts))  # type: ignore[arg-type]

    def graphic(
        self,
        kind: str,
        *,
        points: tuple[tuple[object, object], ...],
        width: object = "0.254mm",
        filled: bool = False,
        unit: int = 0,
    ) -> None:
        """Add one ordered vector primitive in the symbol's local coordinate frame; ``unit`` 0 (the default)
        draws it in every unit."""
        self._authored("graphic")
        unit = _unit_number(self.lib_id, unit, 0)
        if kind not in ("line", "circle", "rect", "polygon"):
            raise DslError(f"unsupported symbol graphic kind {kind!r}")
        minimum = 3 if kind == "polygon" else 2
        if len(points) < minimum:
            raise DslError(f"symbol {kind} needs at least {minimum} point(s)")
        if not isinstance(filled, bool):  # type: ignore[reportUnnecessaryIsInstance]
            raise DslError("symbol graphic filled must be bool")
        converted = tuple(
            Point(as_nm(x, name="symbol graphic x"), as_nm(y, name="symbol graphic y")) for x, y in points
        )
        if kind == "circle" and (converted[1].y != converted[0].y or converted[1].x <= converted[0].x):
            raise DslError(
                "symbol circle edge must be to the right of its center on the same horizontal axis"
            )
        stroke = as_nm(width, name="symbol graphic width")
        if stroke < 0:
            raise DslError("symbol graphic width cannot be negative")
        self._graphics.append(SymbolGraphic(kind, converted, stroke, filled, unit, 1 if unit else 0))  # type: ignore[arg-type]

    def line(
        self,
        start: tuple[object, object],
        end: tuple[object, object],
        *,
        width: object = "0.254mm",
        unit: int = 0,
    ) -> None:
        self.graphic("line", points=(start, end), width=width, unit=unit)

    def rect(
        self,
        start: tuple[object, object],
        end: tuple[object, object],
        *,
        width: object = "0.254mm",
        filled: bool = False,
        unit: int = 0,
    ) -> None:
        self.graphic("rect", points=(start, end), width=width, filled=filled, unit=unit)

    def circle(
        self,
        center: tuple[object, object],
        edge: tuple[object, object],
        *,
        width: object = "0.254mm",
        filled: bool = False,
        unit: int = 0,
    ) -> None:
        self.graphic("circle", points=(center, edge), width=width, filled=filled, unit=unit)

    def polygon(
        self,
        points: tuple[tuple[object, object], ...],
        *,
        width: object = "0.254mm",
        filled: bool = False,
        unit: int = 0,
    ) -> None:
        self.graphic("polygon", points=points, width=width, filled=filled, unit=unit)

    @property
    def definition(self) -> SymbolDef:
        if self._generated is not None:
            return self._generated[0]
        if not self._pins:
            raise DslError(f"symbol {self.lib_id} must have at least one pin")
        props = {
            "Reference": self.reference,
            "Value": self.value,
            "Footprint": self.footprint,
            "Description": self.description,
        }
        return SymbolDef(
            id=derived_id("sym", "dsl", self.lib_id),
            native_ids={"dsl": self.lib_id},
            name=self.name,
            library=self.library,
            properties=props,
            units=self._unit_rows(),
            pins=tuple(self._pins),
            graphics=tuple(self._graphics),
        )

    def _unit_rows(self) -> tuple[SymbolUnit, ...]:
        numbers = sorted(
            {
                1,
                *self._units,
                *(p.unit for p in self._pins if p.unit),
                *(g.unit for g in self._graphics if g.unit),
            }
        )
        if numbers != list(range(1, numbers[-1] + 1)):
            raise DslError(f"symbol {self.lib_id}: units must be numbered 1 … n without a gap, not {numbers}")
        if not any(p.unit == 1 for p in self._pins) and 1 not in self._units and len(numbers) > 1:
            raise DslError(f"symbol {self.lib_id}: unit 1 has no pin")
        return tuple(SymbolUnit(u, 1, self._units.get(u, "")) for u in numbers)


__all__ = ["DerivedSymbol", "Symbol"]
