# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""DIFAT sectors of a written compound file (capability altium-compound-reader, "DIFAT sectors in a written
compound file"; change c0160; hypothesis ``H-A-CONV-DIFAT``).

The scenario "Large file written and read": a storage tree whose streams need 181 FAT sectors is written,
every stream is read back byte for byte by the independent reader ``tests/_cfb_read.py`` and by Fenolite's
own ``backends.altium.read.cfb``, and the header names one DIFAT sector. A tree that needs 109 FAT sectors
or fewer is written with no DIFAT sector at all, which is what keeps every committed sample's bytes.

The sizes are not round numbers: they sit just past the point where the FAT count settles, so the expected
counts are a measurement of the writer's rule and not a coincidence. A file needs a second DIFAT sector once
its FAT needs more than the header's 109 entries plus the 127 numbers a DIFAT sector lists.
"""

from __future__ import annotations

import struct
from pathlib import Path

from _cfb_read import parse_compound

from fenolite.backends.altium import cfb
from fenolite.backends.altium.cfb import DIFSECT, ENDOFCHAIN, FATSECT, FREESECT, write_compound
from fenolite.backends.altium.read import cfb as reader

BIG_SECTORS = 22_860
"""A ``Data`` stream of this many sectors leaves the file needing 181 FAT sectors: 179 and 180 fall short of
the capacity the count must cover, and 181 covers it together with the one DIFAT sector it adds."""
TWO_DIFAT_SECTORS = 30_000
"""The same, past the 109 + 127 FAT sectors the header and one DIFAT sector can list: 237 and two."""
HEADER = b"PCB 6.0 Binary Library File"


def _data(size: int, seed: int = 3) -> bytes:
    return bytes((seed + 11 * i) % 253 + 1 for i in range(size))


def _tree(payload: bytes) -> tuple[cfb.Entry, ...]:
    """A storage tree with one large stream and two small ones, the shape a library or a document has."""
    return (
        ("FileHeader", HEADER),
        cfb.Storage(
            "Library",
            (("Header", struct.pack("<I", 1)), ("Data", payload), ("WideStrings", b"")),
        ),
    )


def _expected(payload: bytes) -> dict[str, bytes]:
    return {
        "FileHeader": HEADER,
        "Library/Header": struct.pack("<I", 1),
        "Library/Data": payload,
        "Library/WideStrings": b"",
    }


def _sector(data: bytes, number: int) -> tuple[int, ...]:
    start = (number + 1) * cfb.SECTOR_SIZE
    return struct.unpack("<128I", data[start : start + cfb.SECTOR_SIZE])


def _read_with_fenolite(tmp_path: Path, data: bytes) -> dict[str, bytes]:
    """Every stream of ``data`` as Fenolite's own reader gives them; it reads a file, not bytes."""
    path = tmp_path / "large.PcbLib"
    path.write_bytes(data)
    compound = reader.read_compound(path)
    return {name: compound.read(name) for name in compound.streams()}


def test_large_file_written_and_read(tmp_path: Path) -> None:
    """The scenario: 181 FAT sectors, one DIFAT sector, every stream read back byte for byte."""
    payload = _data(BIG_SECTORS * cfb.SECTOR_SIZE)
    data = write_compound(_tree(payload))
    found = parse_compound(data)
    assert (found.header.fat_sectors, found.header.difat_sectors) == (181, 1)
    assert found.header.first_difat == 181, "the DIFAT sector stands right after the 181 FAT sectors"
    assert found.header.difat == tuple(range(109)), "the header lists the first 109 FAT sectors"
    assert [found.fat[n] for n in range(181)] == [FATSECT] * 181
    assert found.fat[181] == DIFSECT, "the FAT marks the DIFAT sector"
    listed = _sector(data, 181)
    assert listed[:72] == tuple(range(109, 181)), "the chain lists the rest of the FAT sectors"
    assert set(listed[72:127]) == {FREESECT}
    assert listed[127] == ENDOFCHAIN
    assert found.streams == _expected(payload)
    assert _read_with_fenolite(tmp_path, data) == _expected(payload)


def test_second_difat_sector_is_linked(tmp_path: Path) -> None:
    """Past the 109 + 127 numbers the header and one DIFAT sector list, the chain links a second sector."""
    payload = _data(TWO_DIFAT_SECTORS * cfb.SECTOR_SIZE)
    data = write_compound(_tree(payload))
    found = parse_compound(data)
    assert (found.header.fat_sectors, found.header.difat_sectors) == (237, 2)
    first, second = found.header.first_difat, found.header.first_difat + 1
    assert (first, second) == (237, 238)
    assert _sector(data, first)[:127] == tuple(range(109, 236))
    assert _sector(data, first)[127] == second, "the last entry names the next DIFAT sector"
    assert _sector(data, second)[0] == 236, "the second sector holds the 237th number"
    assert set(_sector(data, second)[1:127]) == {FREESECT}
    assert _sector(data, second)[127] == ENDOFCHAIN, "the chain ends with ENDOFCHAIN"
    assert [found.fat[n] for n in (first, second)] == [DIFSECT, DIFSECT]
    assert found.streams == _expected(payload)
    assert _read_with_fenolite(tmp_path, data) == _expected(payload)


def test_small_file_has_no_difat_sector() -> None:
    """A tree that needs 109 FAT sectors or fewer keeps the bytes it had: no DIFAT sector, no DIFSECT."""
    data = write_compound([("FileHeader", _data(5000)), ("Storage", _data(25))])
    found = parse_compound(data)
    assert found.header.difat_sectors == 0
    assert found.header.first_difat == ENDOFCHAIN
    assert DIFSECT not in found.fat
    assert found.header.difat[0] == 0 and set(found.header.difat[1:]) == {FREESECT}
    assert found.streams == {"FileHeader": _data(5000), "Storage": _data(25)}
