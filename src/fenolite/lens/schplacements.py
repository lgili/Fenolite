# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``schematic-placements.toml``: symbol positions of a generated schematic that the user fixes
(``docs/schematic.md``, "Placements file"; capability ``design-dsl``, "Schematic placements file").

One table per unit, keyed by the component path, or by ``<path>#<unit>`` for a unit above 1::

    ["R1"]
    x = 25.4
    y = 50.8
    rotation = 90
    mirror = "y"

``x`` and ``y`` are the symbol origin in millimetres, multiples of 1.27. Numbers are read as decimals, so
no float is created.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType

from fenolite.backends.kicad.schgen import ISSUE_CODES
from fenolite.backends.kicad.schlayout import GRID, MIRRORS, PROVED_FRAMES, ROTATIONS, SymbolPlacement
from fenolite.core.errors import FormatError, Issue

FILE_NAME = "schematic-placements.toml"
KEYS: tuple[str, ...] = ("x", "y", "rotation", "mirror")
INVALID = "build.symbol-placement-invalid"
_NM_PER_MM = 1_000_000


def _invalid(table: str, key: str, why: str, file: str) -> Issue:
    return Issue(
        INVALID,
        ISSUE_CODES[INVALID],
        f"{file or FILE_NAME}: [{table}] {key}: {why}",
        where=table,
        hint="x and y are millimetres on the 1.27 mm grid; rotation is 0, 90, 180 or 270; mirror is x or y",
    )


def _length(value: object) -> int | None:
    """Millimetres as whole nanometres on the grid, or ``None``."""
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        return None
    scaled = Decimal(value) * _NM_PER_MM
    if scaled != scaled.to_integral_value():
        return None
    nm = int(scaled)
    return nm if nm % GRID == 0 else None


def read_placements(
    text: str, *, file: str = "", issues: list[Issue] | None = None
) -> Mapping[str, SymbolPlacement]:
    """The placements of a ``schematic-placements.toml`` text, by unit key.

    A table with a value off the grid, an unknown key, a rotation or mirror outside the allowed values,
    or a (rotation, mirror) pair that was not proved against KiCad gives one
    ``build.symbol-placement-invalid`` error in ``issues`` and no placement. Text that is not TOML raises
    ``FormatError``.
    """
    sink = issues if issues is not None else []
    try:
        data = tomllib.loads(text, parse_float=Decimal)
    except tomllib.TOMLDecodeError as error:
        raise FormatError(f"not valid TOML: {error}", file=file or FILE_NAME) from error
    found: dict[str, SymbolPlacement] = {}
    for table, raw in data.items():
        if not isinstance(raw, dict):
            sink.append(_invalid(table, table, "a placement is a table of x, y, rotation and mirror", file))
            continue
        values: dict[str, object] = dict(raw)  # pyright: ignore[reportUnknownArgumentType]
        before = len(sink)
        for key in sorted(set(values) - set(KEYS)):
            sink.append(_invalid(table, key, "unknown key", file))
        if ("x" in values) != ("y" in values):
            sink.append(_invalid(table, "x" if "y" in values else "y", "x and y are given together", file))
        x = y = 0
        for key in ("x", "y"):
            if key not in values:
                if "x" not in values and "y" not in values and key == "x":
                    sink.append(_invalid(table, "x", "a placement needs x and y", file))
                continue
            length = _length(values[key])
            if length is None:
                sink.append(_invalid(table, key, f"{values[key]} mm is not a multiple of 1.27 mm", file))
            elif key == "x":
                x = length
            else:
                y = length
        rotation = values.get("rotation", 0)
        if isinstance(rotation, bool) or rotation not in ROTATIONS:
            sink.append(_invalid(table, "rotation", f"{rotation!r} is not 0, 90, 180 or 270", file))
            rotation = 0
        mirror = values.get("mirror", "")
        if not isinstance(mirror, str) or mirror not in MIRRORS:
            sink.append(_invalid(table, "mirror", f"{mirror!r} is not 'x' or 'y'", file))
            mirror = ""
        assert isinstance(rotation, int)
        if len(sink) == before and (rotation, mirror) not in PROVED_FRAMES:
            sink.append(
                _invalid(
                    table,
                    "rotation",
                    f"rotation {rotation} with mirror {mirror!r} was not checked against KiCad",
                    file,
                )
            )
        if len(sink) == before:
            found[table] = SymbolPlacement(x, y, rotation, mirror)
    return MappingProxyType(found)


__all__ = ["FILE_NAME", "KEYS", "read_placements"]
