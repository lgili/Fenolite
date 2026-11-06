# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Storages of an Altium PCB document that no model entity holds, through a conversion to KiCad and back
(change c0450; ``pcb-records.md``, "Storages through KiCad").

A conversion to KiCad copies each carried storage of the source document to a board property
``Fenolite.Altium.<storage>``. The property's value is the base64 text of the zlib-compressed bytes of the
length of the ``Header`` stream (32-bit), that stream and the ``Data`` stream. KiCad keeps a board property
on a save (S-2092). The properties go in as verbatim root items. A conversion back reads them from the
board's root slots and writes each storage again (``pcbdoc.PcbDocSpec.kept_storages``).

The component classes of ``Classes6`` travel as ``Classes6.Component``: the records of ``KIND=1`` that are
no super class. Storages that name primitives by index (``PrimitiveGuids``, the saved violations) are not
carried: the round trip renumbers the primitives. Each one that holds a record is counted lost.
"""

from __future__ import annotations

import base64
import re
import struct
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-CONV-STORAGE",))
"""The claim of the carried storages: written back byte for byte, they open in Altium as in the source
(``docs/hypotheses.md``; settled by the kit request of c0450 task 4.2)."""
PREFIX = "Fenolite.Altium."
"""The name prefix of a board property that carries a storage."""
CARRIED: tuple[str, ...] = ("BoardRegions", "CustomMaskShapes", "EmbeddedFonts6", "UnionNames")
"""The storages copied whole."""
CLASSES = "Classes6"
COMPONENT_CLASSES = "Classes6.Component"
"""The carrier of the component classes of ``Classes6``."""
KIND = "altium-storage"
"""The report kind of a storage."""
INDEX_BOUND_REASON = (
    "the storage names primitives by their index, which the round trip renumbers; Altium makes it again"
)
_INDEX_BOUND = re.compile(r"PrimitiveGuids|WaivedViolations|T[A-Za-z]+Violation")


@dataclass(frozen=True, slots=True)
class Storage:
    """One storage: its ``Header`` and ``Data`` streams."""

    header: bytes
    data: bytes


def encode(storage: Storage) -> str:
    """The property value of ``storage``."""
    packed = struct.pack("<I", len(storage.header)) + storage.header + storage.data
    return base64.b64encode(zlib.compress(packed, 9)).decode("ascii")


def decode(value: str) -> Storage | None:
    """The storage of a property value, or ``None`` when the value is not one ``encode`` gives."""
    try:
        packed = zlib.decompress(base64.b64decode(value.encode("ascii"), validate=True))
    except (ValueError, zlib.error):
        return None
    if len(packed) < 4:
        return None
    (length,) = struct.unpack_from("<I", packed)
    if length > len(packed) - 4:
        return None
    return Storage(packed[4 : 4 + length], packed[4 + length :])


def records(data: bytes) -> list[bytes]:
    """The length-prefixed records of a property storage's ``Data`` stream, each with its 32-bit length."""
    found: list[bytes] = []
    at = 0
    while at + 4 <= len(data):
        (length,) = struct.unpack_from("<I", data, at)
        found.append(data[at : at + 4 + length])
        at += 4 + length
    return found


def fields(record: bytes) -> dict[str, str]:
    """The ``|KEY=value`` fields of one property record (upper-case keys)."""
    text = record[4:].rstrip(b"\x00").decode("latin-1")
    found: dict[str, str] = {}
    for part in text.split("|"):
        key, sep, value = part.partition("=")
        if sep:
            found[key.strip().upper()] = value
    return found


def component_classes(data: bytes) -> list[bytes]:
    """The records of ``Classes6`` that are component classes and no super class."""
    return [
        record
        for record in records(data)
        if (f := fields(record)).get("KIND") == "1" and f.get("SUPERCLASS", "FALSE").upper() != "TRUE"
    ]


@dataclass(frozen=True, slots=True)
class Found:
    """The storages of a source document: those carried, by property name, and the index-bound ones that
    hold a record, with their record counts."""

    carried: Mapping[str, Storage]
    index_bound: Mapping[str, int]


def _count(header: bytes) -> int:
    return struct.unpack_from("<I", header)[0] if len(header) >= 4 else 0


def found_in(path: Path) -> Found:
    """The carried and the index-bound storages of the PCB document at ``path``."""
    from fenolite.backends.altium.read.cfb import read_compound

    compound = read_compound(path)
    names = set(compound.storages())
    carried: dict[str, Storage] = {}
    bound: dict[str, int] = {}

    def streams(name: str) -> Storage | None:
        if f"{name}/Header" not in compound or f"{name}/Data" not in compound:
            return None
        return Storage(compound.read(f"{name}/Header"), compound.read(f"{name}/Data"))

    for name in sorted(names):
        storage = streams(name)
        if storage is None:
            continue
        if name in CARRIED and storage.data:
            carried[PREFIX + name] = storage
        elif name == CLASSES:
            kept = component_classes(storage.data)
            if kept:
                carried[PREFIX + COMPONENT_CLASSES] = Storage(struct.pack("<I", len(kept)), b"".join(kept))
        elif _INDEX_BOUND.fullmatch(name) and _count(storage.header):
            bound[name] = _count(storage.header)
    return Found(carried, bound)


def property_text(name: str, storage: Storage) -> str:
    """The root ``(property …)`` item of a carried storage."""
    return f'(property "{name}" "{encode(storage)}")'


def from_properties(properties: Sequence[tuple[str, str]]) -> dict[str, Storage]:
    """The storages that the board properties ``properties`` (name, value) carry, by storage name
    (``Classes6.Component`` for the component classes); a property whose value does not decode is left
    out."""
    found: dict[str, Storage] = {}
    for name, value in properties:
        if not name.startswith(PREFIX):
            continue
        storage = decode(value)
        if storage is not None:
            found[name.removeprefix(PREFIX)] = storage
    return found


__all__ = [
    "CARRIED",
    "EVIDENCE",
    "COMPONENT_CLASSES",
    "INDEX_BOUND_REASON",
    "KIND",
    "PREFIX",
    "Found",
    "Storage",
    "component_classes",
    "decode",
    "encode",
    "fields",
    "found_in",
    "from_properties",
    "property_text",
    "records",
]
