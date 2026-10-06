# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Builder for simple project-authored symbol definitions."""

from __future__ import annotations

import re

from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl.errors import DslError
from fenolite.dsl.units import as_nm, as_udeg
from fenolite.model.library import SymbolDef, SymbolGraphic, SymbolPin, SymbolUnit

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


class Symbol:
    """Author a one-unit symbol. Pins use exact DSL lengths and KiCad's 0/90/180/270-degree rotations."""

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
    ) -> None:
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
        self._pins.append(SymbolPin(number, name, etype, Point(x, y), shape, angle, n, 1, 1))  # type: ignore[arg-type]

    def graphic(
        self,
        kind: str,
        *,
        points: tuple[tuple[object, object], ...],
        width: object = "0.254mm",
        filled: bool = False,
    ) -> None:
        """Add one ordered vector primitive in the symbol's local coordinate frame."""
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
        self._graphics.append(SymbolGraphic(kind, converted, stroke, filled))  # type: ignore[arg-type]

    def line(
        self, start: tuple[object, object], end: tuple[object, object], *, width: object = "0.254mm"
    ) -> None:
        self.graphic("line", points=(start, end), width=width)

    def rect(
        self,
        start: tuple[object, object],
        end: tuple[object, object],
        *,
        width: object = "0.254mm",
        filled: bool = False,
    ) -> None:
        self.graphic("rect", points=(start, end), width=width, filled=filled)

    def circle(
        self,
        center: tuple[object, object],
        edge: tuple[object, object],
        *,
        width: object = "0.254mm",
        filled: bool = False,
    ) -> None:
        self.graphic("circle", points=(center, edge), width=width, filled=filled)

    def polygon(
        self,
        points: tuple[tuple[object, object], ...],
        *,
        width: object = "0.254mm",
        filled: bool = False,
    ) -> None:
        self.graphic("polygon", points=points, width=width, filled=filled)

    @property
    def definition(self) -> SymbolDef:
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
            units=(SymbolUnit(1, 1),),
            pins=tuple(self._pins),
            graphics=tuple(self._graphics),
        )


__all__ = ["Symbol"]
