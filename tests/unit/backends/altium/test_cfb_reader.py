# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The independent compound-file reader of the tests (capability altium-schematic-writer, "Compound
files read back"; change c0033; hypothesis ``H-A-SCHBIN-CFB``).

``tests/_cfb_read.py`` is checked against one input the writer did not make, the worked example of
[MS-CFB] section 3 (S-0145), rebuilt here from the field values of its tables rather than from its hex
dump, and against one negative control per rule it checks: each control mutates a written container,
and ``read_compound`` must reject it with a message that names the rule.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from functools import cache

import pytest
from _altium import sample_model
from _cfb_read import (
    ENDOFCHAIN,
    FATSECT,
    FREESECT,
    NOSTREAM,
    CfbError,
    parse_compound,
    read_compound,
)

from fenolite.backends.altium.binary import write_schdoc_binary
from fenolite.backends.altium.project import plan_sheet

SECTOR = 512
ENTRY = 128

# Offsets in a 128-byte directory entry (docs/formats/altium/compound-file.md, "Directory").
NAME, NAME_LENGTH, KIND, LEFT, RIGHT, CHILD, CLSID = 0, 64, 66, 68, 72, 76, 80
CREATED, MODIFIED, START, SIZE = 100, 108, 116, 120


UNUSED_ENTRY = bytes(68) + struct.pack("<3I", NOSTREAM, NOSTREAM, NOSTREAM) + bytes(48)


def _entry(
    name: str,
    kind: int,
    *,
    left: int = NOSTREAM,
    right: int = NOSTREAM,
    child: int = NOSTREAM,
    clsid: bytes = bytes(16),
    created: int = 0,
    modified: int = 0,
    start: int = 0,
    size: int = 0,
) -> bytes:
    encoded = (name + "\0").encode("utf-16-le")
    return struct.pack(
        "<64sHBBIII16sIQQIQ",
        encoded,
        len(encoded),
        kind,
        1,
        left,
        right,
        child,
        clsid,
        0,
        created,
        modified,
        start,
        size,
    )


def spec_example() -> bytes:
    """The compound file of [MS-CFB] section 3, from the field values of its tables.

    Header: version 3, one FAT sector (sector 0), the directory at sector 1, one mini FAT sector at
    sector 2, no DIFAT sector. FAT: FATSECT, ENDOFCHAIN (directory), ENDOFCHAIN (mini FAT), 4 and
    ENDOFCHAIN (the mini stream in sectors 3 and 4). Directory: ``Root Entry`` (child 1, mini stream at
    sector 3, size 576), ``Storage 1`` (a storage, child 2) and ``Stream 1`` (mini sector 0, size 544),
    then one unused entry. Mini FAT: mini sectors 0 to 8 chained, the rest free. The example's storage
    carries a CLSID and times, which a storage may; the values here stand in for them, as the reader
    checks only that they are allowed. The stream's bytes are a filler of the example's size.
    """
    header = struct.pack(
        "<8s16sHHHHH6s9I",
        bytes.fromhex("D0CF11E0A1B11AE1"),
        bytes(16),
        0x003E,
        3,
        0xFFFE,
        9,
        6,
        bytes(6),
        0,  # directory sectors
        1,  # FAT sectors
        1,  # first directory sector
        0,  # transaction signature
        4096,  # mini stream cutoff
        2,  # first mini FAT sector
        1,  # mini FAT sectors
        ENDOFCHAIN,  # first DIFAT sector
        0,  # DIFAT sectors
    ) + struct.pack("<109I", 0, *([FREESECT] * 108))
    fat = struct.pack("<128I", FATSECT, ENDOFCHAIN, ENDOFCHAIN, 4, ENDOFCHAIN, *([FREESECT] * 123))
    directory = b"".join(
        (
            _entry("Root Entry", 5, child=1, start=3, size=576),
            _entry(
                "Storage 1",
                1,
                child=2,
                clsid=bytes(range(1, 17)),
                created=0x01D0_0000_0000_0001,
                modified=0x01D0_0000_0000_0002,
            ),
            _entry("Stream 1", 2, start=0, size=544),
            UNUSED_ENTRY,
        )
    )
    minifat = struct.pack("<128I", *range(1, 9), ENDOFCHAIN, *([FREESECT] * 119))
    stream = bytes(0x41 + i % 26 for i in range(544))
    mini_stream = stream.ljust(2 * SECTOR, b"\0")
    return header + fat + directory + minifat + mini_stream


