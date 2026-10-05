# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``placements.toml``: the committed copy of a layout's placements (``docs/lens.md``, "placements.toml").

``fenolite sync --to-source`` writes the file beside the design script and ``fenolite build`` reads it. An
entry is a table ``[part."<component path>"]`` with ``x`` and ``y`` in millimetres in the frame of
``place()``, ``rotation`` in degrees, ``side`` and ``locked``. Values are exact: the text is read with
``Decimal`` numbers and printed from integers, so no float is ever created.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import cast

from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue
from fenolite.core.units import Udeg
from fenolite.model.board import Side

SCHEMA = "fenolite.placements.v0"
FILE_NAME = "placements.toml"
HEADER = "# Written by fenolite sync --to-source."
INVALID = "layout.source-invalid"
KEYS: tuple[str, ...] = ("x", "y", "rotation", "side", "locked")
"""The keys of an entry, in the order they are printed."""
SIDES: tuple[str, ...] = ("top", "bottom")
FULL_TURN = 360_000_000
_SEGMENT = re.compile(r"[A-Za-z0-9_.+-]+")
_MM = 1_000_000
_DEG = 1_000_000


@dataclass(frozen=True, slots=True)
class SourcePlacement:
    """One entry: the position in the written frame, the rotation, the side, and the footprint's lock in
    KiCad, which gives the entry no precedence."""

    at: Point
    rotation: Udeg
    side: Side
    locked: bool


@dataclass(frozen=True)
class PlacementsFile:
    """The valid entries of a placements file, in component-path order, and what was wrong with the rest."""

    entries: Mapping[str, SourcePlacement]
    issues: tuple[Issue, ...] = ()


def is_component_path(path: str) -> bool:
    return bool(path) and all(_SEGMENT.fullmatch(part) for part in path.split("/"))


def table_name(path: str) -> str:
    """The header of the table of ``path``, without its brackets."""
    return f'part."{path}"'


def _scaled(value: object, unit: int) -> int | None:
    """``value`` times ``unit`` when that is a whole number; ``None`` for any other value or type."""
    if isinstance(value, bool) or not isinstance(value, int | Decimal):
        return None
    scaled = Decimal(value) * unit
    if not scaled.is_finite() or scaled != scaled.to_integral_value():
        return None
    return int(scaled)


def _entry(
    table: Mapping[str, object], origin: Point
) -> tuple[SourcePlacement | None, list[tuple[str, str]]]:
    """The entry of one table, or ``None`` with ``(key, what is wrong)`` for each fault."""
    faults: list[tuple[str, str]] = []
    for key in table:
        if key not in KEYS:
            faults.append((key, f"unknown key; an entry holds {', '.join(KEYS)}"))
    lengths: dict[str, int] = {}
    for key in ("x", "y"):
        if key not in table:
            faults.append((key, "is missing"))
            continue
        nm = _scaled(table[key], _MM)
        if nm is None:
            faults.append((key, f"{table[key]!r} is not a whole number of nanometres, in millimetres"))
        else:
            lengths[key] = nm
    rotation = _scaled(table.get("rotation", 0), _DEG)
    if rotation is None or not 0 <= rotation < FULL_TURN:
        faults.append(
            ("rotation", f"{table.get('rotation')!r} is not a whole number of microdegrees in [0, 360)")
        )
    side = table.get("side", "top")
    if side not in SIDES:
        faults.append(("side", f"{side!r} is not 'top' or 'bottom'"))
    locked = table.get("locked", False)
    if not isinstance(locked, bool):
        faults.append(("locked", f"{locked!r} is not true or false"))
    if faults:
        return None, faults
    assert rotation is not None and isinstance(locked, bool)
    at = Point(origin.x + lengths["x"], origin.y + lengths["y"])
    return SourcePlacement(at, rotation, cast(Side, side), locked), []


def read_placements(text: str, *, origin: Point, file: str = "") -> PlacementsFile:
    """The entries of a placements file. ``origin`` is the written position of the point ``place(0, 0)``.

    A text that is not TOML, or whose ``schema`` is not ``SCHEMA``, raises ``FormatError`` naming ``file``.
    A table or a key that is wrong gives ``layout.source-invalid`` and leaves its entry out.
    """
    try:
        data = tomllib.loads(text, parse_float=Decimal)
    except tomllib.TOMLDecodeError as error:
        raise FormatError(f"not TOML: {error}", file=file) from error
    if data.get("schema") != SCHEMA:
        raise FormatError(
            f"schema is {data.get('schema')!r}, not {SCHEMA!r}; fenolite sync --to-source writes the file",
            file=file,
        )
    issues: list[Issue] = []

    def invalid(where: str, message: str) -> None:
        issues.append(Issue(INVALID, "error", f"{file or FILE_NAME}: {message}", where=where))

    for key in data:
        if key not in ("schema", "part"):
            invalid(key, f"unknown key {key!r}; the file holds schema and the part tables")
    parts = data.get("part", {})
    entries: dict[str, SourcePlacement] = {}
    if not isinstance(parts, dict):
        invalid("part", "part is not a table of component paths")
        parts = {}
    for path, table in cast(dict[str, object], parts).items():
        name = table_name(path)
        if not is_component_path(path):
            invalid(name, f"[{name}]: {path!r} is not a component path")
            continue
        if not isinstance(table, dict):
            invalid(name, f"[{name}] is not a table")
            continue
        entry, faults = _entry(cast(dict[str, object], table), origin)
        for key, what in faults:
            invalid(f"{name}.{key}", f"[{name}] {key}: {what}")
        if entry is not None:
            entries[path] = entry
    return PlacementsFile(MappingProxyType(dict(sorted(entries.items()))), tuple(issues))


def decimal_text(value: int, unit: int) -> str:
    """``value / unit`` in its shortest exact decimal form: ``30``, ``12.7``, ``-0.000001``."""
    whole, rest = divmod(abs(value), unit)
    digits = len(str(unit)) - 1
    fraction = str(rest).rjust(digits, "0").rstrip("0")
    return f"{'-' if value < 0 else ''}{whole}{'.' + fraction if fraction else ''}"


def table_text(path: str, entry: SourcePlacement, *, origin: Point) -> str:
    """The table of one entry, as ``write_placements`` prints it."""
    return (
        f"[{table_name(path)}]\n"
        f"x = {decimal_text(entry.at.x - origin.x, _MM)}\n"
        f"y = {decimal_text(entry.at.y - origin.y, _MM)}\n"
        f"rotation = {decimal_text(entry.rotation, _DEG)}\n"
        f'side = "{entry.side}"\n'
        f"locked = {'true' if entry.locked else 'false'}\n"
    )


def write_placements(entries: Mapping[str, SourcePlacement], *, origin: Point) -> str:
    """The text of a placements file: the comment, the schema, then one table per entry in component-path
    order. Nothing depends on the clock or the machine, and ``read_placements`` gives the entries back."""
    for path in entries:
        if not is_component_path(path):
            raise ValueError(f"{path!r} is not a component path")
    tables = [table_text(path, entry, origin=origin) for path, entry in sorted(entries.items())]
    return "\n".join([f'{HEADER}\nschema = "{SCHEMA}"\n', *tables])


__all__ = [
    "FILE_NAME",
    "SCHEMA",
    "PlacementsFile",
    "SourcePlacement",
    "decimal_text",
    "is_component_path",
    "read_placements",
    "table_name",
    "table_text",
    "write_placements",
]
