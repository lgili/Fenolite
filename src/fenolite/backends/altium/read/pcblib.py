# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reader of Altium PCB libraries (``.PcbLib``) into typed footprints, losing no byte
(``docs/formats/altium/pcb-library.md`` and ``pcb-read.md``; change c0041).

A footprint is found through ``SectionKeys``, then through a root storage whose ``Parameters`` holds the
name as ``PATTERN``, then through a root storage of that name (without case). Its ``Data`` rebuilds from
the name block, its primitives and its trailing bytes (:meth:`LibFootprint.rebuild`).
"""

from __future__ import annotations

import re
import struct
from collections.abc import Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
from types import MappingProxyType

from fenolite.backends.altium.read.cfb import CompoundFile
from fenolite.backends.altium.read.pcb import Issues, PcbReadError, file_header, open_container
from fenolite.backends.altium.read.pcbprims import (
    PadRecord,
    Primitive,
    TextRecord,
    decode_primitives,
)
from fenolite.backends.altium.read.pcbprops import CODEC, PropertyRecord, issue, parse_blocks, parse_mil
from fenolite.backends.altium.read.pcbstack import BoardRecord, read_board
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level

UNIQUE_STORAGE = "UniqueIDPrimitiveInformation"
EVIDENCE = Evidence(
    Level.CORPUS_VERIFIED,
    hypotheses=("H-A-RD-PCB-FRAME", "H-A-RD-PCB-IDENTITY", "H-A-RD-PCB-LENGTHS", "H-A-RD-PCB-CODEC"),
)
"""The evidence of a library read: ``CORPUS-VERIFIED`` since the census of the corpus rows passed
(2026-10-05)."""
_CODES = re.compile(r"\d+(?:,\d+)*")
_ENCODED = re.compile(r"ENCODEDTEXT(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class LibFootprint:
    """One footprint: coordinates relative to its origin, Y up. ``primitives`` keeps the order of
    ``Data`` after the name block, so a primitive's index is its position."""

    name: str
    storage: str
    parameters: PropertyRecord
    description: str | None
    height: Fraction | None
    primitives: tuple[Primitive, ...]
    unique_ids: Mapping[int, str]
    wide_strings: Mapping[int, str]
    streams: Mapping[str, bytes]
    name_block: bytes
    trailing: bytes

    @property
    def pads(self) -> tuple[PadRecord, ...]:
        return tuple(p for p in self.primitives if isinstance(p, PadRecord))

    def rebuild(self) -> bytes:
        """The footprint's ``Data``: the name block, every primitive's bytes and the trailing bytes."""
        return self.name_block + b"".join(p.raw for p in self.primitives) + self.trailing


@dataclass(frozen=True)
class PcbLibrary:
    """A PCB library; ``storages`` holds every stream outside the footprint storages, by storage."""

    header_text: str | None
    version: float | None
    unique_id: str | None
    board: BoardRecord
    names: tuple[str, ...]
    footprints: tuple[LibFootprint, ...]
    storages: Mapping[str, Mapping[str, bytes]]
    issues: tuple[Issue, ...]
    evidence: Evidence

    def footprint(self, name: str) -> LibFootprint | None:
        """The footprint named ``name``, or ``None``."""
        return next((f for f in self.footprints if f.name == name), None)


def _string_block(data: bytes, at: int) -> tuple[str, int] | None:
    """A 32-bit length, one length byte and the characters: the text and the offset after the block."""
    if at + 5 > len(data):
        return None
    (length,) = struct.unpack_from("<I", data, at)
    count = data[at + 4]
    end = at + 4 + length
    if length < 1 or end > len(data) or count + 1 > length:
        return None
    return data[at + 5 : at + 5 + count].decode(CODEC), end


