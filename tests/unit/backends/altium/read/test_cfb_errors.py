# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Located rule failures for structural and bounded-input errors."""

from __future__ import annotations

from pathlib import Path

import pytest
from _cfb_build import build, set_field

from fenolite.backends.altium.read.cfb import CompoundError, Limits, is_compound, open_compound


def _must_fail(data: bytes, rule: str, locator: str, offset: int | None) -> None:
    with pytest.raises(CompoundError) as caught:
        open_compound(data, file="x.PcbDoc")
    err = caught.value
    assert err.rule == rule
    assert err.file == "x.PcbDoc"
    assert err.locator == locator
    assert err.offset == offset
    assert err.message.startswith(rule)


def test_signature_truncation_header_and_difat_errors() -> None:
    valid = build([{"path": "Data", "data": b"x"}])
    changed = bytearray(valid.data)
    changed[0] = 0
    _must_fail(bytes(changed), "cfb.signature", "header", 0)
    _must_fail(b"\0\0\0", "cfb.truncated", "header", 0)
    changed = bytearray(valid.data)
    set_field(changed, 0x1A, 5, 2)
    _must_fail(bytes(changed), "cfb.header", "header", 0x1A)
    changed = bytearray(valid.data)
    set_field(changed, 0x2C, 2)
    _must_fail(bytes(changed), "cfb.difat", "header", 0x2C)


def test_chain_cycle_has_fat_field_location() -> None:
    built = build([{"path": "Data", "data": b"x" * 5000}])
    start = int.from_bytes(
        built.data[built.offsets["entry:Data"] + 116 : built.offsets["entry:Data"] + 120], "little"
    )
    fat_offset = built.offsets["fat"] + start * 4
    changed = bytearray(built.data)
    set_field(changed, fat_offset, start)
    _must_fail(bytes(changed), "cfb.chain", "stream:Data", fat_offset)


def test_shared_sector_directory_name_duplicate_size_and_limit_errors() -> None:
    built = build([{"path": "Alpha", "data": b"a" * 5000}, {"path": "Bravo", "data": b"b" * 5000}])
    data = bytearray(built.data)
    first = int.from_bytes(
        data[built.offsets["entry:Alpha"] + 116 : built.offsets["entry:Alpha"] + 120], "little"
    )
    start_offset = built.offsets["entry:Bravo"] + 116
    set_field(data, start_offset, first)
    fat_offset = built.offsets["fat"] + first * 4
    _must_fail(bytes(data), "cfb.shared-sector", "stream:Bravo", fat_offset)

    built = build([{"path": "Data", "data": b"x"}])
    data = bytearray(built.data)
    set_field(data, built.offsets["entry:"] + 76, 1000)
    with pytest.raises(CompoundError) as caught:
        open_compound(bytes(data))
    assert caught.value.rule == "cfb.directory"

    data = bytearray(built.data)
    set_field(data, built.offsets["entry:Data"] + 64, 1, 2)
    with pytest.raises(CompoundError) as caught:
        open_compound(bytes(data))
    assert caught.value.rule == "cfb.name"

    built = build([{"path": "Alpha", "data": b"a"}, {"path": "Bravo", "data": b"b"}])
    data = bytearray(built.data)
    alpha = built.offsets["entry:Alpha"]
    bravo = built.offsets["entry:Bravo"]
    data[bravo : bravo + 10] = data[alpha : alpha + 10]
    with pytest.raises(CompoundError) as caught:
        open_compound(bytes(data))
    assert caught.value.rule == "cfb.duplicate-name"

    built = build([{"path": "Data", "data": b"x"}])
    data = bytearray(built.data)
    set_field(data, built.offsets["entry:"] + 120, 0, 8)
    with pytest.raises(CompoundError) as caught:
        open_compound(bytes(data))
    assert caught.value.rule == "cfb.size"

    with pytest.raises(CompoundError) as caught:
        open_compound(built.data, limits=Limits(max_file_bytes=1))
    assert caught.value.rule == "cfb.limit"


def test_read_compound_passes_the_supplied_file_name(tmp_path: Path) -> None:
    path = tmp_path / "bad.PcbDoc"
    path.write_bytes(b"bad")
    with pytest.raises(CompoundError) as caught:
        open_compound(path.read_bytes(), file=str(path))
    assert caught.value.file == str(path)


def test_empty_is_truncated_and_not_a_compound() -> None:
    _must_fail(b"", "cfb.truncated", "header", 0)
    assert not is_compound(b"")
