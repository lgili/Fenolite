# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A writer of MS-CFB version 3 compound files, the container of Altium's binary schematic (change c0033,
capability altium-schematic-writer, "Compound file container") and of its libraries (change c0034,
"Compound file storages").

Written from ``docs/formats/altium/compound-file.md`` (facts of [MS-CFB], S-0145) with the standard library
only. ``write_compound`` lays the streams out in one fixed layout: the header, then the FAT sectors, the
directory, the mini FAT, the mini stream and each large stream, every chain over consecutive sectors. Every
directory entry is black, with zero CLSIDs, state bits and times, so the bytes depend only on the streams.
No DIFAT sector is written: output whose FAT needs more sectors than the header can list is refused with
``CompoundTooLarge``.

Storages (change c0034): ``write_compound`` takes streams ``(name, data)`` and ``Storage`` values at any
depth. Entries are numbered in pre-order; each storage gets its own sibling tree. ``Storage`` and
``Entry`` are the public API that PCB documents and libraries build on. Empty streams (change c0035) take
no sector or mini sector; their entry has size 0 and starts at ENDOFCHAIN.
"""

# evidence: see binary, pcbdoc, pcblib, schlib

from __future__ import annotations

import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

SIGNATURE = bytes((0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1))
"""Bytes 0-7 of every compound file."""
SECTOR_SIZE = 512
"""Version 3: sector shift 9."""
MINI_SECTOR_SIZE = 64
"""Mini sector shift 6."""
MINI_STREAM_CUTOFF = 4096
"""A stream smaller than this lies in the mini stream; a reader decides by the size alone."""
MAX_FAT_SECTORS = 109
"""The FAT sectors the header can list; past this a file needs DIFAT sectors, which are not written."""
ENDOFCHAIN = 0xFFFFFFFE
FREESECT = 0xFFFFFFFF
FATSECT = 0xFFFFFFFD
NOSTREAM = 0xFFFFFFFF

MINOR_VERSION = 0x003E
MAJOR_VERSION = 3
BYTE_ORDER = 0xFFFE
SECTOR_SHIFT = 9
MINI_SECTOR_SHIFT = 6
HEADER_DIFAT_ENTRIES = 109
ENTRY_SIZE = 128
ENTRIES_PER_SECTOR = SECTOR_SIZE // ENTRY_SIZE
FAT_ENTRIES_PER_SECTOR = SECTOR_SIZE // 4
MAX_NAME = 31
FORBIDDEN = "/\\:!"
ROOT_NAME = "Root Entry"
TYPE_STORAGE = 1
TYPE_STREAM = 2
TYPE_ROOT = 5
BLACK = 1

_HEADER = struct.Struct(f"<8s16sHHHHH6s9I{HEADER_DIFAT_ENTRIES}I")
_ENTRY = struct.Struct("<64sHBBIII16sIQQIQ")


class CompoundTooLarge(ValueError):
    """The FAT would need more than ``MAX_FAT_SECTORS`` sectors, which needs DIFAT sectors."""


@dataclass(frozen=True)
class Storage:
    """A storage named ``name`` holding ``entries``: streams ``(name, data)`` and storages, in order."""

    name: str
    entries: tuple[Entry, ...]


Entry = tuple[str, bytes] | Storage
"""One item of a storage: a stream ``(name, data)`` or a ``Storage``."""


@dataclass(frozen=True)
class _Node:
    """One directory entry in pre-order: a stream (``data`` set) or a storage (``children`` its ids)."""

    name: str
    data: bytes | None
    children: tuple[int, ...] = ()


@dataclass(frozen=True)
class _Stream:
    index: int
    data: bytes
    small: bool
    start: int = 0


def _ceil(size: int, unit: int) -> int:
    return -(-size // unit)


def name_key(name: str) -> tuple[int, tuple[int, ...]]:
    """The MS-CFB order of sibling names: a shorter name first, then the upper-cased UTF-16 code units."""
    encoded = name.upper().encode("utf-16-le")
    units: tuple[int, ...] = struct.unpack(f"<{len(encoded) // 2}H", encoded)
    return len(units), units


def _check_name(name: str, what: str) -> None:
    if not 1 <= len(name.encode("utf-16-le")) // 2 <= MAX_NAME:
        raise ValueError(f"the {what} name {name!r} does not hold 1 to {MAX_NAME} characters")
    if any(ch in FORBIDDEN for ch in name) or "\0" in name:
        raise ValueError(f"the {what} name {name!r} holds one of / \\ : ! or NUL")


def _flatten(entries: Sequence[Entry]) -> list[_Node]:
    """The entries in pre-order after the root (index 0), every rule of names and contents checked."""
    nodes: list[_Node] = [_Node(ROOT_NAME, None)]

    def add(items: Sequence[Entry], owner: str) -> tuple[int, ...]:
        keys: set[tuple[int, tuple[int, ...]]] = set()
        ids: list[int] = []
        for item in items:
            if isinstance(item, Storage):
                name, what = item.name, "storage"
            else:
                name, what = item[0], "stream"
            _check_name(name, what)
            key = name_key(name)
            if key in keys:
                raise ValueError(f"the {what} name {name!r} repeats another of {owner} in the MS-CFB order")
            keys.add(key)
            index = len(nodes)
            ids.append(index)
            if isinstance(item, Storage):
                if not item.entries:
                    raise ValueError(f"the storage {name!r} is empty")
                nodes.append(_Node(name, None))
                children = add(item.entries, f"the storage {name!r}")
                nodes[index] = _Node(name, None, children)
            else:
                nodes.append(_Node(name, bytes(item[1])))
        return tuple(ids)

    nodes[0] = _Node(ROOT_NAME, None, add(entries, "the root"))
    return nodes


def storage_from_paths(mapping: Mapping[str, bytes]) -> tuple[Entry, ...]:
    """Entries from ``{"A/B/Data": data, …}``: storages and streams in the order their paths first appear.

    ``ValueError`` when a path is both a stream and a storage, or holds an empty part.
    """
    tree: dict[str, object] = {}
    for path, data in mapping.items():
        parts = path.split("/")
        if any(not part for part in parts):
            raise ValueError(f"the path {path!r} holds an empty name")
        level = tree
        for part in parts[:-1]:
            child = level.setdefault(part, {})
            if not isinstance(child, dict):
                raise ValueError(f"{part!r} in {path!r} is both a stream and a storage")
            level = cast(dict[str, object], child)
        if parts[-1] in level:
            raise ValueError(f"the path {path!r} is both a stream and a storage, or repeats")
        level[parts[-1]] = bytes(data)

    def build(level: dict[str, object]) -> tuple[Entry, ...]:
        out: list[Entry] = []
        for name, value in level.items():
            if isinstance(value, dict):
                out.append(Storage(name, build(cast(dict[str, object], value))))
            else:
                out.append((name, cast(bytes, value)))
        return tuple(out)

    return build(tree)


def _tree(order: list[int], links: dict[int, list[int]]) -> int:
    """The top of a binary search tree over ``order`` (entry ids sorted by name), built from the element at
    ``len // 2`` of each run; ``links[id]`` receives ``[left, right]``."""
    if not order:
        return NOSTREAM
    middle = len(order) // 2
    top = order[middle]
    links[top] = [_tree(order[:middle], links), _tree(order[middle + 1 :], links)]
    return top