def test_spec_example() -> None:
    data = spec_example()
    assert len(data) == 512 + 5 * SECTOR
    found = parse_compound(data)
    assert list(found.streams) == ["Storage 1/Stream 1"]
    assert len(found.streams["Storage 1/Stream 1"]) == 544
    assert found.entries[0].size == 576
    assert found.chains["mini stream"] == [3, 4]
    assert found.mini_chains == {"Storage 1/Stream 1": list(range(9))}


@cache
def sample_binary() -> bytes:
    """The sample's binary schematic: FileHeader in sectors 4 to 32, Storage in mini sector 0."""
    return write_schdoc_binary(plan_sheet(sample_model()))


def test_sample_layout_the_controls_rely_on() -> None:
    found = parse_compound(sample_binary())
    assert found.chains["FileHeader"] == list(range(4, 33))
    assert found.mini_chains == {"Storage": [0]}
    assert [e.name for e in found.entries] == ["Root Entry", "FileHeader", "Storage", ""]
    assert (found.entries[1].left, found.entries[1].right) == (2, NOSTREAM)


def _u16(offset: int, value: int) -> Callable[[bytearray], None]:
    return lambda data: struct.pack_into("<H", data, offset, value)


def _u32(offset: int, value: int) -> Callable[[bytearray], None]:
    return lambda data: struct.pack_into("<I", data, offset, value)


def _u64(offset: int, value: int) -> Callable[[bytearray], None]:
    return lambda data: struct.pack_into("<Q", data, offset, value)


def _fat(sector: int, value: int) -> Callable[[bytearray], None]:
    return _u32(SECTOR + 4 * sector, value)


def _field(index: int, offset: int, value: int, width: int = 4) -> Callable[[bytearray], None]:
    position = 2 * SECTOR + ENTRY * index + offset
    return {2: _u16, 4: _u32, 8: _u64}[width](position, value)


def _byte(offset: int, value: int) -> Callable[[bytearray], None]:
    def mutate(data: bytearray) -> None:
        data[offset] = value

    return mutate


def _swap_children(data: bytearray) -> None:
    _field(1, LEFT, NOSTREAM)(data)
    _field(1, RIGHT, 2)(data)


def _append_sector(data: bytearray) -> None:
    data.extend(bytes(SECTOR))
    struct.pack_into("<I", data, SECTOR + 4 * 33, ENDOFCHAIN)


def _cut(count: int) -> Callable[[bytearray], None]:
    def mutate(data: bytearray) -> None:
        del data[-count:]

    return mutate


