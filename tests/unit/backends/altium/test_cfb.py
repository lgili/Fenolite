# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The compound-file writer (capability altium-schematic-writer, "Compound file container"; change c0033).

Every container is read back with ``tests/_cfb_read.py``, the independent reader written from
``docs/formats/altium/compound-file.md``; hypothesis ``H-A-SCHBIN-CFB``.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
from _cfb_read import ENDOFCHAIN, FATSECT, FREESECT, NOSTREAM, parse_compound, read_compound

from fenolite.backends.altium import cfb
from fenolite.backends.altium.cfb import CompoundTooLarge, write_compound

READER = Path(__file__).resolve().parents[3] / "_cfb_read.py"


def _data(size: int, seed: int = 1) -> bytes:
    return bytes((seed + 7 * i) % 251 + 1 for i in range(size))


def test_the_two_streams_of_a_schematic() -> None:
    head, storage = b"x" * 5000, b"y" * 25
    data = write_compound([("FileHeader", head), ("Storage", storage)])
    found = parse_compound(data)
    assert found.streams == {"FileHeader": head, "Storage": storage}
    assert len(found.chains["FileHeader"]) == 10
    assert found.mini_chains == {"Storage": [0]}
    root = found.entries[0]
    assert root.size == 64
    top = found.entries[root.child]
    assert top.name == "FileHeader"
    assert found.entries[top.left].name == "Storage"
    assert top.right == NOSTREAM


def test_header_fields() -> None:
    data = write_compound([("FileHeader", _data(5000)), ("Storage", _data(25))])
    assert data[:8] == cfb.SIGNATURE == bytes.fromhex("D0CF11E0A1B11AE1")
    assert data[8:24] == bytes(16)
    minor, major, order, shift, mini_shift = struct.unpack_from("<5H", data, 0x18)
    assert (minor, major, order, shift, mini_shift) == (0x003E, 3, 0xFFFE, 9, 6)
    assert data[0x22:0x28] == bytes(6)
    fields = struct.unpack_from("<9I", data, 0x28)
    dir_count, fat_count, first_dir, transaction, cutoff, first_mini, mini_count, first_difat, difat = fields
    assert (dir_count, transaction, cutoff, first_difat, difat) == (0, 0, 4096, ENDOFCHAIN, 0)
    assert (fat_count, first_dir, first_mini, mini_count) == (1, 1, 2, 1)
    listed = struct.unpack_from("<109I", data, 0x4C)
    assert listed[0] == 0 and set(listed[1:]) == {FREESECT}


def test_layout_order_and_entries() -> None:
    """FAT, directory, mini FAT, mini stream, then the large streams in the given order."""
    data = write_compound([("B", _data(5000)), ("A", _data(10)), ("C", _data(4096))])
    found = parse_compound(data)
    assert found.chains == {
        "directory": [1],
        "mini FAT": [2],
        "mini stream": [3],
        "B": list(range(4, 14)),
        "C": list(range(14, 22)),
    }
    assert found.sector_count == 22
    assert [e.name for e in found.entries] == ["Root Entry", "B", "A", "C"]
    for entry in found.entries:
        assert entry.colour == 1
        assert entry.clsid == bytes(16) and (entry.state, entry.created, entry.modified) == (0, 0, 0)
    assert found.entries[0].child == 1
    assert (found.entries[1].left, found.entries[1].right) == (2, 3)


def test_unused_entries_fill_the_last_directory_sector() -> None:
    data = write_compound([(f"S{i}", _data(10, i)) for i in range(5)])
    found = parse_compound(data)
    assert len(found.chains["directory"]) == 2
    assert len(found.entries) == 8
    assert [e.kind for e in found.entries[6:]] == [0, 0]


def test_tree_is_built_from_the_middle() -> None:
    names = ["e", "dd", "a", "ccc", "b", "Z"]
    data = write_compound([(n, _data(5)) for n in names])
    found = parse_compound(data)
    by_name = {e.name: e for e in found.entries}
    # sorted by length, then upper-cased code units: a, b, e, Z, dd, ccc
    top = found.entries[found.entries[0].child]
    assert top.name == "Z"
    assert found.entries[top.left].name == "b"
    assert found.entries[top.right].name == "ccc"
    assert found.entries[by_name["b"].left].name == "a"
    assert found.entries[by_name["b"].right].name == "e"
    assert found.entries[by_name["ccc"].left].name == "dd"


