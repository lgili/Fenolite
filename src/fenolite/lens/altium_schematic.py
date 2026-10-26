# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Capture and replay native Altium sheets without rebuilding their presentation (c0164)."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from fenolite.backends.altium.adapter import SheetInput, netlist
from fenolite.backends.altium.adapter.parts import part_groups
from fenolite.backends.altium.read import sch
from fenolite.core.errors import FenoliteError, FormatError, Issue, Severity

FILE_NAME = "altium-schematic-layout.json"
BASELINE_DIR = ".fenolite/altium-generated"
SCHEMA = "fenolite.altium-schematic-layout.v0"
_DIGEST = re.compile(r"[0-9a-f]{64}")
ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "build.altium-layout-conflict": "error",
        "sync.altium-connectivity-changed": "error",
        "sync.altium-unverified": "error",
    }
)


class LayoutConflict(FenoliteError):
    """A native sheet cannot be verified or its saved baseline no longer matches."""

    def __init__(self, code: str, message: str, where: str) -> None:
        super().__init__(message)
        self.issues = (
            Issue(
                code,
                ISSUE_CODES[code],
                message,
                where=where,
                hint="keep the saved layout; resolve the circuit conflict before synchronising or rebuilding",
            ),
        )


@dataclass(frozen=True)
class SavedSheet:
    generated_sha256: str
    data: bytes


def digest(data: bytes) -> str:
    """SHA-256 of a complete native document."""
    return hashlib.sha256(data).hexdigest()


def _name(name: str) -> bool:
    return (
        name.lower().endswith(".schdoc")
        and name not in (".", "..")
        and not any(c in name for c in "/\\:\x00")
        and not name.endswith((" ", "."))
    )


def read_snapshot(text: str) -> dict[str, SavedSheet]:
    """Read a strict, versioned snapshot. File names never identify external paths."""

    def bad(reason: str) -> FormatError:
        return FormatError(reason, file=FILE_NAME)

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        found: dict[str, object] = {}
        for key, value in pairs:
            if key in found:
                raise bad(f"duplicate key {key!r}")
            found[key] = value
        return found

    try:
        raw: object = json.loads(text, object_pairs_hook=unique)
    except (json.JSONDecodeError, RecursionError) as error:
        raise bad(f"invalid JSON: {error}") from error
    if not isinstance(raw, dict):
        raise bad("a layout snapshot is an object")
    root = cast(dict[str, object], raw)
    if set(root) != {"schema", "sheets"} or root["schema"] != SCHEMA:
        raise bad("unknown layout schema or keys")
    if not isinstance(root["sheets"], dict):
        raise bad("sheets is an object")
    sheets = cast(dict[str, object], root["sheets"])
    found: dict[str, SavedSheet] = {}
    names: set[str] = set()
    for name, entry in sheets.items():
        if not _name(name) or name.casefold() in names:
            raise bad(f"unsafe or repeated sheet name {name!r}")
        names.add(name.casefold())
        if not isinstance(entry, dict):
            raise bad(f"{name}: a sheet entry is an object")
        row = cast(dict[str, object], entry)
        if set(row) != {"generated_sha256", "sha256", "data"}:
            raise bad(f"{name}: unknown or missing keys")
        generated, checksum, encoded = row["generated_sha256"], row["sha256"], row["data"]
        if not isinstance(generated, str) or _DIGEST.fullmatch(generated) is None:
            raise bad(f"{name}: invalid baseline SHA-256")
        if not isinstance(checksum, str) or not isinstance(encoded, str):
            raise bad(f"{name}: SHA-256 and data are strings")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise bad(f"{name}: invalid base64") from error
        if digest(data) != checksum:
            raise bad(f"{name}: saved document SHA-256 mismatch")
        found[name] = SavedSheet(generated, data)
    return found


