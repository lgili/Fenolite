# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The static fenolite.block-item.v0 record of a library block (c0273).

Reading validates canonical data and every digest without importing the item's Python. Stored
parameter text is displayed as written: a rounded range must never be reconstructed as exact data.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, cast

from fenolite.core.errors import FormatError
from fenolite.core.units import format_length
from fenolite.dsl.errors import DslError
from fenolite.dsl.record import (
    REQUIRED,
    SHIPPED_PACKAGE,
    BlockRecord,
    PortRecord,
    RecordedParam,
    RecordedValue,
    Requires,
    StoredBlockRecord,
    check_header,
    digests,
    record_data,
)
from fenolite.dsl.record import (
    SCHEMA as RECORD_SCHEMA,
)
from fenolite.model import canonical

SCHEMA = "fenolite.block-item.v0"
FILE = "block.json"
DEFAULT_FENOLITE = ">=0.7.0"
_KEYS = {"schema", "id", "version", "namespace", "fenolite", "record"}
_PARAM_KEYS = {"name", "type", "unit", "required", "default", "min", "max", "choices", "doc"}
_TYPES = {"any", "bool", "int", "str", "none", "length", "quantity", "range"}
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def _fail(message: str) -> FormatError:
    return FormatError(message, file=FILE)


def _object(value: object, what: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in cast(dict[object, object], value)):
        raise _fail(f"{what} is an object")
    return cast(dict[str, Any], value)


def _strings(value: object, what: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in cast(list[object], value)):
        raise _fail(f"{what} is a list of texts")
    return tuple(cast(list[str], value))


def _text(value: object, what: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value):
        raise _fail(f"{what} is {'a text' if empty else 'a non-empty text'}")
    return value


def _display(value: object, kind: str, what: str) -> RecordedValue | None:
    if value is None:
        return None
    text = _text(value, what, empty=True)
    if kind == "length":
        try:
            text = format_length(int(text))
        except ValueError:
            raise _fail(f"{what} is an integer nanometre text") from None
    return RecordedValue(text)


def _params(value: object) -> tuple[RecordedParam, ...]:
    if not isinstance(value, list):
        raise _fail("record.params is a list")
    found: list[RecordedParam] = []
    for raw in cast(list[object], value):
        table = _object(raw, "record.params entry")
        if set(table) != _PARAM_KEYS:
            raise _fail("a parameter holds name, type, unit, required, default, min, max, choices and doc")
        kind = _text(table["type"], "parameter.type")
        if kind not in _TYPES or type(table["required"]) is not bool:
            raise _fail("a parameter has a recorded type and a boolean required")
        unit = table["unit"]
        if unit is not None and not isinstance(unit, str):
            raise _fail("parameter.unit is a text or null")
        required = table["required"]
        if required and table["default"] is not None:
            raise _fail("a required parameter has no default")
        choices = table["choices"]
        if choices is not None and not isinstance(choices, list):
            raise _fail("parameter.choices is a list or null")
        default = REQUIRED if required else _display(table["default"], kind, "parameter.default")
        found.append(
            RecordedParam(
                name=_text(table["name"], "parameter.name"),
                default=default,
                doc=_text(table["doc"], "parameter.doc", empty=True),
                unit=unit,
                min=_display(table["min"], kind, "parameter.min"),
                max=_display(table["max"], kind, "parameter.max"),
                choices=None
                if choices is None
                else tuple(_display(v, kind, "parameter.choice") for v in cast(list[object], choices)),
                recorded_type=kind,
            )
        )
    if [p.name for p in found] != sorted({p.name for p in found}):
        raise _fail("parameters are sorted by unique names")
    return tuple(found)


