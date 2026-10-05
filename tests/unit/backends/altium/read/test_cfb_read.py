# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Compound-file views, version layouts, and lazy stream reads."""

from __future__ import annotations

from pathlib import Path

import pytest
from _cfb_build import build, spec_example
from _cfb_read import read_compound as independent_read

from fenolite.backends.altium.read import cfb

ROOT = Path(__file__).resolve().parents[5]


def test_spec_worked_example_and_writer_output() -> None:
    worked = cfb.open_compound(spec_example())
    assert worked.evidence == cfb.EVIDENCE_V3
    assert worked.streams() == ("Storage 1/Stream 1",)
    assert len(worked.read("storage 1/stream 1")) == 544
    assert worked.notes == ()

    sample = ROOT / "tests/data/altium/sample/binary/altium_sample.SchDoc"
    data = sample.read_bytes()
    found = cfb.read_compound(sample)
    assert found.header.major == 3
    assert found.as_dict() == independent_read(data)
    assert found.streams() == ("Storage", "FileHeader")


@pytest.mark.parametrize("version", [3, 4])
@pytest.mark.parametrize("size", [0, 1, 64, 65, 4095, 4096, 4097])
def test_stream_size_cutoff(version: int, size: int) -> None:
    payload = bytes(i % 251 for i in range(size))
    found = cfb.open_compound(build([{"path": "Data", "data": payload}], version=version).data)
    assert found.read("data") == payload


def test_version4_nested_storage_and_regular_stream() -> None:
    rows = [
        {"path": "S/Small", "data": b"s" * 10},
        {"path": "S/Large", "data": b"l" * 5000},
        {"path": "RootStream", "data": b"r" * 70_000},
    ]
    found = cfb.open_compound(build(rows, version=4).data)
    assert found.evidence == cfb.EVIDENCE_V4
    assert found.header.sector_size == 4096
    assert found.node("S").children == ("S/Large", "S/Small")
    assert found.read("s/small") == b"s" * 10
    assert found.read("S/Large") == b"l" * 5000
    assert found.read("rootstream") == b"r" * 70_000


def test_difat_two_sectors_and_tree_round_trip() -> None:
    built = build([{"path": "Data", "data": b"x"}], pad_fat_sectors=30_000)
    found = cfb.open_compound(built.data)
    assert found.header.fat_sectors > 236
    assert found.header.difat_sectors == 2
    assert found.read("Data") == b"x"
    rewritten = cfb.open_compound(
        __import__("fenolite.backends.altium.cfb", fromlist=["write_compound"]).write_compound(found.tree())
    )
    assert rewritten.as_dict() == found.as_dict()


def test_paths_children_and_membership() -> None:
    found = cfb.open_compound(build([{"path": "Library/Data", "data": b"v"}]).data)
    assert "library/data" in found
    assert found.read("library/DATA") == b"v"
    assert found.node("Library").kind == "storage"
    assert found.children("library") == tuple(found.node(p) for p in found.node("Library").children)
    with pytest.raises(IsADirectoryError):
        found.read("Library")
    with pytest.raises(NotADirectoryError):
        found.children("Library/Data")
    with pytest.raises(KeyError):
        found.node("Nope")
