# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact length ranges of package records (change c0260, requirement "Exact length ranges").

A ``LengthRange`` holds integer nanometre bounds, each optional, read from text with a unit: ``"1.27mm"``
(exact), ``"4.80mm..5.00mm"``, ``"1.75mm max"``, ``"0.10mm min"``, or a ``{min, nom, max}`` table. Units are
those of ``fenolite.core.units`` (``mm``, ``um``, ``mil``, ``in`` and the others), parsed exactly: a value
that is not a whole number of nanometres is refused, never rounded. The bounds are the exact intervals of
change c0246 (worst-case arithmetic); the semantics follow c0246 when it lands.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from fenolite.core.errors import FormatError
from fenolite.core.units import Nm, parse_length


@dataclass(frozen=True, slots=True)
class LengthRange:
    """A length known within bounds: ``min <= nom <= max``, each ``None`` when the source gives none."""

    min: Nm | None
    nom: Nm | None
    max: Nm | None

    def __post_init__(self) -> None:
        if self.min is None and self.nom is None and self.max is None:
            raise ValueError("a length range needs at least one bound")
        known = [value for value in (self.min, self.nom, self.max) if value is not None]
        if known != sorted(known):
            raise ValueError(f"bounds out of order: {self.min}, {self.nom}, {self.max}")

    @classmethod
    def exact(cls, value: Nm) -> LengthRange:
        """The degenerate range ``[value, value]`` with nominal ``value``."""
        return cls(value, value, value)

    @property
    def nominal(self) -> Nm | None:
        """``nom`` when given, else ``(min + max) // 2`` (floored to the nanometre), else ``None``."""
        if self.nom is not None:
            return self.nom
        if self.min is not None and self.max is not None:
            return (self.min + self.max) // 2
        return None


def _value(text: str, *, file: str, locator: str) -> Nm:
    try:
        return parse_length(text.strip())
    except ValueError as exc:
        raise FormatError(f"{text!r} is not an exact length: {exc}", file=file, locator=locator) from None


def parse_length_range(value: object, *, file: str = "", locator: str = "") -> LengthRange:
    """The range of a text or a ``{min, nom, max}`` table; ``FormatError`` (``FEN-3004``) naming ``locator``
    for a malformed text, a value that is not whole nanometres or bounds out of order."""
    bounds: tuple[Nm | None, Nm | None, Nm | None]
    if isinstance(value, Mapping):
        table: Mapping[object, object] = value  # pyright: ignore[reportUnknownVariableType]
        unknown = sorted(str(key) for key in table if key not in ("min", "nom", "max"))
        if unknown:
            raise FormatError(f"unknown key {unknown[0]!r} in a length range", file=file, locator=locator)
        parsed: dict[str, Nm] = {}
        for key in ("min", "nom", "max"):
            item = table.get(key)
            if item is None:
                continue
            if not isinstance(item, str):
                raise FormatError(f"{key} must be a length text", file=file, locator=f"{locator}.{key}")
            parsed[key] = _value(item, file=file, locator=f"{locator}.{key}")
        if not parsed:
            raise FormatError("a length range needs min, nom or max", file=file, locator=locator)
        bounds = (parsed.get("min"), parsed.get("nom"), parsed.get("max"))
    elif isinstance(value, str):
        text = value.strip()
        if ".." in text:
            low, _, high = text.partition("..")
            bounds = (
                _value(low, file=file, locator=locator),
                None,
                _value(high, file=file, locator=locator),
            )
        elif text.endswith(" max"):
            bounds = (None, None, _value(text[:-4], file=file, locator=locator))
        elif text.endswith(" min"):
            bounds = (_value(text[:-4], file=file, locator=locator), None, None)
        else:
            exact = _value(text, file=file, locator=locator)
            bounds = (exact, exact, exact)
    else:
        raise FormatError("a length range is a text or a {min, nom, max} table", file=file, locator=locator)
    try:
        return LengthRange(*bounds)
    except ValueError as exc:
        raise FormatError(f"{value!r}: {exc}", file=file, locator=locator) from None


__all__ = ["LengthRange", "parse_length_range"]
