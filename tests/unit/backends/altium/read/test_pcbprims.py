# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Binary primitives of the PCB reader (capability altium-pcb-reader, "Lossless PCB records", "Record
length tolerance" and "Track, arc, via and fill records", change c0041)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields

import pytest
from _altium_long import (
    ARC,
    ARC_WIDTH,
    TRACK_WIDTH,
    TRACK_XY,
    frame,
    long_arc,
    long_fill,
    long_pad,
    long_text,
    long_track,
    long_via,
    pattern,
)

from fenolite.backends.altium import pcbrecords
from fenolite.backends.altium.read.pcbprims import (
    MINIMUMS,
    SUBRECORDS,
    ArcRecord,
    FillRecord,
    RawPrimitive,
    TextRecord,
    TrackRecord,
    ViaRecord,
    decode_primitives,
)


def _one(data: bytes) -> TrackRecord | ArcRecord:
    (item,), trailing, issues = decode_primitives(data, where="Tracks6/Data")
    assert trailing == b"" and issues == []
    assert isinstance(item, TrackRecord | ArcRecord)
    return item


def test_frame_counts_and_minimums() -> None:
    assert SUBRECORDS == {1: 1, 2: 6, 3: 1, 4: 1, 5: 2, 6: 1, 11: 1, 12: 1}
    assert MINIMUMS == {
        "track": 33, "arc": 45, "via": 31, "fill": 37, "text": 40,
        "pad": 110, "pad-layers": 596, "region": 26,
    }  # fmt: skip


def test_frame_empty_stream() -> None:
    assert decode_primitives(b"", where="Tracks6/Data") == ((), b"", [])


def test_frame_component_body_is_raw_without_issue() -> None:
    body = frame(12, b"\x01\x02\x03")
    (item,), trailing, issues = decode_primitives(body, where="ComponentBodies6/Data")
    assert item == RawPrimitive(12, (b"\x01\x02\x03",), body)
    assert trailing == b"" and issues == []


def test_frame_start_offset() -> None:
    data = b"name" + long_track(36)
    (item,), trailing, issues = decode_primitives(data, where="FP/Data", start=4)
    assert isinstance(item, TrackRecord) and item.raw == data[4:]
    assert trailing == b"" and issues == []


def test_a_long_track_keeps_its_tail() -> None:
    data = long_track(49)
    track = _one(data)
    assert isinstance(track, TrackRecord)
    assert (track.x1, track.y1, track.x2, track.y2, track.width) == (*TRACK_XY, TRACK_WIDTH)
    assert track.tail == pattern(13) == bytes(range(1, 14))
    assert track.raw == data
    assert track.sub_polygon == 0


def test_track_prefix() -> None:
    track = _one(long_track(36, layer=32, net=3, component=0xFFFF))
    assert isinstance(track, TrackRecord)
    pre = track.prefix
    assert (pre.layer, pre.flags1, pre.flags2, pre.net, pre.polygon, pre.component) == (
        32,
        0x0C,
        0,
        3,
        None,
        None,
    )
    assert pre.locked is False


def test_track_short_form_of_33_bytes() -> None:
    track = _one(long_track(33))
    assert isinstance(track, TrackRecord)
    assert track.sub_polygon is None and track.tail == b""


def test_track_a_longer_record_than_any_seen() -> None:
    track = _one(long_track(80))
    assert isinstance(track, TrackRecord) and len(track.tail) == 44


def test_arc_long_and_short() -> None:
    for length, tail in ((45, 0), (47, 0), (56, 9), (60, 13)):
        arc = _one(long_arc(length))
        assert isinstance(arc, ArcRecord)
        assert (arc.cx, arc.cy, arc.radius, arc.start_angle, arc.end_angle, arc.width) == (
            ARC.cx, ARC.cy, ARC.radius, ARC.start, ARC.end, ARC_WIDTH,
        )  # fmt: skip
        assert arc.sub_polygon == (None if length < 47 else 0)
        assert len(arc.tail) == tail


def test_frame_a_short_record_is_kept() -> None:
    short, good = long_track(20), long_track(49)
    items, trailing, issues = decode_primitives(short + good, where="Tracks6/Data")
    assert isinstance(items[0], RawPrimitive) and items[0].raw == short and items[0].type == 4
    assert isinstance(items[1], TrackRecord)
    assert trailing == b""
    (problem,) = issues
    assert problem.code == "altium.pcb-read.short-record" and problem.severity == "warning"
    assert problem.where == "Tracks6/Data#0"


def test_frame_an_unknown_type_stops_the_stream() -> None:
    track = long_track(36)
    rest = b"\x09" + long_track(36)
    items, trailing, issues = decode_primitives(track + rest, where="Tracks6/Data")
    assert len(items) == 1 and isinstance(items[0], TrackRecord)
    assert trailing == rest and trailing[0] == 9
    (problem,) = issues
    assert problem.code == "altium.pcb-read.unknown-type" and problem.severity == "error"
    assert problem.where == f"Tracks6/Data#1@{len(track)}"


@pytest.mark.parametrize("cut", [1, 3, 10])
def test_frame_cut_subrecord(cut: int) -> None:
    whole = long_track(36)
    items, trailing, issues = decode_primitives(whole + whole[:-cut], where="Tracks6/Data")
    assert len(items) == 1 and trailing == whole[:-cut]
    assert [i.code for i in issues] == ["altium.pcb-read.truncated"]


