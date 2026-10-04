# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Permitted deviations and the reader's single-note-per-code report."""

from __future__ import annotations

import pytest
from _cfb_build import ENDOFCHAIN, build, set_field

from fenolite.backends.altium.read.cfb import NOTE_CODES, CompoundError, open_compound


def test_root_and_storage_metadata_are_kept_without_a_note() -> None:
    root_clsid = bytes(range(16))
    storage_clsid = bytes(range(16, 32))
    data = build(
        [
            {
                "path": "S",
                "kind": "storage",
                "clsid": storage_clsid,
                "state": 5,
                "created": 10,
                "modified": 20,
                "colour": 0,
            },
            {"path": "S/Data", "data": b"ok"},
        ],
        root={"clsid": root_clsid, "modified": 30},
    ).data
    found = open_compound(data)
    assert found.notes == ()
    assert found.node("").clsid == root_clsid
    assert found.node("").modified == 30
    assert found.node("S").clsid == storage_clsid
    assert (found.node("S").created, found.node("S").modified) == (10, 20)


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("minor-version", "cfb.note.minor-version"),
        ("header-fields", "cfb.note.header-fields"),
        ("partial-sector", "cfb.note.partial-sector"),
        ("fat-marks", "cfb.note.fat-marks"),
        ("high-size-bits", "cfb.note.high-size-bits"),
        ("long-chain", "cfb.note.long-chain"),
        ("entry-fields", "cfb.note.entry-fields"),
        ("tree-order", "cfb.note.tree-order"),
        ("orphan-entries", "cfb.note.orphan-entries"),
    ],
)
def test_each_note_code(case: str, expected: str) -> None:
    built = build([{"path": "Data", "data": b"x"}])
    data = bytearray(built.data)
    if case == "minor-version":
        set_field(data, 0x18, 1, 2)
    elif case == "header-fields":
        data[8] = 1
    elif case == "partial-sector":
        data.append(0)
    elif case == "fat-marks":
        set_field(data, built.offsets["fat"], 0xFFFFFFFF)
    elif case == "high-size-bits":
        set_field(data, built.offsets["entry:Data"] + 124, 1)
    elif case == "long-chain":
        minifat = built.offsets["minifat"]
        set_field(data, minifat, 1)
        set_field(data, minifat + 4, 2)
        set_field(data, minifat + 8, ENDOFCHAIN)
        set_field(data, built.offsets["entry:"] + 120, 192, 8)
    elif case == "entry-fields":
        data[built.offsets["entry:Data"] + 80] = 1
    elif case == "tree-order":
        two = build([{"path": "Alpha", "data": b"a"}, {"path": "Bravo", "data": b"b"}])
        data = bytearray(two.data)
        set_field(data, two.offsets["entry:Bravo"] + 68, 0xFFFFFFFF)
        set_field(data, two.offsets["entry:Bravo"] + 72, 1)
    elif case == "orphan-entries":
        set_field(data, built.offsets["entry:"] + 76, 0xFFFFFFFF)
    found = open_compound(bytes(data))
    assert [issue.code for issue in found.notes] == [expected]
    assert "1 case(s)" in found.notes[0].message
    with pytest.raises(CompoundError) as caught:
        open_compound(bytes(data), strict=True)
    assert caught.value.rule == expected


def test_three_stream_metadata_fields_are_one_note() -> None:
    rows = [{"path": name, "data": b"x"} for name in ("Alpha", "Bravo", "Charlie")]
    built = build(rows)
    data = bytearray(built.data)
    for name in ("Alpha", "Bravo", "Charlie"):
        data[built.offsets[f"entry:{name}"] + 108] = 1
    found = open_compound(bytes(data))
    (issue,) = found.notes
    assert issue.code == "cfb.note.entry-fields"
    assert "3 case(s)" in issue.message
    assert issue.where == "stream:Alpha"
    assert tuple(item.code for item in found.notes) == NOTE_CODES[:0] + ("cfb.note.entry-fields",)
