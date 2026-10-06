# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Property lists keep every field (capability altium-schematic-reader, "Property lists keep every field")."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fenolite.backends.altium.read.sch.props import Prop, parse, parse_int

MIXED = b"|RECORD=27|OwnerPartId=-1|FROB=x=y|LOCATIONCOUNT=2|X1=10|Y1=20|X2=30|Y2=20|"


def test_mixed_case_and_unknown_keys_survive() -> None:
    props = parse(MIXED)
    assert props.get("OWNERPARTID") == "-1"
    assert props.int("OWNERPARTID") == -1
    assert props.raw("FROB") == b"x=y"
    assert props.keys() == ("RECORD", "OWNERPARTID", "FROB", "LOCATIONCOUNT", "X1", "Y1", "X2", "Y2")
    assert props.to_bytes() == MIXED
    assert props.prop("ownerpartid") == Prop("OwnerPartId", b"-1")


def test_missing_values() -> None:
    props = parse(b"|RECORD=14|ISSOLID=T")
    assert props.bool("ISSOLID") is True
    assert props.bool("TRANSPARENT") is False
    assert props.int("LINEWIDTH") == 0
    assert props.text("NAME") == ""
    assert props.get("NAME") is None
    assert props.has("issolid") and not props.has("NAME")


def test_odd_fields_are_kept() -> None:
    for payload in (b"RECORD=28|TEXT=a", b"", b"|", b"||A=1", b"|A", b"|A=1|A=2|", b"|=x", b"|A= 7 "):
        assert parse(payload).to_bytes() == payload
    props = parse(b"|A|B=")
    assert props.items == (Prop("", None), Prop("A", None), Prop("B", b""))
    assert props.keys() == ("B",)


def test_repeated_key() -> None:
    props = parse(b"|HOTSPOTGRIDON=T|HotSpotGridOn=F|X=1")
    assert props.bool("HOTSPOTGRIDON") is True
    assert props.duplicates == ("HOTSPOTGRIDON",)
    assert props.keys() == ("HOTSPOTGRIDON", "X")


def test_integers_and_booleans() -> None:
    assert parse_int(b" -12 ") == -12
    assert parse_int(b"+3") == 3
    assert parse_int(b"1.5") is None
    assert parse_int(b"") is None
    props = parse(b"|A=t|B=T |C=two")
    assert props.bool("A") is False
    assert props.bool("B") is True
    assert props.int("C", 5) == 5


def test_text_is_trimmed_in_the_view_only() -> None:
    props = parse(b"|NAME=  R1 ")
    assert props.text("NAME") == "R1"
    assert props.raw("NAME") == b"  R1 "


@given(st.binary(max_size=300))
def test_to_bytes_is_the_identity(payload: bytes) -> None:
    assert parse(payload).to_bytes() == payload