def _names(data: bytes, start: int, found: Issues) -> tuple[str, ...]:
    if start + 4 > len(data):
        found.add(issue("altium.pcb-read.bad-frame", "the footprint count is missing", "Library/Data"))
        return ()
    (count,) = struct.unpack_from("<I", data, start)
    at = start + 4
    out: list[str] = []
    for number in range(count):
        block = _string_block(data, at)
        if block is None:
            found.add(
                issue(
                    "altium.pcb-read.bad-frame",
                    f"footprint name {number} of {count} does not parse",
                    "Library/Data",
                )
            )
            break
        name, at = block
        out.append(name)
    return tuple(out)


def _section_keys(data: bytes, found: Issues) -> dict[str, str]:
    """Full footprint name → storage name, from ``SectionKeys``."""
    out: dict[str, str] = {}
    if len(data) < 4:
        return out
    (count,) = struct.unpack_from("<i", data, 0)
    at = 4
    for _ in range(max(count, 0)):
        if at + 4 > len(data):
            break
        (length,) = struct.unpack_from("<I", data, at)
        raw = data[at + 4 : at + 4 + length]
        block = _string_block(data, at + 4 + length)
        if len(raw) != length or block is None:
            break
        storage, at = block
        out[raw.rstrip(b"\0").decode(CODEC)] = storage
    else:
        return out
    found.add(issue("altium.pcb-read.bad-frame", "a SectionKeys entry does not parse", "SectionKeys"))
    return out


def _encoded(record: PropertyRecord | None) -> dict[int, str]:
    out: dict[int, str] = {}
    for key, value in record.fields if record else ():
        match = _ENCODED.fullmatch(key)
        if match and (not value or _CODES.fullmatch(value)):
            out[int(match.group(1))] = "".join(chr(int(c)) for c in value.split(",") if c)
    return out


def _first_block(compound: CompoundFile, path: str, found: Issues) -> PropertyRecord | None:
    if path not in compound:
        return None
    records, _, problems = parse_blocks(compound.read(path), where=path)
    found.add(*problems)
    return records[0] if records else None


def _footprint(compound: CompoundFile, name: str, storage: str, found: Issues) -> LibFootprint:
    where = f"{storage}/Data"
    data = compound.read(where)
    block = _string_block(data, 0)
    start = 0 if block is None else block[1]
    if block is None:
        found.add(issue("altium.pcb-read.bad-frame", "the footprint name block does not parse", where))
    primitives, trailing, problems = decode_primitives(data, where=where, start=start)
    found.add(*problems)
    header = f"{storage}/Header"
    if header in compound and not trailing:
        raw = compound.read(header)
        if len(raw) == 4 and struct.unpack("<I", raw)[0] != len(primitives):
            found.add(
                issue(
                    "altium.pcb-read.count-mismatch",
                    f"Header says {struct.unpack('<I', raw)[0]} primitives, Data holds {len(primitives)}",
                    header,
                )
            )
    parameters = _first_block(compound, f"{storage}/Parameters", found) or PropertyRecord(b"", ())
    ids: dict[int, str] = {}
    uid_path = f"{storage}/{UNIQUE_STORAGE}/Data"
    if uid_path in compound:
        records, _, problems = parse_blocks(compound.read(uid_path), where=uid_path)
        found.add(*problems)
        for record in records:
            index = record.get("PRIMITIVEINDEX")
            if index is not None and index.isdigit():
                ids[int(index)] = record.text("UNIQUEID")
    wide = _encoded(_first_block(compound, f"{storage}/WideStrings", found))
    primitives = tuple(
        replace(p, text=wide[p.wide_index])
        if isinstance(p, TextRecord) and p.wide_index is not None and p.wide_index in wide
        else p
        for p in primitives
    )
    prefix = compound.node(storage).path + "/"
    streams = {
        path[len(prefix) :]: compound.read(path) for path in compound.streams() if path.startswith(prefix)
    }
    return LibFootprint(
        name=name,
        storage=compound.node(storage).name,
        parameters=parameters,
        description=parameters.get("DESCRIPTION"),
        height=parse_mil(parameters.get("HEIGHT")),
        primitives=primitives,
        unique_ids=MappingProxyType(ids),
        wide_strings=MappingProxyType(wide),
        streams=MappingProxyType(streams),
        name_block=data[:start],
        trailing=trailing,
    )


