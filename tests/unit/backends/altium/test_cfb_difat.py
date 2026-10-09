# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""DIFAT sectors of a written compound file (capability altium-compound-reader, "DIFAT sectors in a written
compound file", scenario "Large file written and read"; change c0160, ``H-A-CONV-DIFAT``).

A file whose FAT needs more than the 109 sectors the header lists is written with DIFAT sectors after the
FAT sectors and read back by Fenolite's compound reader, which follows the DIFAT chain. A file of 109 FAT
sectors or fewer keeps the layout and the bytes it had before (no DIFAT sector).
"""

from __future__ import annotations

import hashlib
import struct

from fenolite.backends.altium import cfb
from fenolite.backends.altium.cfb import Storage, write_compound
from fenolite.backends.altium.read.cfb import open_compound

SECTOR = cfb.SECTOR_SIZE


def _data(size: int, seed: int) -> bytes:
    """``size`` bytes that differ per position and seed, so a misplaced sector shows."""
    block = hashlib.sha256(seed.to_bytes(4, "little")).digest()
    return (block * (size // len(block) + 1))[:size]


def _header(data: bytes) -> tuple[int, int, int, tuple[int, ...]]:
    """``(FAT sectors, first DIFAT sector, DIFAT sectors, header DIFAT)`` of a written file."""
    fields = struct.unpack_from("<9I", data, 0x2C)
    difat = struct.unpack_from("<109I", data, 0x4C)
    return fields[0], fields[6], fields[7], difat


def _tree(total_sectors: int) -> tuple[cfb.Entry, ...]:
    """Streams in two storages whose large sectors number about ``total_sectors``."""
    per = total_sectors // 4
    return (
        ("FileHeader", _data(300, 1)),
        Storage("Board6", (("Header", _data(4, 2)), ("Data", _data(per * SECTOR + 17, 3)))),
        Storage("Tracks6", (("Header", _data(4, 4)), ("Data", _data(per * SECTOR * 3 - 5, 5)))),
    )


def _streams(entries: tuple[cfb.Entry, ...], prefix: str = "") -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    for entry in entries:
        if isinstance(entry, Storage):
            found.update(_streams(entry.entries, f"{prefix}{entry.name}/"))
        else:
            found[f"{prefix}{entry[0]}"] = entry[1]
    return found


def test_large_file_written_and_read() -> None:
    """Scenario "Large file written and read": 181 FAT sectors, one DIFAT sector, every stream back."""
    entries = _tree(22_900)
    data = write_compound(entries)
    fat, first_difat, difat_count, listed = _header(data)
    assert fat == 181
    assert difat_count == 1 and first_difat == fat  # the DIFAT sector follows the FAT sectors
    assert listed == tuple(range(109))
    raw = struct.unpack_from("<128I", data, (first_difat + 1) * SECTOR)
    assert raw[: fat - 109] == tuple(range(109, fat))
    assert set(raw[fat - 109 : 127]) == {cfb.FREESECT} and raw[127] == cfb.ENDOFCHAIN
    fat_entries = struct.unpack_from(f"<{fat * 128}I", data, SECTOR)
    assert fat_entries[:fat] == (cfb.FATSECT,) * fat
    assert fat_entries[fat] == cfb.DIFSECT
    read = open_compound(data, file="large")
    assert read.as_dict() == _streams(entries)


def test_two_difat_sectors_chain() -> None:
    """Past 109 + 127 FAT sectors the first DIFAT sector names the second, which ends the chain."""
    entries = _tree(240 * 127)
    data = write_compound(entries)
    fat, first_difat, difat_count, _listed = _header(data)
    assert fat > 109 + 127 and difat_count == 2
    first = struct.unpack_from("<128I", data, (first_difat + 1) * SECTOR)
    second = struct.unpack_from("<128I", data, (first_difat + 2) * SECTOR)
    assert first[127] == first_difat + 1 and second[127] == cfb.ENDOFCHAIN
    assert open_compound(data, file="larger").as_dict() == _streams(entries)


def test_small_file_has_no_difat_sector() -> None:
    """A tree that needs 109 FAT sectors or fewer is written as before: no DIFAT sector, ENDOFCHAIN and 0
    in the header, the directory right after the FAT."""
    for sectors in (100 * 127, 108 * 127, 109 * 127 - 200):
        data = write_compound(_tree(sectors))
        fat, first_difat, difat_count, _listed = _header(data)
        assert fat <= 109 and first_difat == cfb.ENDOFCHAIN and difat_count == 0
        first_directory = struct.unpack_from("<I", data, 0x30)[0]
        assert first_directory == fat


def test_layout_counts_itself() -> None:
    """The FAT covers its own sectors, the DIFAT sectors and the rest, with no FAT sector to spare."""
    for rest in (1, 127, 13_000, 13_800, 13_900, 30_000, 60_000):
        fat, difat = cfb.fat_layout(rest)
        assert fat * 128 >= fat + difat + rest > (fat - 1) * 128
        assert difat == max(0, -(-(fat - 109) // 127))
