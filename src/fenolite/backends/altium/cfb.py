# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A writer of MS-CFB version 3 compound files, the container of Altium's binary schematic (change c0033,
capability altium-schematic-writer, "Compound file container").

Written from ``docs/formats/altium/compound-file.md`` (facts of [MS-CFB], S-0145) with the standard library
only. ``write_compound`` lays the streams out in one fixed layout: the header, then the FAT sectors, the
directory, the mini FAT, the mini stream and each large stream, every chain over consecutive sectors. Every
directory entry is black, with zero CLSIDs, state bits and times, so the bytes depend only on the streams.
No DIFAT sector is written: output whose FAT needs more sectors than the header can list is refused with
``CompoundTooLarge``.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass

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
TYPE_STREAM = 2
TYPE_ROOT = 5
BLACK = 1

_HEADER = struct.Struct(f"<8s16sHHHHH6s9I{HEADER_DIFAT_ENTRIES}I")
_ENTRY = struct.Struct("<64sHBBIII16sIQQIQ")


class CompoundTooLarge(ValueError):
    """The FAT would need more than ``MAX_FAT_SECTORS`` sectors, which needs DIFAT sectors."""


@dataclass(frozen=True)
class _Stream:
    name: str
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


def _check_names(streams: Sequence[tuple[str, bytes]]) -> None:
    keys: set[tuple[int, tuple[int, ...]]] = set()
    for name, data in streams:
        if not 1 <= len(name.encode("utf-16-le")) // 2 <= MAX_NAME:
            raise ValueError(f"the stream name {name!r} does not hold 1 to {MAX_NAME} characters")
        if any(ch in FORBIDDEN for ch in name) or "\0" in name:
            raise ValueError(f"the stream name {name!r} holds one of / \\ : ! or NUL")
        key = name_key(name)
        if key in keys:
            raise ValueError(f"the stream name {name!r} repeats another under the MS-CFB order")
        keys.add(key)
        if not data:
            raise ValueError(f"the stream {name!r} is empty")


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


def write_compound(streams: Sequence[tuple[str, bytes]]) -> bytes:
    """The bytes of a version 3 compound file whose root storage holds exactly ``streams``.

    ``streams`` are ``(name, data)`` pairs, written as directory entries 1 … n in the given order.
    ``ValueError`` for an invalid, repeated or empty stream; ``CompoundTooLarge`` past the FAT limit.
    """
    _check_names(streams)
    mini_used = 0
    placed: list[_Stream] = []
    for name, data in streams:
        if len(data) < MINI_STREAM_CUTOFF:
            placed.append(_Stream(name, bytes(data), True, mini_used))
            mini_used += _ceil(len(data), MINI_SECTOR_SIZE)
        else:
            placed.append(_Stream(name, bytes(data), False))
    mini_stream = b"".join(_pad(s.data, MINI_SECTOR_SIZE) for s in placed if s.small)
    directory_sectors = _ceil(1 + len(placed), ENTRIES_PER_SECTOR)
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
    starts = [s.start if s.small else chain(_ceil(len(s.data), SECTOR_SIZE)) for s in placed]

    minifat = [FREESECT] * (minifat_sectors * FAT_ENTRIES_PER_SECTOR)
    for s in placed:
        if s.small:
            count = _ceil(len(s.data), MINI_SECTOR_SIZE)
            for number in range(s.start, s.start + count - 1):
                minifat[number] = number + 1
            minifat[s.start + count - 1] = ENDOFCHAIN

    links: dict[int, list[int]] = {}
    order = sorted(range(1, len(placed) + 1), key=lambda i: name_key(placed[i - 1].name))
    top = _tree(order, links)
    entries = [
        _entry(
            ROOT_NAME,
            TYPE_ROOT,
            NOSTREAM,
            NOSTREAM,
            top,
            mini_start,
            mini_used * MINI_SECTOR_SIZE,
        )
    ]
    for index, (s, start) in enumerate(zip(placed, starts, strict=True), start=1):
        left, right = links[index]
        entries.append(_entry(s.name, TYPE_STREAM, left, right, NOSTREAM, start, len(s.data)))
    entries += [_UNUSED] * (directory_sectors * ENTRIES_PER_SECTOR - len(entries))

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
        b"".join(entries),
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
    "name_key",
    "write_compound",
]