def read_pcblib(source: bytes | CompoundFile, *, file: str = "", strict: bool = False) -> PcbLibrary:
    """A PCB library. ``source`` is the file's bytes or an open ``CompoundFile``. A source that is no
    compound file, or has no ``Library/Data``, raises ``PcbReadError``; a container error of ``read.cfb``
    is passed on unchanged."""
    compound = open_container(source, file=file)
    found = Issues(file=file, strict=strict)
    found.add(*compound.notes)
    if "Library/Data" not in compound:
        raise PcbReadError("no Library/Data: not a binary PCB library", file=file, locator="Library/Data")
    data = compound.read("Library/Data")
    first = 4 + (struct.unpack_from("<I", data)[0] & 0xFFFFFF) if len(data) >= 4 else len(data)
    records, _, problems = parse_blocks(data[:first], where="Library/Data")
    found.add(*problems)
    if not records:
        raise PcbReadError("Library/Data holds no board record", file=file, locator="Library/Data")
    board, problems = read_board(records[0], where="Library/Data#0")
    found.add(*problems)
    names = _names(data, len(records[0].raw), found)
    keys = _section_keys(compound.read("SectionKeys"), found) if "SectionKeys" in compound else {}
    roots = [n for n in compound.children("") if n.kind == "storage" and f"{n.path}/Data" in compound]
    roots = [n for n in roots if f"{n.path}/Parameters" in compound]
    patterns: dict[str, str] = {}
    for node in roots:
        record = _first_block(compound, f"{node.path}/Parameters", Issues(file=file, strict=False))
        pattern = record.get("PATTERN") if record else None
        if pattern is not None:
            patterns.setdefault(pattern, node.path)
    by_upper = {node.name.upper(): node.path for node in roots}
    used: set[str] = set()
    footprints: list[LibFootprint] = []
    for name in names:
        storage = keys.get(name)
        if storage is None or f"{storage}/Data" not in compound:
            storage = patterns.get(name) or by_upper.get(name.upper())
        if storage is None or f"{storage}/Data" not in compound:
            found.add(
                issue("altium.pcb-read.missing-stream", "a listed footprint has no storage", "Library/Data")
            )
            continue
        used.add(compound.node(storage).path)
        footprints.append(_footprint(compound, name, storage, found))
    for node in roots:
        if node.path not in used:
            found.add(
                issue(
                    "altium.pcb-read.unlisted-footprint",
                    "a root storage with Data and Parameters is not listed in Library/Data",
                    f"{node.path}/Data",
                )
            )
            pattern = _first_block(compound, f"{node.path}/Parameters", Issues(file=file, strict=False))
            name = pattern.get("PATTERN") if pattern else None
            footprints.append(_footprint(compound, name or node.name, node.path, found))
            used.add(node.path)
    storages: dict[str, dict[str, bytes]] = {}
    for path in compound.streams():
        storage, _, stream = path.partition("/") if "/" in path else ("", "", path)
        if storage not in used:
            storages.setdefault(storage, {})[stream] = compound.read(path)
    text: str | None = None
    version: float | None = None
    unique: str | None = None
    if "FileHeader" in compound:
        text, version, unique = file_header(compound.read("FileHeader"))
    return PcbLibrary(
        header_text=text,
        version=version,
        unique_id=unique,
        board=board,
        names=names,
        footprints=tuple(footprints),
        storages=MappingProxyType({k: MappingProxyType(v) for k, v in storages.items()}),
        issues=tuple(found.items),
        evidence=EVIDENCE,
    )


__all__ = ["EVIDENCE", "UNIQUE_STORAGE", "LibFootprint", "PcbLibrary", "read_pcblib"]