def _signature(files: Mapping[str, bytes]) -> tuple[object, ...]:
    sheets: list[SheetInput] = []
    components: list[tuple[object, ...]] = []
    assignments: list[tuple[object, ...]] = []
    for name, data in sorted(files.items()):
        document = sch.read_schematic(data, file=name)
        if document.sheet is None or any(i.severity in ("error", "warning") for i in document.issues):
            raise LayoutConflict(
                "sync.altium-unverified", "the schematic reader cannot verify this sheet", name
            )
        if document.of_type(sch.UnknownRecord):
            raise LayoutConflict(
                "sync.altium-unverified", "unknown schematic records prevent verification", name
            )
        ids: set[str] = set()
        for component in document.components():
            if not component.unique_id or component.unique_id in ids:
                raise LayoutConflict(
                    "sync.altium-unverified", "missing or duplicate component unit IDs", name
                )
            ids.add(component.unique_id)
            children = document.children_of(component)
            pins = tuple(
                sorted(
                    (p.designator, p.name, p.electrical, p.owner_part)
                    for p in children
                    if isinstance(p, sch.Pin)
                )
            )
            parameters = tuple(
                sorted(
                    (p.record_id, p.name, p.text)
                    for p in children
                    if isinstance(p, (sch.Parameter, sch.Designator))
                )
            )
            components.append(
                (
                    name,
                    component.unique_id,
                    component.current_part,
                    component.lib_reference,
                    component.design_item_id,
                    component.source_library,
                    pins,
                    parameters,
                )
            )
        sheets.append(SheetInput(name, digest(data), document))
        assignments.extend(
            (name, group.unique_ids, group.lib_footprint_ref, group.pin_pads)
            for group in part_groups(document)
        )
    issues: list[Issue] = []
    nets = netlist(sheets, issues=issues)
    if any(i.severity in ("error", "warning") for i in issues):
        raise LayoutConflict("sync.altium-unverified", "the netlist has unresolved findings", FILE_NAME)
    return (
        tuple(sorted(components)),
        tuple(sorted(assignments)),
        tuple(sorted((n.name, n.aliases, n.pins) for n in nets.nets)),
        tuple(sorted(nets.no_connects)),
        tuple(sorted((b.name, b.label, b.members) for b in nets.buses)),
        tuple(sorted((h.type, h.members) for h in nets.harnesses)),
    )


def capture(generated: Mapping[str, bytes], edited: Mapping[str, bytes]) -> str:
    """Capture exact native bytes only after project-wide electrical and identity checks."""
    if not generated or set(generated) != set(edited):
        raise LayoutConflict(
            "sync.altium-unverified", "the complete set of generated sheets is required", FILE_NAME
        )
    if any(not _name(name) for name in generated):
        raise FormatError("unsafe sheet name", file=FILE_NAME)
    if _signature(generated) != _signature(edited):
        raise LayoutConflict(
            "sync.altium-connectivity-changed",
            "component identities, symbols, parameters or connectivity differ from the build",
            FILE_NAME,
        )
    payload = {
        "schema": SCHEMA,
        "sheets": {
            name: {
                "generated_sha256": digest(generated[name]),
                "sha256": digest(data),
                "data": base64.b64encode(data).decode("ascii"),
            }
            for name, data in sorted(edited.items())
        },
    }
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"


def replay(generated: Mapping[str, bytes], text: str) -> dict[str, bytes]:
    """Replay saved sheets byte for byte; additions without saved layout use the normal writer."""
    saved = read_snapshot(text)
    result = dict(generated)
    for name, sheet in saved.items():
        if name not in generated or digest(generated[name]) != sheet.generated_sha256:
            raise LayoutConflict(
                "build.altium-layout-conflict",
                f"{name}: the generated sheet changed or was removed after layout sync",
                name,
            )
        result[name] = sheet.data
    if saved:
        capture(
            {name: generated[name] for name in saved}, {name: sheet.data for name, sheet in saved.items()}
        )
    return result
