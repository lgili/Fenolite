# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The working state of an edit session (change c0241): every stream of the document's compound file, the
raw records of each storage an operation edits, and the multiset of records each operation declared as
removed and added. ``State.data()`` assembles the compound file again; ``State.document()`` reads it."""

# evidence: see edit.session

from __future__ import annotations

import struct
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field

from fenolite.backends.altium.cfb import Entry, Storage, write_compound
from fenolite.backends.altium.read.cfb import CompoundFile, open_compound
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc, wide_table
from fenolite.backends.altium.read.pcbprims import Primitive, decode_primitives
from fenolite.backends.altium.read.pcbprops import PropertyRecord, parse_blocks

PROPERTY_STORAGES = {
    "Board6": 0,
    "Nets6": 0,
    "Components6": 0,
    "Classes6": 0,
    "Rules6": 2,
    "Polygons6": 0,
    "UniqueIDPrimitiveInformation": 0,
}
"""The property storages an operation may edit and the lead bytes of their records."""
PRIMITIVE_STORAGES = (
    "Pads6",
    "Vias6",
    "Tracks6",
    "Arcs6",
    "Texts6",
    "Fills6",
    "Regions6",
    "ShapeBasedRegions6",
    "ComponentBodies6",
    "ShapeBasedComponentBodies6",
)
SHAPE_BASED = frozenset({"ShapeBasedRegions6", "ShapeBasedComponentBodies6"})
WIDE = "WideStrings6"


@dataclass
class State:
    """Mutable records of one document. ``streams`` maps each stream path to its bytes as read;
    ``records`` holds, per storage that was split, its records and the bytes after them."""

    file: str
    tree: tuple[Entry, ...]
    streams: dict[str, bytes]
    records: dict[str, tuple[list[bytes], bytes]] = field(default_factory=lambda: {})
    removed: Counter[tuple[str, bytes]] = field(default_factory=lambda: Counter[tuple[str, bytes]]())
    added: Counter[tuple[str, bytes]] = field(default_factory=lambda: Counter[tuple[str, bytes]]())
    touched: set[str] = field(default_factory=lambda: set[str]())
    _names: dict[str, str] = field(default_factory=lambda: {})

    @classmethod
    def of(cls, data: bytes, *, file: str = "") -> State:
        compound = open_compound(data, file=file)
        streams = {path: compound.read(path) for path in compound.streams()}
        names = {path.split("/", 1)[0].upper(): path.split("/", 1)[0] for path in streams if "/" in path}
        return cls(file=file, tree=compound.tree(), streams=streams, _names=names)

    # --- records ---------------------------------------------------------------------------------------

    def name(self, storage: str) -> str:
        """The storage's name as the file spells it (names are matched without case)."""
        return self._names.get(storage.upper(), storage)

    def has(self, storage: str) -> bool:
        return f"{self.name(storage)}/Data" in self.streams

    def split(self, storage: str) -> tuple[list[bytes], bytes]:
        """The records of ``storage`` (a property, primitive or wide-string storage) and its tail."""
        name = self.name(storage)
        if name in self.records:
            return self.records[name]
        data = self.streams.get(f"{name}/Data", b"")
        if storage in PROPERTY_STORAGES:
            found, trailing, _ = parse_blocks(data, lead=PROPERTY_STORAGES[storage], where=name)
            raws = [record.raw for record in found]
        elif storage == WIDE:
            table = wide_table(data)
            raws, trailing = (list(table[1]), b"") if table is not None else ([], data)
        else:
            items, trailing, _ = decode_primitives(data, where=name, shape_based=storage in SHAPE_BASED)
            raws = [item.raw for item in items]
        self.records[name] = (raws, trailing)
        return self.records[name]

    def get(self, storage: str) -> list[bytes]:
        return self.split(storage)[0]

    def typed(self, storage: str) -> list[Primitive]:
        """The current primitives of ``storage``, typed by ``read.pcbprims``, one per record."""
        shape = storage in SHAPE_BASED
        out: list[Primitive] = []
        for raw in self.get(storage):
            items, _, _ = decode_primitives(raw, where=storage, shape_based=shape)
            out.append(items[0])
        return out

    def properties(self, storage: str) -> list[PropertyRecord]:
        """The current property records of ``storage``."""
        lead = PROPERTY_STORAGES[storage]
        return [parse_blocks(raw, lead=lead, where=storage)[0][0] for raw in self.get(storage)]

    def wide(self) -> dict[int, tuple[int, str]]:
        """Each wide-string index → its record's position and its text."""
        out: dict[int, tuple[int, str]] = {}
        for position, raw in enumerate(self.get(WIDE)):
            table = wide_table(raw)
            if table is not None:
                for index, text in table[0].items():
                    out[index] = (position, text)
        return out

    def replace(self, storage: str, index: int, raw: bytes) -> None:
        raws = self.get(storage)
        old = raws[index]
        if old == raw:
            return
        self._declare(storage, removed=old, added=raw)
        raws[index] = raw

    def append(self, storage: str, raw: bytes) -> int:
        raws = self.get(storage)
        raws.append(raw)
        self._declare(storage, added=raw)
        return len(raws) - 1

    def remove(self, storage: str, indices: set[int]) -> None:
        raws = self.get(storage)
        for index in sorted(indices, reverse=True):
            self._declare(storage, removed=raws[index])
            del raws[index]

    def _declare(self, storage: str, *, removed: bytes | None = None, added: bytes | None = None) -> None:
        name = self.name(storage)
        self.touched.add(name)
        for counter, raw in ((self.removed, removed), (self.added, added)):
            if raw is None:
                continue
            other = self.added if counter is self.removed else self.removed
            key = (name, raw)
            if other[key]:
                other[key] -= 1
                if not other[key]:
                    del other[key]
            else:
                counter[key] += 1

    # --- assembly --------------------------------------------------------------------------------------

    def flush(self) -> dict[str, bytes]:
        """``streams`` with every split storage joined again and its ``Header`` count set where the stream
        holds one."""
        out = dict(self.streams)
        for name, (raws, trailing) in self.records.items():
            if name not in self.touched:
                continue
            out[f"{name}/Data"] = b"".join(raws) + trailing
            header = f"{name}/Header"
            if header in out and len(out[header]) == 4:
                out[header] = struct.pack("<I", len(raws))
        return out

    def data(self) -> bytes:
        streams = self.flush()

        def walk(entries: tuple[Entry, ...], path: str) -> tuple[Entry, ...]:
            out: list[Entry] = []
            for entry in entries:
                if isinstance(entry, Storage):
                    out.append(Storage(entry.name, walk(entry.entries, f"{path}{entry.name}/")))
                else:
                    out.append((entry[0], streams.get(f"{path}{entry[0]}", entry[1])))
            return tuple(out)

        return write_compound(walk(self.tree, ""))

    def document(self) -> tuple[PcbDocument, CompoundFile]:
        compound = open_compound(self.data(), file=self.file)
        return read_pcbdoc(compound, file=self.file), compound

    def changed_streams(self, original: dict[str, bytes]) -> Iterator[str]:
        streams = self.flush()
        for path in sorted(set(streams) | set(original)):
            if streams.get(path) != original.get(path):
                yield path


__all__ = ["PRIMITIVE_STORAGES", "PROPERTY_STORAGES", "SHAPE_BASED", "WIDE", "State"]
