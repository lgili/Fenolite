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

``fenolite sync --to-source`` writes the file from the schematic of a built project, as edited in KiCad:
``extract_symbol_placements`` reads the symbols that carry ``fenolite.path``, and ``write_placements``
prints them (change c0069; ``docs/lens.md``, "sync").
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from decimal import Decimal
from types import MappingProxyType

from fenolite.backends.kicad.schgen import ISSUE_CODES
from fenolite.backends.kicad.schlayout import GRID, MIRRORS, PROVED_FRAMES, ROTATIONS, SymbolPlacement
from fenolite.core.errors import FormatError, Issue
from fenolite.model.design import Design
from fenolite.model.schematic import SchematicSheet

FILE_NAME = "schematic-placements.toml"
KEYS: tuple[str, ...] = ("x", "y", "rotation", "mirror")
INVALID = "build.symbol-placement-invalid"
OFF_GRID = "sync.symbol-off-grid"
PATH_PROPERTY = "fenolite.path"
HEADER = "# Written by fenolite sync --to-source."
_UDEG_PER_DEG = 1_000_000
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


def unit_key(path: str, unit: int) -> str:
    """The table name of a unit: the component path, or ``<path>#<unit>`` above unit 1."""
    return path if unit == 1 else f"{path}#{unit}"


def extract_symbol_placements(
    sheets: Iterable[SchematicSheet], *, design: Design
) -> tuple[Mapping[str, SymbolPlacement], tuple[Issue, ...]]:
    """The placement of every symbol unit of ``sheets`` whose ``fenolite.path`` property is a component
    path of ``design``, by unit key in key order.

    A symbol without that property (a power flag, a symbol drawn in KiCad) gives no entry and no issue. A
    position off the 1.27 mm grid, or a rotation and mirror pair that the schematic writer does not
    produce, gives ``sync.symbol-off-grid`` (warning) and no entry: the file could not hold it.
    """
    paths = {
        component.properties[PATH_PROPERTY]
        for component in design.circuit.components
        if PATH_PROPERTY in component.properties
    }
    found: dict[str, SymbolPlacement] = {}
    issues: list[Issue] = []
    for sheet in sheets:
        for symbol in sheet.symbols:
            path = symbol.properties.get(PATH_PROPERTY)
            if path is None or path not in paths:
                continue
            key = unit_key(path, symbol.unit)
            degrees, rest = divmod(symbol.rotation, _UDEG_PER_DEG)
            x, y = symbol.position.x, symbol.position.y
            on_grid = x % GRID == 0 and y % GRID == 0
            proved = rest == 0 and (degrees, symbol.mirror) in PROVED_FRAMES
            if not (on_grid and proved):
                why = (
                    f"its origin ({_millimetres(x)} mm, {_millimetres(y)} mm) is off the 1.27 mm grid"
                    if not on_grid
                    else f"rotation {degrees} with mirror {symbol.mirror!r} is no frame of the writer"
                )
                issues.append(
                    Issue(
                        OFF_GRID,
                        "warning",
                        f"symbol {key}: {why}, so {FILE_NAME} cannot hold its placement",
                        where=key,
                        hint="move the symbol onto the grid in KiCad and run sync again",
                    )
                )
                continue
            found[key] = SymbolPlacement(x, y, degrees, symbol.mirror)
    return MappingProxyType(dict(sorted(found.items()))), tuple(issues)


def _millimetres(value: int) -> str:
    """``value`` nm as millimetres in the shortest exact decimal form."""
    whole, rest = divmod(abs(value), _NM_PER_MM)
    fraction = str(rest).rjust(6, "0").rstrip("0")
    return f"{'-' if value < 0 else ''}{whole}{'.' + fraction if fraction else ''}"


def write_placements(entries: Mapping[str, SymbolPlacement]) -> str:
    """The text of a ``schematic-placements.toml``: one table per entry in key order, with ``x`` and ``y``
    in millimetres, ``rotation`` when it is not 0 and ``mirror`` when the symbol is mirrored.
    ``read_placements`` of the text gives the entries back."""
    tables: list[str] = []
    for key, entry in sorted(entries.items()):
        lines = [f'["{key}"]', f"x = {_millimetres(entry.x)}", f"y = {_millimetres(entry.y)}"]
        if entry.rotation:
            lines.append(f"rotation = {entry.rotation}")
        if entry.mirror:
            lines.append(f'mirror = "{entry.mirror}"')
        tables.append("\n".join(lines) + "\n")
    return "\n".join([HEADER + "\n", *tables])


__all__ = [
    "FILE_NAME",
    "KEYS",
    "OFF_GRID",
    "extract_symbol_placements",
    "read_placements",
    "unit_key",
    "write_placements",
]
