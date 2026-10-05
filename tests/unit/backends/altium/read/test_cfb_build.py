# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Proofs for the authored MS-CFB test container builder."""

from __future__ import annotations

import struct

from _cfb_build import ENDOFCHAIN, FREESECT, build, cut, cycle, set_field, share, spec_example
from _cfb_read import parse_compound


def test_worked_example_is_read_by_independent_reader() -> None:
    found = parse_compound(spec_example())
    assert set(found.streams) == {"Storage 1/Stream 1"}
    assert len(found.streams["Storage 1/Stream 1"]) == 544


def test_builder_covers_versions_storages_metadata_and_colours() -> None:
    rows = [{"path": "Library/Part/Data", "data": b"payload"}]
    for version in (3, 4):
        built = build(rows, version=version, root={"modified": 42, "clsid": bytes(range(16))})
        sector = 512 if version == 3 else 4096
        assert built.data[:8] == bytes.fromhex("D0CF11E0A1B11AE1")
        assert struct.unpack_from("<H", built.data, 0x1A)[0] == version
        assert len(built.data) % sector == 0
        assert built.offsets["entry:Library/Part/Data"] > built.offsets["directory"]
    parsed = parse_compound(build(rows).data)
    assert parsed.streams == {"Library/Part/Data": b"payload"}


def test_builder_emits_a_difat_chain_and_mutations_report_offsets() -> None:
    built = build([{"path": "Data", "data": b"x"}], pad_fat_sectors=14_000)
    fat_count = struct.unpack_from("<I", built.data, 0x2C)[0]
    difat_count = struct.unpack_from("<I", built.data, 0x48)[0]
    assert fat_count > 109
    assert difat_count >= 1
    first_difat = struct.unpack_from("<I", built.data, 0x44)[0]
    difat_offset = (first_difat + 1) * 512
    assert struct.unpack_from("<I", built.data, difat_offset + 127 * 4)[0] == ENDOFCHAIN
    assert struct.unpack_from("<I", built.data, difat_offset + (fat_count - 109) * 4)[0] == FREESECT

    original = build([{"path": "Data", "data": b"x" * 5000}])
    mutated = bytearray(original.data)
    start = struct.unpack_from("<I", mutated, original.offsets["entry:Data"] + 116)[0]
    offset = original.offsets["fat"] + start * 4
    assert cycle(mutated, offset, start) == offset
    assert struct.unpack_from("<I", mutated, offset)[0] == start
    offset = original.offsets["entry:Data"] + 116
    assert share(mutated, offset, 7) == offset
    assert struct.unpack_from("<I", mutated, offset)[0] == 7
    assert set_field(mutated, offset, start) == offset
    offset = cut(mutated, 1)
    assert offset == len(mutated)
