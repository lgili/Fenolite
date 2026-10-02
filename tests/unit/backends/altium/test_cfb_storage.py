# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Compound-file storages (capability altium-schematic-writer, "Compound file storages"; change c0034).

Every container is read back with ``tests/_cfb_read.py``, written from
``docs/formats/altium/compound-file.md``; hypotheses ``H-A-SCHLIB-OPEN`` and ``H-A-SCHLIB-KICAD``.
"""

from __future__ import annotations

import dataclasses
import struct

import pytest
from _cfb_read import NOSTREAM, CfbError, parse_compound, read_compound

from fenolite.backends.altium.cfb import Storage, storage_from_paths, write_compound

ENTRY_OFFSET = 1024  # the directory is sector 1, after the header and the FAT sector 0


def _data(size: int, seed: int = 1) -> bytes:
    return bytes((seed + 7 * i) % 251 + 1 for i in range(size))


def test_a_library_shaped_container() -> None:
    head, store, res, cap = _data(300), _data(25, 2), _data(90, 3), _data(70, 4)
    data = write_compound(
        [
            ("FileHeader", head),
            ("Storage", store),
            Storage("RES", (("Data", res),)),
            Storage("CAP", (("Data", cap),)),
        ]
    )
    found = parse_compound(data)
    assert found.streams == {"FileHeader": head, "Storage": store, "RES/Data": res, "CAP/Data": cap}
    names = [e.name for e in found.entries if e.kind != 0]
    assert names == ["Root Entry", "FileHeader", "Storage", "RES", "Data", "CAP", "Data"]
    assert found.storages == ["CAP", "RES"]  # tree order of the root's children
    for index in (3, 5):
        entry = found.entries[index]
        assert (entry.kind, entry.colour, entry.start, entry.size) == (1, 1, 0, 0)
        assert entry.clsid == bytes(16) and entry.state == 0 and entry.created == entry.modified == 0
        assert found.entries[entry.child].name == "Data"


def test_streams_only_keep_the_c0033_layout() -> None:
    """A streams-only call numbers the streams 1 … n and lays them out as before (the binary golden
    test checks the sample byte for byte)."""
    data = write_compound([("FileHeader", _data(5000)), ("Storage", _data(25))])
    found = parse_compound(data)
    assert found.storages == []
    assert [e.name for e in found.entries[:3]] == ["Root Entry", "FileHeader", "Storage"]


def test_two_levels_and_a_large_stream() -> None:
    big, small = _data(10_000, 5), _data(10, 6)
    data = write_compound([Storage("A", (Storage("B", (("Data", big),)),)), ("X", small)])
    found = parse_compound(data)
    assert read_compound(data) == {"A/B/Data": big, "X": small}
    assert "A/B/Data" in found.chains and "A/B/Data" not in found.mini_chains
    assert "X" in found.mini_chains
    assert [e.name for e in found.entries if e.kind != 0] == ["Root Entry", "A", "B", "Data", "X"]


def test_large_streams_take_sectors_in_pre_order() -> None:
    first, second = _data(5000, 7), _data(6000, 8)
    data = write_compound([Storage("S", (("Big", first),)), ("Late", second)])
    found = parse_compound(data)
    assert found.chains["S/Big"][-1] < found.chains["Late"][0]


def test_same_name_in_two_storages() -> None:
    data = write_compound([Storage("A", (("Data", b"1"),)), Storage("B", (("Data", b"2"),))])
    assert read_compound(data) == {"A/Data": b"1", "B/Data": b"2"}


@pytest.mark.parametrize(
    "entries",
    [
        [Storage("E", ())],
        [Storage("S", (("Data", b"1"), ("DATA", b"2")))],
        [Storage("S", (("Data", b"1"),)), ("s", b"2")],
        [Storage("A/B", (("Data", b"1"),))],
        [Storage("x" * 32, (("Data", b"1"),))],
        [Storage("S", (("Data", b""),))],
    ],
)
def test_invalid_storages(entries: list[object]) -> None:
    with pytest.raises(ValueError):
        write_compound(entries)  # type: ignore[arg-type]


def test_storage_is_a_frozen_dataclass() -> None:
    storage = Storage("RES", (("Data", b"1"),))
    assert dataclasses.is_dataclass(storage)
    with pytest.raises(dataclasses.FrozenInstanceError):
        storage.name = "CAP"  # type: ignore[misc]


def test_storage_from_paths() -> None:
    entries = storage_from_paths(
        {"FileHeader": b"h", "RES/Data": b"r", "RES/PinFrac": b"f", "CAP/Data": b"c"}
    )
    assert entries == (
        ("FileHeader", b"h"),
        Storage("RES", (("Data", b"r"), ("PinFrac", b"f"))),
        Storage("CAP", (("Data", b"c"),)),
    )
    assert storage_from_paths({"A/B/C": b"x"}) == (Storage("A", (Storage("B", (("C", b"x"),)),)),)


@pytest.mark.parametrize(
    "mapping",
    [{"A": b"1", "A/Data": b"2"}, {"A/Data": b"2", "A": b"1"}, {"A//Data": b"1"}, {"": b"1"}],
)
def test_storage_from_paths_refuses(mapping: dict[str, bytes]) -> None:
    with pytest.raises(ValueError):
        storage_from_paths(mapping)


# --- reader negative controls ----------------------------------------------------------------------


def _patch_entry(data: bytes, index: int, offset: int, fmt: str, value: int) -> bytes:
    """``data`` with field ``offset`` of directory entry ``index`` set to ``value``."""
    out = bytearray(data)
    struct.pack_into(fmt, out, ENTRY_OFFSET + 128 * index + offset, value)
    return bytes(out)


def _library() -> bytes:
    return write_compound([("FileHeader", b"h"), Storage("RES", (("Data", b"r"),))])


def test_reader_checks_storage_start_and_size() -> None:
    data = _library()
    assert parse_compound(data).entries[2].name == "RES"
    with pytest.raises(CfbError, match="storage RES: starting sector 5"):
        parse_compound(_patch_entry(data, 2, 116, "<I", 5))
    with pytest.raises(CfbError, match="storage RES: .*size 64"):
        parse_compound(_patch_entry(data, 2, 120, "<Q", 64))


def test_reader_checks_storage_children() -> None:
    data = _patch_entry(_library(), 2, 76, "<I", NOSTREAM)
    with pytest.raises(CfbError):
        parse_compound(data)