CONTROLS: list[tuple[str, Callable[[bytearray], None], str]] = [
    ("signature", _byte(0, 0x00), r"^signature"),
    ("header-clsid", _byte(8, 0x01), r"^header CLSID"),
    ("minor-version", _u16(0x18, 0x003B), r"^versions"),
    ("major-version", _u16(0x1A, 4), r"^versions"),
    ("directory-sector-count", _u32(0x28, 1), r"^versions"),
    ("byte-order", _u16(0x1C, 0xFEFF), r"^byte order"),
    ("sector-shift", _u16(0x1E, 12), r"^sector shift"),
    ("mini-sector-shift", _u16(0x20, 5), r"^mini sector shift"),
    ("reserved-bytes", _byte(0x22, 0x01), r"^reserved bytes"),
    ("transaction-signature", _u32(0x34, 1), r"^transaction signature"),
    ("cutoff", _u32(0x38, 2048), r"^cutoff"),
    ("difat-sectors", _u32(0x48, 1), r"^DIFAT"),
    ("difat-tail-not-free", _u32(0x4C + 4, 1), r"^DIFAT: the header entries after"),
    ("fat-sector-outside-file", _u32(0x4C, 40), r"^DIFAT: the header lists a FAT sector outside"),
    ("fatsect-not-listed", _fat(1, FATSECT), r"^FAT sectors: the header DIFAT does not list exactly"),
    ("fat-past-end-not-free", _fat(40, ENDOFCHAIN), r"^FAT: an entry past the end"),
    ("chain-without-end", _fat(32, FREESECT), r"^chain of FileHeader: sector 32 does not end"),
    ("chain-cycle", _fat(32, 4), r"^chain of FileHeader: sector 4 repeats"),
    ("chain-outside-table", _fat(32, 0x1000), r"^chain of FileHeader: sector 0x1000 is outside"),
    ("chain-shares-a-sector", _u32(0x3C, 1), r"^chain of the mini FAT: sector 1 is shared"),
    ("minifat-count", _u32(0x40, 2), r"^chain of the mini FAT: 1 sectors, the header says 2"),
    ("chain-length-regular", _field(1, SIZE, 13778, 8), r"^chain of FileHeader: 29 sectors for 13778 bytes"),
    ("chain-length-mini", _field(2, SIZE, 100, 8), r"^chain of Storage: 1 mini sectors for 100 bytes"),
    ("small-not-in-mini-stream", _field(1, SIZE, 4000, 8), r"^chain of FileHeader: sector 0x4 is outside"),
    ("large-stream-not-in-sectors", _field(2, SIZE, 4096, 8), r"^chain of Storage: sector 0 does not end"),
    ("root-name", _byte(2 * SECTOR, ord("r")), r"^root entry: entry 0 is not 'Root Entry'"),
    ("root-type", _byte(2 * SECTOR + KIND, 1), r"^root entry: entry 0 is not 'Root Entry'"),
    ("root-size", _field(0, SIZE, 128, 8), r"^root entry: size 128 is not 64 x the 1 mini sectors"),
    ("root-siblings", _field(0, LEFT, 1), r"^root entry: the root has siblings"),
    ("name-length-odd", _field(1, NAME_LENGTH, 23, 2), r"^name length of entry 1"),
    ("name-length-short", _field(1, NAME_LENGTH, 2, 2), r"^name length of entry 1"),
    ("name-without-nul", _field(1, NAME_LENGTH, 20, 2), r"^name length of entry 1"),
    ("name-forbidden", _byte(2 * SECTOR + ENTRY, ord("/")), r"^name of entry 1"),
    ("stream-clsid", _byte(2 * SECTOR + ENTRY + CLSID, 1), r"^stream FileHeader: the CLSID or a timestamp"),
    ("stream-created", _field(1, CREATED, 1, 8), r"^stream FileHeader: the CLSID or a timestamp"),
    ("stream-modified", _field(2, MODIFIED, 1, 8), r"^stream Storage: the CLSID or a timestamp"),
    ("stream-with-child", _field(1, CHILD, 2), r"^stream FileHeader: a stream has a child"),
    ("empty-stream", _field(2, SIZE, 0, 8), r"^stream Storage: an empty stream"),
    ("unused-entry-link", _field(3, LEFT, 0), r"^unused entry 3"),
    ("unused-entry-data", _field(3, SIZE, 1, 8), r"^unused entry 3"),
    ("tree-order", _swap_children, r"breaks the binary search"),
    ("tree-reaches-twice", _field(2, LEFT, 1), r"^tree of Root Entry: entry 1 is reached twice"),
    ("tree-misses-a-stream", _field(1, LEFT, NOSTREAM), r"^tree: entry 2 \('Storage'\) is not in any"),
    ("tree-links-the-root", _field(1, LEFT, 0), r"^tree of Root Entry: link to entry 0"),
    ("partial-sector", _cut(100), r"^sectors: \d+ bytes are not the header and whole sectors"),
    ("missing-sector", _cut(SECTOR), r"^FAT: an entry past the end"),
    ("stray-sector", _append_sector, r"^sectors: the file does not hold exactly"),
    ("short-file", _cut(17408 - 100), r"^header: the file has 100 bytes"),
]


def test_controls_start_from_a_valid_container() -> None:
    assert set(read_compound(sample_binary())) == {"FileHeader", "Storage"}
    assert len(sample_binary()) == 17408


@pytest.mark.parametrize(("mutate", "message"), [c[1:] for c in CONTROLS], ids=[c[0] for c in CONTROLS])
def test_negative_control(mutate: Callable[[bytearray], None], message: str) -> None:
    data = bytearray(sample_binary())
    mutate(data)
    with pytest.raises(CfbError, match=message):
        read_compound(bytes(data))


def test_broken_chain_caught() -> None:
    """A FileHeader sector whose FAT entry points at the first FAT sector."""
    data = bytearray(sample_binary())
    _fat(10, 0)(data)
    with pytest.raises(CfbError, match=r"^chain of FileHeader"):
        read_compound(bytes(data))


def test_spec_example_controls() -> None:
    """The rebuilt example is rejected too once one of its tables breaks a rule."""
    data = bytearray(spec_example())
    struct.pack_into("<I", data, 3 * SECTOR + 4 * 8, 3)
    with pytest.raises(CfbError, match=r"^chain of Storage 1/Stream 1: sector 3 repeats"):
        read_compound(bytes(data))
