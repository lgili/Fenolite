# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Canonical JSON form of a design.

UTF-8, LF, two-space indent; keys in dataclass field order; default values omitted; integers only;
collections of entities sorted by ``(kind, path | ref | name | number, id)`` unless the field is
marked ``ordered``; mappings sorted by key. ``dumps(loads(dumps(x))) == dumps(x)``.

Reading validates with a type-directed decoder driven by the same annotations the JSON Schemas in
``schemas/`` are generated from, and reports the first violation as :class:`FormatError` with its
JSON pointer.
"""

from __future__ import annotations

import dataclasses
import json
import types
import typing
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Any

from fenolite import __version__
from fenolite.core.errors import FormatError
from fenolite.core.io import atomic_write
from fenolite.model.base import Entity
from fenolite.model.board import Board
from fenolite.model.circuit import Circuit
from fenolite.model.design import SCHEMA_VERSION, Design, DesignHeader
from fenolite.model.findings import Findings
from fenolite.model.manufacturing import Manifest
from fenolite.model.rules import RuleSet

LAYER_FILES: tuple[tuple[str, str, type], ...] = (
    ("meta.json", "header", DesignHeader),
    ("circuit.json", "circuit", Circuit),
    ("board.json", "board", Board),
    ("rules.json", "rules", RuleSet),
    ("manufacturing.json", "manufacturing", Manifest),
    ("findings.json", "findings", Findings),
)


# ----------------------------------------------------------------------------------------- writing


def _sort_key(entity: Entity) -> tuple[str, str, str]:
    label = ""
    for attr in ("path", "ref", "name", "number"):
        value = getattr(entity, attr, "")
        if isinstance(value, str) and value:
            label = value
            break
    return (type(entity).__name__, label, entity.id)


def _is_default(f: dataclasses.Field[Any], value: Any) -> bool:
    if f.default is not dataclasses.MISSING:
        return bool(value == f.default)
    if f.default_factory is not dataclasses.MISSING:
        return bool(value == f.default_factory())
    return False


def to_data(value: Any, *, ordered: bool = True) -> Any:
    """The canonical plain-JSON structure of ``value``."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        raise TypeError("floats are not allowed in the model; use integer nm or µdeg")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        out: dict[str, Any] = {}
        for f in dataclasses.fields(value):
            item = getattr(value, f.name)
            if not _is_default(f, item):
                out[f.name] = to_data(item, ordered=bool(f.metadata.get("ordered", False)))
        return out
    if isinstance(value, dict):
        return {str(k): to_data(value[k]) for k in sorted(value)}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    if isinstance(value, (tuple, list)):
        items: list[Any] = list(value)  # pyright: ignore[reportUnknownArgumentType]
        if not ordered and items and all(isinstance(i, Entity) for i in items):
            items = sorted(items, key=_sort_key)
        return [to_data(i) for i in items]
    raise TypeError(f"cannot serialise {type(value).__name__}")


def dumps(value: Any) -> str:
    """Canonical JSON text of a dataclass (a layer, an entity or a value object)."""
    return json.dumps(to_data(value), indent=2, ensure_ascii=False) + "\n"


def dump_texts(design: Design) -> dict[str, str]:
    """The six layer files of ``design`` as texts, by file name (what ``dump_dir`` writes)."""
    header = dataclasses.replace(design.header, schema_version=SCHEMA_VERSION, fenolite_version=__version__)
    parts: dict[str, Any] = {
        "header": header,
        "circuit": design.circuit,
        "board": design.board or Board(id=_placeholder_id("brd", design)),
        "rules": design.rules or RuleSet(id=_placeholder_id("rst", design)),
        "manufacturing": design.manufacturing or Manifest(id=_placeholder_id("mfn", design)),
        "findings": design.findings,
    }
    return {file_name: dumps(parts[attr]) for file_name, attr, _cls in LAYER_FILES}


def dump_dir(design: Design, path: str | Path) -> list[Path]:
    """Write the six layer files of ``design`` under ``path``; return the paths written."""
    root = Path(path)
    written: list[Path] = []
    for file_name, text in dump_texts(design).items():
        target = root / file_name
        atomic_write(target, text.encode("utf-8"), backup=False)
        written.append(target)
    return written


def _placeholder_id(prefix: str, design: Design) -> str:
    from fenolite.core.ids import derived_id

    return derived_id(prefix, "fenolite", f"{design.id}:{prefix}")


# ----------------------------------------------------------------------------------------- reading


def _pointer(base: str, key: str | int) -> str:
    return f"{base}/{str(key).replace('~', '~0').replace('/', '~1')}"


@cache
def _hints(cls: type) -> dict[str, Any]:
    return typing.get_type_hints(cls)