@pytest.mark.parametrize("size", [1, 64, 65, 4095, 4096, 4097])
def test_cutoff_boundary(size: int) -> None:
    payload = _data(size)
    found = parse_compound(write_compound([("S", payload)]))
    assert found.streams == {"S": payload}
    if size < 4096:
        assert "S" in found.mini_chains and "S" not in found.chains
        assert found.entries[0].size == 64 * -(-size // 64)
    else:
        assert "S" in found.chains and "S" not in found.mini_chains
        assert found.entries[0].size == 0
        assert found.entries[0].start == ENDOFCHAIN
        assert found.header.first_minifat == ENDOFCHAIN and found.header.minifat_sectors == 0


@pytest.mark.parametrize("size", [1, 65, 4097, 5000])
def test_tails_are_zero(size: int) -> None:
    data = write_compound([("S", _data(size))])
    found = parse_compound(data)
    if size < 4096:
        start = (found.chains["mini stream"][0] + 1) * 512
        tail = data[start + size : start + found.entries[0].size]
        sector_end = start + 512 * len(found.chains["mini stream"])
        tail += data[start + found.entries[0].size : sector_end]
    else:
        start = (found.chains["S"][0] + 1) * 512
        tail = data[start + size : start + 512 * len(found.chains["S"])]
    assert tail and tail == bytes(len(tail))


def test_several_fat_sectors() -> None:
    payload = _data(200_000)
    data = write_compound([("Big", payload)])
    found = parse_compound(data)
    assert found.header.fat_sectors == 4
    assert found.header.difat[:4] == (0, 1, 2, 3)
    assert [found.fat[n] for n in range(4)] == [FATSECT] * 4
    assert found.streams == {"Big": payload}


def test_fat_count_covers_itself() -> None:
    """Sizes around the point where the FAT needs a second sector."""
    for sectors in range(122, 130):
        found = parse_compound(write_compound([("S", _data(512 * sectors))]))
        used = sectors + 1 + found.header.fat_sectors
        assert found.header.fat_sectors * 128 >= used
        assert (found.header.fat_sectors - 1) * 128 < used


def test_too_large() -> None:
    with pytest.raises(CompoundTooLarge):
        write_compound([("Big", bytes(8_000_000))])
    assert issubclass(CompoundTooLarge, ValueError)


def test_limit_is_read_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfb, "MAX_FAT_SECTORS", 0)
    with pytest.raises(CompoundTooLarge):
        write_compound([("S", b"x")])


@pytest.mark.parametrize(
    "streams",
    [
        [("A" * 32, b"x")],
        [("a/b", b"x")],
        [("a\\b", b"x")],
        [("a:b", b"x")],
        [("a!b", b"x")],
        [("", b"x")],
        [("Storage", b"x"), ("STORAGE", b"y")],
    ],
)
def test_invalid_streams(streams: list[tuple[str, bytes]]) -> None:
    with pytest.raises(ValueError):
        write_compound(streams)


def test_31_characters_accepted() -> None:
    name = "N" * 31
    assert read_compound(write_compound([(name, b"x")])) == {name: b"x"}


def test_bytes_depend_only_on_the_streams() -> None:
    streams = [("FileHeader", _data(5000)), ("Storage", _data(25))]
    first = write_compound(streams)
    assert write_compound(list(streams)) == first
    assert write_compound(tuple(streams)) == first


def test_reader_is_independent() -> None:
    text = READER.read_text(encoding="utf-8")
    assert "import fenolite" not in text and "from fenolite" not in text
    assert "backends.altium.cfb" not in text


def test_empty_streams() -> None:
    """``altium-schematic-writer`` "Compound file container", "Empty streams" (change c0035)."""
    data = write_compound([("Header", b"\x00\x00\x00\x00"), ("Data", b"")])
    compound = parse_compound(data)
    assert compound.streams == {"Header": b"\x00\x00\x00\x00", "Data": b""}
    entries = {e.name: e for e in compound.entries}
    assert entries["Data"].size == 0 and entries["Data"].start == ENDOFCHAIN
    assert entries["Root Entry"].size == 64
    assert "Data" not in compound.mini_chains and "Data" not in compound.chains


def test_only_empty_streams() -> None:
    compound = parse_compound(write_compound([("Data", b"")]))
    assert compound.streams == {"Data": b""}
    root = next(e for e in compound.entries if e.name == "Root Entry")
    assert root.size == 0 and root.start == ENDOFCHAIN


def test_empty_stream_bytes_are_stable() -> None:
    entries = [cfb.Storage("Arcs6", (("Header", bytes(4)), ("Data", b"")))]
    assert write_compound(entries) == write_compound(entries)
