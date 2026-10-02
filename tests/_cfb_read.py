# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A reader of MS-CFB compound files, for tests only (change c0033, capability altium-schematic-writer,
"Compound files read back").

It is written from ``docs/formats/altium/compound-file.md`` alone, independently of the product's writer,
which it never imports. ``read_compound`` returns every stream by its path and raises ``CfbError`` naming
the first rule the bytes break; ``parse_compound`` returns the same reading with the header, FAT, mini FAT,
directory and chains, for tests that look at the layout. Storages (change c0034, the schematic library)
are walked to any depth: each holds its own sibling tree, its entry has starting sector 0 and size 0,
and its streams are returned under ``<storage>/<stream>`` paths; ``Compound.storages`` lists the
storage paths in directory order. ``deframe`` splits a ``FileHeader`` stream of a
binary schematic into its records (``docs/formats/altium/schematic-binary.md``).

A misreading of the specification that this reader shares with the writer is caught only by an Altium
reader (``docs/evidence/altium-schematic.md``, Part V) and by the specification's own worked example
(``tests/unit/backends/altium/test_cfb_reader.py``).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

SIGNATURE = bytes((0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1))
HEADER_SIZE = 512
SECTOR = 512
MINI_SECTOR = 64
CUTOFF = 4096
ENTRY_SIZE = 128
HEADER_DIFAT = 109
MAX_REGULAR = 0xFFFFFFFA
DIFSECT = 0xFFFFFFFC
FATSECT = 0xFFFFFFFD
ENDOFCHAIN = 0xFFFFFFFE
FREESECT = 0xFFFFFFFF
NOSTREAM = 0xFFFFFFFF
ROOT_NAME = "Root Entry"
FORBIDDEN = "/\\:!"
UNUSED, STORAGE, STREAM, ROOT = 0, 1, 2, 5

_HEADER = struct.Struct(f"<8s16sHHHHH6s9I{HEADER_DIFAT}I")
_ENTRY = struct.Struct("<64sHBBIII16sIQQIQ")


class CfbError(ValueError):
    """The bytes break a rule of ``compound-file.md``; the message names the rule."""


@dataclass(frozen=True)
class Header:
    clsid: bytes
    minor: int
    major: int
    byte_order: int
    sector_shift: int
    mini_shift: int
    reserved: bytes
    dir_sectors: int
    fat_sectors: int
    first_dir: int
    transaction: int
    cutoff: int
    first_minifat: int
    minifat_sectors: int
    first_difat: int
    difat_sectors: int
    difat: tuple[int, ...]


@dataclass(frozen=True)
class Entry:
    index: int
    name: str
    name_length: int
    kind: int
    colour: int
    left: int
    right: int
    child: int
    clsid: bytes
    state: int
    created: int
    modified: int
    start: int
    size: int


@dataclass
class Compound:
    """One reading: the header, tables, entries, every chain by owner and the streams by path."""

    header: Header
    sector_count: int
    fat: list[int]
    minifat: list[int]
    entries: list[Entry]
    chains: dict[str, list[int]] = field(default_factory=dict)
    mini_chains: dict[str, list[int]] = field(default_factory=dict)
    streams: dict[str, bytes] = field(default_factory=dict)
    storages: list[str] = field(default_factory=list)


def name_key(name: str) -> tuple[int, list[int]]:
    """The MS-CFB order: a shorter name first, then the upper-cased UTF-16 code units."""
    units = name.upper().encode("utf-16-le")
    codes = [units[i] | units[i + 1] << 8 for i in range(0, len(units), 2)]
    return len(codes), codes


def _header(data: bytes) -> Header:
    if len(data) < HEADER_SIZE:
        raise CfbError(f"header: the file has {len(data)} bytes, fewer than the 512-byte header")
    values = _HEADER.unpack_from(data, 0)
    if values[0] != SIGNATURE:
        raise CfbError("signature: bytes 0-7 are not D0 CF 11 E0 A1 B1 1A E1")
    header = Header(*values[1:17], difat=tuple(values[17:]))
    if header.clsid != bytes(16):
        raise CfbError("header CLSID: bytes 8-23 are not zero")
    if header.minor != 0x003E or header.major != 3:
        raise CfbError(f"versions: minor {header.minor:#06x} major {header.major}, not 0x003e and 3")
    if header.dir_sectors != 0:
        raise CfbError(f"versions: version 3 counts 0 directory sectors, not {header.dir_sectors}")
    if header.byte_order != 0xFFFE:
        raise CfbError(f"byte order: {header.byte_order:#06x}, not 0xfffe")
    if header.sector_shift != 9:
        raise CfbError(f"sector shift: {header.sector_shift}, not 9")
    if header.mini_shift != 6:
        raise CfbError(f"mini sector shift: {header.mini_shift}, not 6")
    if header.reserved != bytes(6):
        raise CfbError("reserved bytes: the six reserved header bytes are not zero")
    if header.transaction != 0:
        raise CfbError(f"transaction signature: {header.transaction}, not 0")
    if header.cutoff != CUTOFF:
        raise CfbError(f"cutoff: the mini stream cutoff is {header.cutoff}, not 4096")
    if header.difat_sectors != 0 or header.first_difat != ENDOFCHAIN:
        raise CfbError("DIFAT: this reader reads files without DIFAT sectors only")
    return header