def _fail(message: str, pointer: str, file: str) -> FormatError:
    return FormatError(message, file=file, locator=pointer or "/")


def decode(tp: Any, data: Any, pointer: str = "", file: str = "") -> Any:
    """Build a value of type ``tp`` from plain JSON ``data``, validating as it goes."""
    origin = typing.get_origin(tp)
    args = typing.get_args(tp)
    if tp is Any:
        return data
    if tp is type(None):
        if data is not None:
            raise _fail("expected null", pointer, file)
        return None
    if tp is bool:
        if not isinstance(data, bool):
            raise _fail("expected a boolean", pointer, file)
        return data
    if tp is int:
        if isinstance(data, bool) or not isinstance(data, int):
            raise _fail("expected an integer", pointer, file)
        return data
    if tp is str:
        if not isinstance(data, str):
            raise _fail("expected a string", pointer, file)
        return data
    if origin is typing.Literal:
        if data not in args:
            raise _fail(f"expected one of {list(args)!r}", pointer, file)
        return data
    if origin in (typing.Union, types.UnionType):
        if data is None and type(None) in args:
            return None
        errors: list[FormatError] = []
        for option in (a for a in args if a is not type(None)):
            try:
                return decode(option, data, pointer, file)
            except FormatError as exc:
                errors.append(exc)
        raise errors[0] if errors else _fail("no matching type", pointer, file)
    if origin is tuple or origin is list:
        if not isinstance(data, list):
            raise _fail("expected an array", pointer, file)
        items: list[Any] = data  # pyright: ignore[reportUnknownVariableType]
        item_type = args[0]
        decoded = [decode(item_type, item, _pointer(pointer, i), file) for i, item in enumerate(items)]
        return tuple(decoded) if origin is tuple else decoded
    if origin is dict:
        if not isinstance(data, dict):
            raise _fail("expected an object", pointer, file)
        mapping: dict[Any, Any] = data  # pyright: ignore[reportUnknownVariableType]
        return {str(k): decode(args[1], v, _pointer(pointer, str(k)), file) for k, v in mapping.items()}
    if isinstance(tp, type) and issubclass(tp, Enum):
        try:
            return tp(data)
        except ValueError as exc:
            raise _fail(f"expected one of {[m.value for m in tp]!r}", pointer, file) from exc
    if isinstance(tp, type) and dataclasses.is_dataclass(tp):
        return _decode_dataclass(tp, data, pointer, file)
    raise TypeError(f"unsupported annotation {tp!r}")


def _decode_dataclass(cls: type, data: Any, pointer: str, file: str) -> Any:
    if not isinstance(data, dict):
        raise _fail(f"expected an object ({cls.__name__})", pointer, file)
    obj: dict[str, Any] = data  # pyright: ignore[reportUnknownVariableType]
    fields = {f.name: f for f in dataclasses.fields(cls)}
    unknown = sorted(set(obj) - set(fields))
    if unknown:
        raise _fail(f"unexpected property {unknown[0]!r}", _pointer(pointer, unknown[0]), file)
    hints = _hints(cls)
    kwargs: dict[str, Any] = {}
    for name, f in fields.items():
        if name in obj:
            kwargs[name] = decode(hints[name], obj[name], _pointer(pointer, name), file)
        elif f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
            raise _fail(f"missing required property {name!r}", pointer, file)
    try:
        return cls(**kwargs)
    except (TypeError, ValueError) as exc:
        raise _fail(str(exc), pointer, file) from exc


def loads(text: str, cls: type, *, file: str = "") -> Any:
    """Parse canonical JSON text into an instance of ``cls`` (validated)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FormatError(f"invalid JSON: {exc.msg}", file=file, offset=exc.pos) from exc
    return decode(cls, data, "", file)


def load_dir(path: str | Path) -> Design:
    """Read the six layer files written by :func:`dump_dir`."""
    root = Path(path)
    parts: dict[str, Any] = {}
    for file_name, attr, cls in LAYER_FILES:
        target = root / file_name
        if not target.is_file():
            raise FormatError("missing layer file", file=str(target))
        parts[attr] = loads(target.read_text(encoding="utf-8"), cls, file=str(target))
    header: DesignHeader = parts["header"]
    if header.schema_version != SCHEMA_VERSION:
        raise FormatError(
            f"schema_version {header.schema_version!r} is not supported (expected {SCHEMA_VERSION!r})",
            file=str(root / "meta.json"),
            locator="/schema_version",
        )
    return Design(**parts)


__all__ = ["LAYER_FILES", "decode", "dump_dir", "dump_texts", "dumps", "load_dir", "loads", "to_data"]
