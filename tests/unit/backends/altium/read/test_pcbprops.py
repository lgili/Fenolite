# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Property records of the PCB reader (capability altium-pcb-reader, "Property records" and "An unknown
key and a duplicate survive", change c0041)."""

from __future__ import annotations

import struct
from fractions import Fraction

from fenolite.backends.altium.read.pcbprops import (
    PropertyRecord,
    parse_angle,
    parse_blocks,
    parse_bool,
    parse_int,
    parse_mil,
    parse_text,
)


def block(text: bytes, *, lead: bytes = b"", nul: bool = True) -> bytes:
    payload = text + (b"\0" if nul else b"")
    return lead + struct.pack("<I", len(payload)) + payload


def test_board_record_of_many_lines() -> None:
    data = block(b"|A=1\r|RECORD=Board|B=2")
    (record,), trailing, issues = parse_blocks(data, where="Board6/Data")
    assert record.fields == (("A", "1"), ("RECORD", "Board"), ("B", "2"))
    assert record.raw == data
    assert b"\r" in record.raw and record.raw.endswith(b"\0")
    assert trailing == b"" and issues == []


def test_lf_and_crlf_belong_to_the_separator() -> None:
    assert parse_text(b"|A=1\r\n|B=2\n") == (("A", "1"), ("B", "2"))


def test_piece_without_equals_and_empty_pieces() -> None:
    assert parse_text(b"|FLAG||A=") == (("FLAG", ""), ("A", ""))
    assert parse_text(b"V7_LAYER=TOP|KIND=0") == (("V7_LAYER", "TOP"), ("KIND", "0"))


def test_payload_without_nul_is_read_whole() -> None:
    (record,), trailing, issues = parse_blocks(block(b"|NAME=X", nul=False), where="Nets6/Data")
    assert record.fields == (("NAME", "X"),)
    assert trailing == b"" and issues == []


def test_an_unknown_key_and_a_duplicate_survive() -> None:
    (record,), _, _ = parse_blocks(block(b"|NAME=GND|XYZZY=1|XYZZY=2"), where="Nets6/Data")
    assert record.fields == (("NAME", "GND"), ("XYZZY", "1"), ("XYZZY", "2"))
    assert record.get("name") == "GND"
    assert record.get_all("xyzzy") == ("1", "2")
    assert record.keys() == ("NAME", "XYZZY", "XYZZY")


def test_utf8_key_preferred() -> None:
    text = b"|NAME=R?sistance|%UTF8%NAME=" + "Résistance".encode()
    record = PropertyRecord(block(text), parse_text(text))
    assert record.get("name") == "Résistance"


def test_bad_utf8_falls_back() -> None:
    text = b"|NAME=plain|%UTF8%NAME=\xff\xfe"
    assert PropertyRecord(b"", parse_text(text)).get("NAME") == "plain"


def test_iso_8859_1_maps_every_byte() -> None:
    text = bytes(range(0x20, 0x100)).replace(b"|", b"").replace(b"=", b"")
    ((key, value),) = parse_text(b"|K=" + text)
    assert key == "K" and value.encode("iso-8859-1") == text


def test_length_in_mils() -> None:
    assert parse_mil("0.5mil") == Fraction(5000)
    assert parse_mil("-0.0001mil") == Fraction(-1)
    assert parse_mil("0.5mm") is None
    assert parse_mil(None) is None
    assert parse_mil("10MIL") == Fraction(100000)


def test_booleans_integers_and_angles() -> None:
    assert [parse_bool(t) for t in ("TRUE", "FALSE", "T", "F", "yes")] == [True, False, True, False, None]
    assert parse_int(" 12") == 12 and parse_int("x") is None
    assert parse_angle(" 2.70000000000000E+0002") == 270.0
    assert parse_angle("abc") is None


def test_truncated_block() -> None:
    first = block(b"|A=1")
    second = struct.pack("<I", 100) + bytes(20)
    records, trailing, issues = parse_blocks(first + second, where="Nets6/Data")
    assert len(records) == 1
    assert trailing == second and len(trailing) == 24
    (problem,) = issues
    assert problem.code == "altium.pcb-read.truncated" and problem.severity == "error"
    assert problem.where == f"Nets6/Data@{len(first)}"


def test_lead_bytes_of_rules() -> None:
    data = block(b"|RULEKIND=Width", lead=b"\x02\x00") + block(b"|RULEKIND=Clearance", lead=b"\x00\x00")
    records, trailing, issues = parse_blocks(data, lead=2, where="Rules6/Data")
    assert [r.lead for r in records] == [b"\x02\x00", b"\x00\x00"]
    assert b"".join(r.raw for r in records) == data
    assert trailing == b"" and issues == []


def test_cut_length_word() -> None:
    records, trailing, issues = parse_blocks(block(b"|A=1") + b"\x01\x02", where="X/Data")
    assert len(records) == 1 and trailing == b"\x01\x02" and len(issues) == 1