def _sector(data: bytes, number: int) -> bytes:
    start = (number + 1) * SECTOR
    return data[start : start + SECTOR]


def _fat(data: bytes, header: Header, count: int) -> list[int]:
    listed = header.difat[: header.fat_sectors]
    if header.fat_sectors > HEADER_DIFAT:
        raise CfbError(f"DIFAT: {header.fat_sectors} FAT sectors need DIFAT sectors")
    if any(s > MAX_REGULAR or s >= count for s in listed):
        raise CfbError("DIFAT: the header lists a FAT sector outside the file")
    if any(s != FREESECT for s in header.difat[header.fat_sectors :]):
        raise CfbError("DIFAT: the header entries after the FAT sectors are not FREESECT")
    if len(set(listed)) != len(listed):
        raise CfbError("DIFAT: the header lists a FAT sector twice")
    fat: list[int] = []
    for number in listed:
        fat.extend(struct.unpack("<128I", _sector(data, number)))
    if len(fat) < count:
        raise CfbError(f"FAT: {len(fat)} entries do not cover the file's {count} sectors")
    if any(entry != FREESECT for entry in fat[count:]):
        raise CfbError("FAT: an entry past the end of the file is not FREESECT")
    marked = {i for i, entry in enumerate(fat) if entry == FATSECT}
    if marked != set(listed):
        raise CfbError("FAT sectors: the header DIFAT does not list exactly the sectors marked FATSECT")
    return fat


def _chain(table: list[int], start: int, limit: int, owner: str) -> list[int]:
    """The sectors of a chain; ``CfbError`` on a cycle, a missing end or a number outside the table."""
    chain: list[int] = []
    seen: set[int] = set()
    current = start
    while current != ENDOFCHAIN:
        if current >= limit or current > MAX_REGULAR:
            raise CfbError(f"chain of {owner}: sector {current:#x} is outside the table")
        if current in seen:
            raise CfbError(f"chain of {owner}: sector {current} repeats (a cycle)")
        seen.add(current)
        chain.append(current)
        current = table[current]
        if current in (FREESECT, FATSECT, DIFSECT):
            raise CfbError(f"chain of {owner}: sector {chain[-1]} does not end with ENDOFCHAIN")
    return chain


def _claim(owners: dict[int, str], chain: list[int], owner: str) -> None:
    for number in chain:
        if number in owners:
            raise CfbError(f"chain of {owner}: sector {number} is shared with {owners[number]}")
        owners[number] = owner