def _ports(value: object) -> tuple[PortRecord, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise _fail("record.ports is a list or null")
    found: list[PortRecord] = []
    for raw in cast(list[object], value):
        table = _object(raw, "port")
        if set(table) != {"name", "kind", "direction", "optional", "members", "doc"}:
            raise _fail("a port holds name, kind, direction, optional, members and doc")
        if type(table["optional"]) is not bool:
            raise _fail("port.optional is a boolean")
        found.append(
            PortRecord(
                _text(table["name"], "port.name"),
                _text(table["kind"], "port.kind"),
                _text(table["direction"], "port.direction"),
                table["optional"],
                _strings(table["members"], "port.members"),
                _text(table["doc"], "port.doc", empty=True),
            )
        )
    if [p.name for p in found] != sorted({p.name for p in found}):
        raise _fail("ports are sorted by unique names")
    return tuple(found)


def read_record(value: object) -> StoredBlockRecord:
    table = _object(value, "record")
    expected = set(record_data(BlockRecord("", None, ())))
    if set(table) != expected or table.get("schema") != RECORD_SCHEMA:
        raise _fail(f"record holds exactly the {RECORD_SCHEMA} fields")
    ident = _text(table["id"], "record.id")
    try:
        header = check_header(
            ident,
            SHIPPED_PACKAGE if ident.startswith("Fenolite:") else "library",
            **{
                k: table[k]
                for k in (
                    "id",
                    "version",
                    "summary",
                    "category",
                    "licence",
                    "evidence",
                    "sources",
                    "replaces",
                    "deprecated",
                )
            },
        )
    except DslError as error:
        raise _fail(str(error)) from error
    params = _params(table["params"])
    ports = _ports(table["ports"])
    parts = None if table["parts"] is None else _strings(table["parts"], "record.parts")
    nets = None if table["nets"] is None else _strings(table["nets"], "record.nets")
    blocks = table["blocks"]
    nested: list[tuple[str, str]] | None = None
    if blocks is not None:
        if not isinstance(blocks, list):
            raise _fail("record.blocks is a list or null")
        nested = []
        for raw in cast(list[object], blocks):
            child = _object(raw, "nested block")
            if set(child) != {"name", "block"}:
                raise _fail("a nested block holds name and block")
            nested.append((_text(child["name"], "nested name"), _text(child["block"], "nested id")))
    requires = None
    if table["requires"] is not None:
        needs = _object(table["requires"], "record.requires")
        if set(needs) != {"devices", "lib_ids", "queries"}:
            raise _fail("record.requires holds devices, lib_ids and queries")
        requires = Requires(*(_strings(needs[k], f"requires.{k}") for k in ("devices", "lib_ids", "queries")))
    elaboration = table["elaboration"]
    if elaboration is not None:
        why = _object(elaboration, "record.elaboration")
        if not why or set(why) - {"reason", "error"} or not all(isinstance(v, str) for v in why.values()):
            raise _fail("record.elaboration holds reason or error text")
    record = StoredBlockRecord(
        _text(table["name"], "record.name"),
        header,
        params,
        ports,
        parts,
        nets,
        None if nested is None else tuple(nested),
        requires,
        elaboration,
        data=table,
    )
    given = _object(table["digests"], "record.digests")
    if (
        set(given) != {"record", "definition", "interface"}
        or not all(isinstance(v, str) and _DIGEST.fullmatch(v) for v in given.values())
        or given != digests(record)
    ):
        raise _fail("record.digests do not match the canonical record")
    return record


@dataclass(frozen=True, slots=True)
class BlockItem:
    id: str
    version: str
    namespace: str
    fenolite: str
    record: BlockRecord

    @property
    def digest(self) -> str:
        return digests(self.record)["record"]

    def data(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "id": self.id,
            "version": self.version,
            "namespace": self.namespace,
            "fenolite": self.fenolite,
            "record": record_data(self.record),
        }

    def text(self) -> str:
        return canonical.dumps(self.data())


def from_record(record: BlockRecord, *, fenolite: str = DEFAULT_FENOLITE) -> BlockItem:
    header = record.header
    if header is None:
        raise _fail("a library block has an id and a version")
    return BlockItem(header.id, header.version, header.namespace, fenolite, record)


def read_item(text: str, *, item_id: str | None = None, item_version: str | None = None) -> BlockItem:
    try:
        table = _object(json.loads(text), "block item")
        canonical.dumps(table)  # refuses non-integer numbers and non-JSON values
    except (ValueError, TypeError) as error:
        raise _fail(f"not canonical JSON data: {error}") from error
    if set(table) != _KEYS or table.get("schema") != SCHEMA:
        raise _fail(f"the block item holds exactly the {SCHEMA} fields")
    record = read_record(table["record"])
    item = from_record(record, fenolite=_text(table["fenolite"], "fenolite"))
    if (table["id"], table["version"], table["namespace"]) != (item.id, item.version, item.namespace):
        raise _fail("block item id, version and namespace must equal its record")
    if item_id is not None and (item.id != item_id or item.version != item_version):
        raise _fail("block record id and version must equal item.json")
    return item
