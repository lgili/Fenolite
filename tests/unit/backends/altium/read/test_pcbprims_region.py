# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Region records of the PCB reader (capability altium-pcb-reader, "Region and polygon records", change
c0041)."""

from __future__ import annotations

import struct

import pytest
from _altium_long import frame, region

from fenolite.backends.altium.read.pcbprims import RawPrimitive, RegionRecord, decode_primitives

OUTLINE = ((0.0, 0.0), (1000.0, 0.0), (1000.0, 500.0), (0.0, 500.0))
HOLE = ((100.0, 100.0), (200.0, 100.0), (150.0, 200.0))


@pytest.mark.parametrize("shape_based", [False, True])
def test_region_with_a_hole(shape_based: bool) -> None:
    data = region(OUTLINE, [HOLE], shape_based=shape_based, polygon=3)
    (item,), trailing, issues = decode_primitives(data, where="Regions6/Data", shape_based=shape_based)
    assert isinstance(item, RegionRecord) and trailing == b"" and issues == []
    assert len(item.outline) == 4
    assert [(v.x, v.y) for v in item.outline] == [(x, y) for x, y in OUTLINE]
    assert item.hole_count == 1 and len(item.holes) == 1 and len(item.holes[0]) == 3
    assert [(v.x, v.y) for v in item.holes[0]] == list(HOLE)
    assert item.properties.get("KIND") == "0" and item.properties.get("V7_LAYER") == "TOP"
    assert item.tail == b"" and item.raw == data
    assert item.prefix.polygon == 3 and item.shape_based is shape_based
    if shape_based:
        assert item.closing is not None and (item.closing.x, item.closing.y) == OUTLINE[0]
        assert item.outline[0].is_round is False and item.outline[0].radius == 0
        assert isinstance(item.outline[1].x, int)
    else:
        assert item.closing is None and item.outline[0].is_round is None
        assert isinstance(item.outline[1].x, float)


def test_region_stored_doubles_are_not_rounded() -> None:
    (item,), _, _ = decode_primitives(region(((0.25, -1.5), (3.125, 7.0), (2.0, 2.0))), where="Regions6/Data")
    assert isinstance(item, RegionRecord)
    assert (item.outline[0].x, item.outline[0].y) == (0.25, -1.5)


def test_region_tail() -> None:
    (item,), _, issues = decode_primitives(region(OUTLINE, tail=b"\x07\x08"), where="Regions6/Data")
    assert isinstance(item, RegionRecord) and item.tail == b"\x07\x08" and issues == []


def test_region_vertex_count_past_the_subrecord() -> None:
    data = region(OUTLINE)
    body = bytearray(data[5:])
    at = 22 + struct.unpack_from("<I", body, 18)[0]
    struct.pack_into("<I", body, at, 99)
    (item,), trailing, issues = decode_primitives(frame(11, bytes(body)), where="Regions6/Data")
    assert isinstance(item, RawPrimitive) and trailing == b""
    assert [i.code for i in issues] == ["altium.pcb-read.short-record"]


def test_region_shorter_than_its_minimum() -> None:
    (item,), _, issues = decode_primitives(frame(11, bytes(25)), where="Regions6/Data")
    assert isinstance(item, RawPrimitive) and len(issues) == 1