def _ceil(size: int, unit: int) -> int:
    return -(-size // unit)


def _entry(raw: bytes, index: int) -> Entry:
    values = _ENTRY.unpack(raw)
    name_bytes, length = values[0], values[1]
    kind = values[2]
    if kind == UNUSED:
        expected = _ENTRY.pack(bytes(64), 0, 0, 0, NOSTREAM, NOSTREAM, NOSTREAM, bytes(16), 0, 0, 0, 0, 0)
        if raw != expected:
            raise CfbError(f"unused entry {index}: not all zero with NOSTREAM links")
        return Entry(index, "", 0, UNUSED, 0, NOSTREAM, NOSTREAM, NOSTREAM, bytes(16), 0, 0, 0, 0, 0)
    if length < 4 or length > 64 or length % 2:
        raise CfbError(f"name length of entry {index}: {length} is not an even count of 4 to 64 bytes")
    if name_bytes[length - 2 : length] != b"\0\0" or any(name_bytes[length:]):
        raise CfbError(f"name length of entry {index}: the name does not end with its NUL at {length}")
    name = name_bytes[: length - 2].decode("utf-16-le")
    if "\0" in name or any(ch in FORBIDDEN for ch in name):
        raise CfbError(f"name of entry {index}: {name!r} holds a forbidden character")
    if kind not in (STORAGE, STREAM, ROOT):
        raise CfbError(f"object type of entry {index}: {kind}")
    if values[3] not in (0, 1):
        raise CfbError(f"colour of entry {index}: {values[3]}")
    size = values[12]
    if size >> 32:
        raise CfbError(f"size of entry {index}: the high 4 bytes are not zero in version 3")
    return Entry(index, name, length, kind, *values[3:])


def _tree(entries: list[Entry], top: int, owner: str) -> list[Entry]:
    """The children of a storage in order; ``CfbError`` unless the sibling links form a search tree."""
    found: list[Entry] = []
    seen: set[int] = set()

    def walk(index: int, low: tuple[int, list[int]] | None, high: tuple[int, list[int]] | None) -> None:
        if index == NOSTREAM:
            return
        if index >= len(entries) or index == 0:
            raise CfbError(f"tree of {owner}: link to entry {index}, which is not a child entry")
        if index in seen:
            raise CfbError(f"tree of {owner}: entry {index} is reached twice")
        seen.add(index)
        entry = entries[index]
        if entry.kind not in (STORAGE, STREAM):
            raise CfbError(f"tree of {owner}: entry {index} is not a storage or a stream")
        key = name_key(entry.name)
        if (low is not None and key <= low) or (high is not None and key >= high):
            raise CfbError(f"tree of {owner}: {entry.name!r} breaks the binary search tree order")
        walk(entry.left, low, key)
        found.append(entry)
        walk(entry.right, key, high)

    walk(top, None, None)
    return found


def parse_compound(data: bytes) -> Compound:
    """Read ``data`` with every rule checked; ``CfbError`` names the first rule broken."""
    header = _header(data)
    if (len(data) - HEADER_SIZE) % SECTOR:
        raise CfbError(f"sectors: {len(data)} bytes are not the header and whole sectors")
    count = (len(data) - HEADER_SIZE) // SECTOR
    fat = _fat(data, header, count)
    owners: dict[int, str] = {}
    for number in header.difat[: header.fat_sectors]:
        owners[number] = "FAT"
    compound = Compound(header, count, fat, [], [])

    directory = _chain(fat, header.first_dir, count, "the directory")
    _claim(owners, directory, "the directory")
    compound.chains["directory"] = directory
    raw = b"".join(_sector(data, n) for n in directory)
    entries = [_entry(raw[i : i + ENTRY_SIZE], i // ENTRY_SIZE) for i in range(0, len(raw), ENTRY_SIZE)]
    compound.entries = entries
    if not entries:
        raise CfbError("root entry: the directory is empty")
    root = entries[0]
    if root.kind != ROOT or root.name != ROOT_NAME or root.name_length != 22:
        raise CfbError("root entry: entry 0 is not 'Root Entry' of type 5 with name length 22")
    if root.left != NOSTREAM or root.right != NOSTREAM:
        raise CfbError("root entry: the root has siblings")

    minifat_chain = _chain(fat, header.first_minifat, count, "the mini FAT")
    if len(minifat_chain) != header.minifat_sectors:
        raise CfbError(
            f"chain of the mini FAT: {len(minifat_chain)} sectors, the header says {header.minifat_sectors}"
        )
    _claim(owners, minifat_chain, "the mini FAT")
    compound.chains["mini FAT"] = minifat_chain
    minifat: list[int] = []
    for number in minifat_chain:
        minifat.extend(struct.unpack("<128I", _sector(data, number)))
    compound.minifat = minifat

    mini_chain = _chain(fat, root.start, count, "the mini stream")
    if len(mini_chain) != _ceil(root.size, SECTOR):
        raise CfbError(f"chain of the mini stream: {len(mini_chain)} sectors for a root size of {root.size}")
    _claim(owners, mini_chain, "the mini stream")
    compound.chains["mini stream"] = mini_chain
    mini_stream = b"".join(_sector(data, n) for n in mini_chain)[: root.size]
    used = [i for i, entry in enumerate(minifat) if entry != FREESECT]
    in_use = used[-1] + 1 if used else 0
    if root.size % MINI_SECTOR or root.size != in_use * MINI_SECTOR:
        raise CfbError(f"root entry: size {root.size} is not 64 x the {in_use} mini sectors in use")
    mini_owners: dict[int, str] = {}
    mini_count = root.size // MINI_SECTOR

    reached: set[int] = set()

    def visit(storage: Entry, prefix: str) -> None:
        for entry in _tree(entries, storage.child, storage.name):
            if entry.index in reached:
                raise CfbError(f"tree: entry {entry.index} belongs to two storages")
            reached.add(entry.index)
            path = prefix + entry.name
            if entry.kind == STORAGE:
                if entry.start != 0 or entry.size != 0:
                    where = f"starting sector {entry.start} and size {entry.size}"
                    raise CfbError(f"storage {path}: {where}, not 0 and 0")
                if entry.child == NOSTREAM:
                    raise CfbError(f"storage {path}: a storage without children has no recorded rule")
                compound.storages.append(path)
                visit(entry, path + "/")
                continue
            if entry.child != NOSTREAM:
                raise CfbError(f"stream {path}: a stream has a child")
            if entry.clsid != bytes(16) or entry.created or entry.modified:
                raise CfbError(f"stream {path}: the CLSID or a timestamp is not zero")
            if entry.size == 0:
                # compound-file.md, "Storages" (c0035): size 0, no sector, starting sector ENDOFCHAIN
                if entry.start != ENDOFCHAIN:
                    raise CfbError(f"stream {path}: an empty stream starts at {entry.start:#x}, not ENDOFCHAIN")
                compound.streams[path] = b""
                continue
            if entry.size < CUTOFF:
                chain = _chain(minifat, entry.start, mini_count, path)
                if len(chain) != _ceil(entry.size, MINI_SECTOR):
                    raise CfbError(f"chain of {path}: {len(chain)} mini sectors for {entry.size} bytes")
                _claim(mini_owners, chain, path)
                compound.mini_chains[path] = chain
                body = b"".join(mini_stream[n * MINI_SECTOR : (n + 1) * MINI_SECTOR] for n in chain)
            else:
                chain = _chain(fat, entry.start, count, path)
                if len(chain) != _ceil(entry.size, SECTOR):
                    raise CfbError(f"chain of {path}: {len(chain)} sectors for {entry.size} bytes")
                _claim(owners, chain, path)
                compound.chains[path] = chain
                body = b"".join(_sector(data, n) for n in chain)
            compound.streams[path] = body[: entry.size]

    visit(root, "")
    for entry in entries[1:]:
        if entry.kind != UNUSED and entry.index not in reached:
            raise CfbError(f"tree: entry {entry.index} ({entry.name!r}) is not in any storage's tree")
    if set(mini_owners) != set(used):
        raise CfbError("mini FAT: the mini sectors in use are not exactly the streams' chains")
    allocated = {i for i in range(count) if fat[i] != FREESECT}
    if allocated != set(owners):
        raise CfbError("sectors: the file does not hold exactly the sectors its chains and FAT use")
    return compound


def read_compound(data: bytes) -> dict[str, bytes]:
    """Every stream of ``data`` by its path (storage names and the stream name joined by ``/``)."""
    return parse_compound(data).streams


def deframe(stream: bytes) -> list[list[tuple[str, str]]]:
    """The records of a ``FileHeader`` stream as lists of ``(key, value)`` fields.

    Each record is a 4-byte little-endian word (low 24 bits the payload length, top byte the type) and
    the payload; a property list has type 0 and ends with a NUL that the length counts.
    """
    records: list[list[tuple[str, str]]] = []
    offset = 0
    while offset < len(stream):
        if offset + 4 > len(stream):
            raise CfbError(f"record at {offset}: the length word is cut")
        (word,) = struct.unpack_from("<I", stream, offset)
        length, kind = word & 0xFFFFFF, word >> 24
        if kind != 0:
            raise CfbError(f"record at {offset}: type {kind}, not a property list")
        payload = stream[offset + 4 : offset + 4 + length]
        if len(payload) != length:
            raise CfbError(f"record at {offset}: the payload is cut")
        if not payload.endswith(b"\0") or b"\0" in payload[:-1]:
            raise CfbError(f"record at {offset}: the payload does not end with its one NUL")
        text = payload[:-1].decode("ascii")
        if not text.startswith("|"):
            raise CfbError(f"record at {offset}: the text does not start with '|'")
        fields: list[tuple[str, str]] = []
        for part in text[1:].split("|"):
            key, equals, value = part.partition("=")
            if not equals or not key:
                raise CfbError(f"record at {offset}: field {part!r} is not KEY=VALUE")
            fields.append((key, value))
        records.append(fields)
        offset += 4 + length
    return records


__all__ = ["CfbError", "Compound", "deframe", "name_key", "parse_compound", "read_compound"]
