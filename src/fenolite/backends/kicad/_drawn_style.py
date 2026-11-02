# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Versioned private adapters for actual typed drawn effects (c0326).

The public value lives in model.drawn; these compact integer-nm records carry it through the existing
created-entity extension bag. They are not native KiCad syntax or opaque public font storage.
"""

# evidence: none, Fenolite-owned private drawn-style extension records, not native KiCad syntax

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from fenolite.core.coords import Size
from fenolite.core.errors import FormatError
from fenolite.model.base import Entity, ExtBag
from fenolite.model.canonical import to_data
from fenolite.model.drawn import JUSTIFY_WORDS, DrawnFont

FIELD_FONT = "field-font-v1"
FONT = "font-v1"
JUSTIFY = "justify-v1"
SHEET_PROPERTY = "sheet-property-v1"
_FONT_KEYS = frozenset({"size", "thickness", "bold", "italic", "face"})


def style_key(key: str) -> bool:
    return key.startswith(("field-font-", "font-", "justify-"))


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    found: dict[str, object] = {}
    for key, value in pairs:
        if key in found:
            raise ValueError(f"duplicate key {key!r}")
        found[key] = value
    return found


def _fraction(value: str) -> object:
    raise ValueError(f"{value!r} is not a JSON integer")


def _read(text: str, where: str) -> object:
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_float=_fraction, parse_constant=_fraction)
    except ValueError as error:
        raise FormatError(f"invalid drawn style record: {error}", locator=where) from error


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{value!r} is not whole nanometres")
    return value


def _boolean(data: Mapping[str, object], key: str) -> bool | None:
    if key not in data:
        return None
    value = data[key]
    if not isinstance(value, bool):
        raise ValueError(f"{key} is a boolean")
    return value


def font_payload(font: DrawnFont, *, name: str | None = None) -> str:
    data: dict[str, object] = to_data(font)
    if name is not None:
        data = {"name": name, **data}
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def read_font(text: str, *, named: bool = False, where: str = FONT) -> tuple[str | None, DrawnFont]:
    raw = _read(text, where)
    try:
        if not isinstance(raw, dict):
            raise ValueError("a font record is an object")
        data = cast(dict[str, object], raw)
        unknown = data.keys() - (_FONT_KEYS | ({"name"} if named else set()))
        if unknown:
            raise ValueError(f"unknown font keys: {', '.join(sorted(unknown))}")
        name = data.get("name")
        if named and not isinstance(name, str):
            raise ValueError("a field font names its field pose")
        size = None
        if "size" in data:
            value = data["size"]
            if not isinstance(value, dict):
                raise ValueError("font size is an object with exactly w and h")
            pair = cast(dict[str, object], value)
            if set(pair) != {"w", "h"}:
                raise ValueError("font size is an object with exactly w and h")
            size = Size(_integer(pair["w"]), _integer(pair["h"]))
        face = data.get("face")
        if "face" in data and not isinstance(face, str):
            raise ValueError("font face is a name")
        font = DrawnFont(
            size,
            _integer(data["thickness"]) if "thickness" in data else None,
            _boolean(data, "bold"),
            _boolean(data, "italic"),
            face if isinstance(face, str) else None,
        )
        return name if isinstance(name, str) else None, font
    except (TypeError, ValueError) as error:
        raise FormatError(f"invalid drawn font record: {error}", locator=where) from error


def text_ext(font: DrawnFont | None, justify: str | None) -> ExtBag:
    """An empty bag for legacy text; separate versioned records for explicit effects."""
    pairs: list[tuple[str, str]] = []
    if font is not None:
        pairs.append((FONT, font_payload(font)))
    if justify is not None:
        pairs.append((JUSTIFY, json.dumps(_justification(justify, JUSTIFY), ensure_ascii=False)))
    return ExtBag(None, tuple(pairs))


def sheet_property_texts(entity: Entity, namespace: str = "drawn") -> tuple[tuple[str, str], ...]:
    """Closed versioned name/text bindings; poses and fonts retain their existing typed adapter."""
    bag = entity.ext.get(namespace)
    found: list[tuple[str, str]] = []
    names: set[str] = set()
    for key, text in bag.payload if bag is not None else ():
        if not key.startswith("sheet-property-"):
            continue
        where = f"{namespace}.{key}"
        if key != SHEET_PROPERTY:
            raise FormatError("unsupported custom sheet property adapter", locator=where)
        value = _read(text, where)
        if not isinstance(value, dict):
            raise FormatError("custom sheet property record has missing/unknown keys", locator=where)
        data = cast(dict[str, object], value)
        if set(data) != {"name", "text"}:
            raise FormatError("custom sheet property record has missing/unknown keys", locator=where)
        name, content = data["name"], data["text"]
        if (
            not isinstance(name, str)
            or not name
            or not name.isprintable()
            or name in {"Sheetname", "Sheetfile"}
            or name in names
            or not isinstance(content, str)
        ):
            raise FormatError("invalid or repeated custom sheet property text binding", locator=where)
        if "${" in content:
            raise FormatError("custom sheet property text variables are not supported", locator=where)
        names.add(name)
        found.append((name, content))
    return tuple(found)


def _justification(value: object, where: str) -> str:
    if (
        not isinstance(value, str)
        or any(word not in JUSTIFY_WORDS for word in value.split())
        or value != " ".join(value.split())
    ):
        raise FormatError("invalid drawn text justification", locator=where)
    return value


def text_style(entity: Entity, namespace: str = "drawn") -> tuple[DrawnFont | None, str | None]:
    bag = entity.ext.get(namespace)
    found: set[str] = set()
    font, justify = None, None
    for key, text in bag.payload if bag is not None else ():
        if not style_key(key):
            continue
        if key not in {FONT, JUSTIFY} or key in found:
            raise FormatError(f"unsupported or repeated drawn style {key!r}", locator=f"{namespace}.{key}")
        found.add(key)
        if key == FONT:
            _, font = read_font(text, where=f"{namespace}.{key}")
        else:
            value = _read(text, f"{namespace}.{key}")
            justify = _justification(value, f"{namespace}.{key}")
    return font, justify