def test_via_of_321_bytes() -> None:
    data = pcbrecords.via_record(0, 0, 236220, 118110)
    (via,), trailing, issues = decode_primitives(data, where="Vias6/Data")
    assert isinstance(via, ViaRecord) and trailing == b"" and issues == []
    assert (via.x, via.y, via.diameter, via.hole) == (0, 0, 236220, 118110)
    assert (via.start_layer, via.end_layer) == (1, 32)
    assert via.prefix.net is None and via.prefix.layer == 74
    assert len(via.tail) == 290 and via.raw == data
    assert via.tented_top is False and via.tented_bottom is False


def test_via_lengths_and_tenting() -> None:
    for length in (31, 209, 299, 321, 351):
        (via,), _, issues = decode_primitives(long_via(length, net=2), where="Vias6/Data")
        assert isinstance(via, ViaRecord) and issues == []
        assert (via.diameter, via.hole, via.prefix.net, len(via.tail)) == (236220, 118110, 2, length - 31)
    body = bytearray(subrecords_of(long_via(321)))
    body[1] |= 0x20 | 0x40
    (via,), _, _ = decode_primitives(frame(3, bytes(body)), where="Vias6/Data")
    assert isinstance(via, ViaRecord) and via.tented_top and via.tented_bottom


def test_via_short_is_raw() -> None:
    (item,), _, issues = decode_primitives(long_via(30), where="Vias6/Data")
    assert isinstance(item, RawPrimitive) and [i.code for i in issues] == ["altium.pcb-read.short-record"]


def test_rotated_fill() -> None:
    data = long_fill(50)
    (fill,), trailing, issues = decode_primitives(data, where="Fills6/Data")
    assert isinstance(fill, FillRecord) and trailing == b"" and issues == []
    assert (fill.x1, fill.y1, fill.x2, fill.y2, fill.rotation) == (0, 0, 1_000_000, 500_000, 90.0)
    assert len(fill.tail) == 13 and fill.raw == data


def test_fill_lengths() -> None:
    for length in (37, 46, 50):
        (fill,), _, issues = decode_primitives(long_fill(length), where="Fills6/Data")
        assert isinstance(fill, FillRecord) and issues == [] and len(fill.tail) == length - 37
    (item,), _, issues = decode_primitives(long_fill(36), where="Fills6/Data")
    assert isinstance(item, RawPrimitive) and len(issues) == 1


def subrecords_of(record: bytes) -> bytes:
    return record[5:]


def test_long_text_without_the_wide_string() -> None:
    data = long_text(252, text="X", font="Arial", bold=True, wide_index=0)
    (text,), trailing, issues = decode_primitives(data, where="Texts6/Data")
    assert isinstance(text, TextRecord) and trailing == b"" and issues == []
    assert text.font_name == "Arial" and text.bold is True and text.italic is False
    assert text.wide_index == 0 and text.short_text == "X" and text.text == "X"
    assert text.tail == pattern(252 - 119)
    assert (text.x, text.y, text.height) == (500_000, -600_000, 393701)
    assert (text.stroke_font, text.rotation) == (1, 90.0)
    assert text.mirrored is False and text.stroke_width == 39370 and text.raw == data


def test_text_short_form() -> None:
    (text,), _, issues = decode_primitives(long_text(40, text="AB"), where="Texts6/Data")
    assert isinstance(text, TextRecord) and issues == []
    assert text.is_designator is None and text.font_name is None and text.wide_index is None
    assert text.text == "AB" and text.tail == b""


def test_text_designator_flag() -> None:
    (text,), _, _ = decode_primitives(long_text(137, designator=True, component=2), where="Texts6/Data")
    assert isinstance(text, TextRecord)
    assert text.is_designator is True and text.is_comment is False and text.prefix.component == 2


def test_text_short_is_raw() -> None:
    (item,), _, issues = decode_primitives(long_text(39), where="Texts6/Data")
    assert isinstance(item, RawPrimitive) and [i.code for i in issues] == ["altium.pcb-read.short-record"]


LENGTHS: dict[str, tuple[Callable[[int], bytes], tuple[int, ...]]] = {
    "track": (long_track, (36, 45, 49)),
    "arc": (long_arc, (47, 56, 60)),
    "via": (long_via, (31, 209, 299, 321, 351)),
    "fill": (long_fill, (37, 46, 50)),
    "text": (long_text, (40, 137, 232, 252)),
    "pad": (lambda n: long_pad(n, 0), (110, 114, 170, 171, 185, 186, 194)),
}


@pytest.mark.parametrize("kind", sorted(LENGTHS))
def test_lengths_every_observed_one_is_read(kind: str) -> None:
    make, lengths = LENGTHS[kind]
    data = b"".join(make(n) for n in lengths)
    items, trailing, issues = decode_primitives(data, where="X/Data")
    assert trailing == b"" and issues == [] and len(items) == len(lengths)
    assert not any(isinstance(item, RawPrimitive) for item in items)
    first = items[0]
    core = [
        f.name for f in fields(first) if f.name not in ("raw", "tail") and getattr(first, f.name) is not None
    ]
    for item in items[1:]:
        assert [getattr(item, name) for name in core] == [getattr(first, name) for name in core], kind
