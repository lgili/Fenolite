# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An exact JSON codec for KiCad project files: key order kept, numbers kept as their text.

Facts and Fenolite choices: ``docs/formats/kicad/project.md``. Parsing goes through the standard
``json`` module with hooks, so no float is ever created: numbers become ``JsonNumber`` with their
original spelling, and ``NaN``, ``Infinity`` and duplicate keys are refused with a JSON pointer.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, cast

from fenolite.core.errors import FormatError

_NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")


@dataclass(frozen=True, slots=True)
class JsonNumber:
    """A JSON number as written; ``text`` matches the JSON number grammar."""

    text: str

    def __post_init__(self) -> None:
        if not _NUMBER.fullmatch(self.text):
            raise ValueError(f"{self.text!r} is not a JSON number")


JsonObject = dict[str, Any]
"""A JSON object: keys in file order; values are ``JsonObject``, lists, ``str``, ``JsonNumber``,
``bool`` or ``None`` (``JsonValue``)."""
JsonValue = JsonObject | list[Any] | str | JsonNumber | bool | None


class _Duplicate:
    """Marker of an object that repeated a key; replaced by an error after parsing."""

    def __init__(self, key: str) -> None:
        self.key = key


class _Constant:
    """Marker of ``NaN``, ``Infinity`` or ``-Infinity``."""

    def __init__(self, name: str) -> None:
        self.name = name


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            out[key] = _Duplicate(key)
            continue
        out[key] = value
    return out


def _escape(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


def _check(value: Any, pointer: str, file: str) -> None:
    if isinstance(value, _Duplicate):
        raise FormatError(f"duplicate key {value.key!r}", file=file, locator=pointer)
    if isinstance(value, _Constant):
        raise FormatError(f"{value.name} is not a JSON number", file=file, locator=pointer)
    if isinstance(value, dict):
        for key, item in cast(dict[str, Any], value).items():
            _check(item, f"{pointer}/{_escape(key)}", file)
    elif isinstance(value, list):
        for index, item in enumerate(cast(list[Any], value)):
            _check(item, f"{pointer}/{index}", file)


def loads(text: str, *, file: str = "") -> JsonObject:
    """The object of ``text``; ``FormatError`` for syntax errors (with ``offset``), duplicate keys,
    ``NaN``/``Infinity`` and a root that is not an object (with a JSON-pointer ``locator``)."""
    try:
        data = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_int=JsonNumber,
            parse_float=JsonNumber,
            parse_constant=_Constant,
        )
    except json.JSONDecodeError as error:
        offset = len(text[: error.pos].encode("utf-8"))
        raise FormatError(f"not valid JSON: {error.msg}", file=file, offset=offset) from error
    _check(data, "", file)
    if not isinstance(data, dict):
        raise FormatError("the root is not a JSON object", file=file, locator="")
    return cast(JsonObject, data)


def _dump(value: Any, indent: int, out: list[str]) -> None:
    pad = "  " * (indent + 1)
    if isinstance(value, dict):
        items = cast(dict[str, Any], value)
        if not items:
            out.append("{}")
            return
        out.append("{\n")
        for i, (key, item) in enumerate(items.items()):
            out.append(f"{pad}{json.dumps(key, ensure_ascii=False)}: ")
            _dump(item, indent + 1, out)
            out.append(",\n" if i < len(items) - 1 else "\n")
        out.append("  " * indent + "}")
    elif isinstance(value, list):
        elements = cast(list[Any], value)
        if not elements:
            out.append("[]")
            return
        out.append("[\n")
        for i, item in enumerate(elements):
            out.append(pad)
            _dump(item, indent + 1, out)
            out.append(",\n" if i < len(elements) - 1 else "\n")
        out.append("  " * indent + "]")
    elif isinstance(value, JsonNumber):
        out.append(value.text)
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif value is None:
        out.append("null")
    elif isinstance(value, str):
        out.append(json.dumps(value, ensure_ascii=False))
    else:
        raise TypeError(f"{type(value).__name__} is not a project JSON value (floats never are)")


def dumps(data: JsonObject) -> str:
    """Two-space indentation, one member or element per line, ``{}``/``[]`` when empty, final newline."""
    out: list[str] = []
    _dump(data, 0, out)
    return "".join(out) + "\n"


def _unescape(part: str) -> str:
    return part.replace("~1", "/").replace("~0", "~")


def get(data: JsonObject, pointer: str) -> Any:
    """The value at a JSON pointer (``/a/0/b``), or ``None`` when a step is missing."""
    current: Any = data
    for raw in pointer.split("/")[1:] if pointer else ():
        part = _unescape(raw)
        if isinstance(current, dict):
            current = cast(dict[str, Any], current).get(part)
        elif isinstance(current, list) and part.isdigit():
            elements = cast(list[Any], current)
            current = elements[int(part)] if int(part) < len(elements) else None
        else:
            return None
        if current is None:
            return None
    return current


def key_paths(data: JsonObject) -> frozenset[str]:
    """Every key path of ``data``, with list items written ``*`` (``/net_settings/classes/*/name``)."""
    found: set[str] = set()

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, item in cast(dict[str, Any], value).items():
                child = f"{path}/{_escape(key)}"
                found.add(child)
                walk(item, child)
        elif isinstance(value, list):
            for item in cast(list[Any], value):
                found.add(f"{path}/*")
                walk(item, f"{path}/*")

    walk(data, "")
    return frozenset(found)


def structural_equal(a: object, b: object) -> bool:
    """Equal structure, key order included, with numbers compared as text."""
    if isinstance(a, dict) and isinstance(b, dict):
        left, right = cast(dict[str, Any], a), cast(dict[str, Any], b)
        return list(left) == list(right) and all(structural_equal(left[k], right[k]) for k in left)
    if isinstance(a, list) and isinstance(b, list):
        xs, ys = cast(list[Any], a), cast(list[Any], b)
        return len(xs) == len(ys) and all(structural_equal(x, y) for x, y in zip(xs, ys, strict=True))
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, str) or isinstance(b, str):
        return isinstance(a, str) and isinstance(b, str) and a == b
    return a == b


__all__ = ["JsonNumber", "JsonObject", "JsonValue", "dumps", "get", "key_paths", "loads", "structural_equal"]