def _entry(name: str, kind: int, left: int, right: int, child: int, start: int, size: int) -> bytes:
    encoded = (name + "\0").encode("utf-16-le")
    links = (left, right, child)
    return _ENTRY.pack(
        encoded.ljust(64, b"\0"), len(encoded), kind, BLACK, *links, bytes(16), 0, 0, 0, start, size
    )


_UNUSED = _ENTRY.pack(bytes(64), 0, 0, 0, NOSTREAM, NOSTREAM, NOSTREAM, bytes(16), 0, 0, 0, 0, 0)


def _pad(data: bytes, unit: int) -> bytes:
    return data + bytes(-len(data) % unit)


def write_compound(entries: Sequence[Entry]) -> bytes:
    """The bytes of a version 3 compound file whose root storage holds exactly ``entries``.

    ``entries`` are streams ``(name, data)`` and ``Storage`` values, numbered in pre-order from 1: each
    storage is followed at once by its own entries. ``ValueError`` for an invalid, repeated or empty
    or empty storage; ``CompoundTooLarge`` past the FAT limit. Streams only give c0033's bytes. An empty
    stream (change c0035) takes no sector: its entry has size 0 and starting sector ENDOFCHAIN.
    """
    nodes = _flatten(entries)
    mini_used = 0
    placed: list[_Stream] = []
    for index, node in enumerate(nodes):
        data = node.data
        if data is None or not data:
            continue
        if len(data) < MINI_STREAM_CUTOFF:
            placed.append(_Stream(index, data, True, mini_used))
            mini_used += _ceil(len(data), MINI_SECTOR_SIZE)
        else:
            placed.append(_Stream(index, data, False))
    mini_stream = b"".join(_pad(s.data, MINI_SECTOR_SIZE) for s in placed if s.small)
    directory_sectors = _ceil(len(nodes), ENTRIES_PER_SECTOR)
    minifat_sectors = _ceil(mini_used, FAT_ENTRIES_PER_SECTOR)
    mini_sectors = _ceil(len(mini_stream), SECTOR_SIZE)
    large = [_ceil(len(s.data), SECTOR_SIZE) for s in placed if not s.small]
    rest = directory_sectors + minifat_sectors + mini_sectors + sum(large)
    fat_sectors = 1
    while fat_sectors * FAT_ENTRIES_PER_SECTOR < fat_sectors + rest:
        fat_sectors += 1
    if fat_sectors > MAX_FAT_SECTORS:
        raise CompoundTooLarge(
            f"the compound file needs {fat_sectors} FAT sectors, more than the {MAX_FAT_SECTORS} that "
            "a file without DIFAT sectors can hold"
        )

    fat = [FREESECT] * (fat_sectors * FAT_ENTRIES_PER_SECTOR)
    for number in range(fat_sectors):
        fat[number] = FATSECT
    cursor = fat_sectors

    def chain(length: int) -> int:
        nonlocal cursor
        if length == 0:
            return ENDOFCHAIN
        start = cursor
        for number in range(start, start + length - 1):
            fat[number] = number + 1
        fat[start + length - 1] = ENDOFCHAIN
        cursor += length
        return start

    first_directory = chain(directory_sectors)
    first_minifat = chain(minifat_sectors)
    mini_start = chain(mini_sectors)
    starts = {s.index: s.start if s.small else chain(_ceil(len(s.data), SECTOR_SIZE)) for s in placed}

    minifat = [FREESECT] * (minifat_sectors * FAT_ENTRIES_PER_SECTOR)
    for s in placed:
        if s.small:
            count = _ceil(len(s.data), MINI_SECTOR_SIZE)
            for number in range(s.start, s.start + count - 1):
                minifat[number] = number + 1
            minifat[s.start + count - 1] = ENDOFCHAIN

    links: dict[int, list[int]] = {}
    tops: dict[int, int] = {}
    for index, node in enumerate(nodes):
        if node.data is None:
            order = sorted(node.children, key=lambda i: name_key(nodes[i].name))
            tops[index] = _tree(order, links)
    records = [
        _entry(
            ROOT_NAME,
            TYPE_ROOT,
            NOSTREAM,
            NOSTREAM,
            tops[0],
            mini_start,
            mini_used * MINI_SECTOR_SIZE,
        )
    ]
    for index, node in enumerate(nodes[1:], start=1):
        left, right = links[index]
        if node.data is None:
            records.append(_entry(node.name, TYPE_STORAGE, left, right, tops[index], 0, 0))
        else:
            start, size = starts.get(index, ENDOFCHAIN), len(node.data)
            records.append(_entry(node.name, TYPE_STREAM, left, right, NOSTREAM, start, size))
    records += [_UNUSED] * (directory_sectors * ENTRIES_PER_SECTOR - len(records))

    difat = list(range(fat_sectors)) + [FREESECT] * (HEADER_DIFAT_ENTRIES - fat_sectors)
    header = _HEADER.pack(
        SIGNATURE,
        bytes(16),
        MINOR_VERSION,
        MAJOR_VERSION,
        BYTE_ORDER,
        SECTOR_SHIFT,
        MINI_SECTOR_SHIFT,
        bytes(6),
        0,
        fat_sectors,
        first_directory,
        0,
        MINI_STREAM_CUTOFF,
        first_minifat,
        minifat_sectors,
        ENDOFCHAIN,
        0,
        *difat,
    )
    parts = [
        header,
        struct.pack(f"<{len(fat)}I", *fat),
        b"".join(records),
        struct.pack(f"<{len(minifat)}I", *minifat),
        _pad(mini_stream, SECTOR_SIZE),
        *(_pad(s.data, SECTOR_SIZE) for s in placed if not s.small),
    ]
    return b"".join(parts)


__all__ = [
    "ENDOFCHAIN",
    "FATSECT",
    "FREESECT",
    "MAX_FAT_SECTORS",
    "MINI_SECTOR_SIZE",
    "MINI_STREAM_CUTOFF",
    "NOSTREAM",
    "SECTOR_SIZE",
    "SIGNATURE",
    "CompoundTooLarge",
    "Entry",
    "Storage",
    "name_key",
    "storage_from_paths",
    "write_compound",
]
