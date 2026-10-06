# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pad records of the PCB reader (capability altium-pcb-reader, "Pad records", change c0041)."""

from __future__ import annotations

import pytest
from _altium_long import WORKED_PAD, long_pad, pattern

from fenolite.backends.altium.read.pcbprims import PadRecord, RawPrimitive, decode_primitives


def _pad(data: bytes) -> PadRecord:
    (pad,), trailing, issues = decode_primitives(data, where="Pads6/Data")
    assert isinstance(pad, PadRecord) and trailing == b"" and issues == []
    assert pad.raw == data
    return pad


def test_short_and_long_pad_agree() -> None:
    short, long = _pad(long_pad(114, 596)), _pad(long_pad(194, 651))
    for pad in (short, long):
        assert pad.name == "1"
        assert (pad.x, pad.y) == (WORKED_PAD["x"], WORKED_PAD["y"]) == (-314961, 0)
        assert pad.size_top == pad.size_mid == pad.size_bottom == (354331, 374016)
        assert pad.hole == 0
        assert pad.alternate_shapes is not None and pad.alternate_shapes[0] == 9
        assert pad.corner_percentages is not None and pad.corner_percentages[0] == 50
        assert (pad.shape_top, pad.shape_mid, pad.shape_bottom) == (1, 1, 1)
        assert pad.rotation == 0.0 and pad.hole_rotation == 0.0
        assert (pad.paste_mode, pad.solder_mode) == (0, 1)
        assert pad.inner_sizes is not None and len(pad.inner_sizes) == 29
        assert pad.inner_sizes[0] == (354331, 374016)
        assert pad.inner_shapes == (1,) * 29
        assert pad.hole_offsets == ((0, 0),) * 32
        assert pad.hole_shape == 0 and pad.slot_length == 0 and pad.slot_rotation == 0.0
    assert short.tail == (b"", b"")
    assert [len(t) for t in long.tail] == [80, 55]
    assert long.tail == (pattern(80), pattern(55))


def test_through_hole_pad_without_a_layer_block() -> None:
    pad = _pad(long_pad(114, 0, layer=74, hole=393701, plated=True))
    assert pad.hole == 393701 and pad.plated is True
    assert pad.prefix.layer == 74
    assert pad.hole_shape is None and pad.inner_sizes is None and pad.corner_percentages is None
    assert pad.tail == (b"", b"")


def test_pad_of_110_bytes_has_no_hole_rotation() -> None:
    pad = _pad(long_pad(110, 0))
    assert pad.hole_rotation is None and pad.size_top == (354331, 374016)


@pytest.mark.parametrize(("geometry", "layers"), [(109, 0), (114, 595), (114, 1)])
def test_short_pad_is_raw(geometry: int, layers: int) -> None:
    (item,), _, issues = decode_primitives(long_pad(geometry, layers), where="Pads6/Data")
    assert isinstance(item, RawPrimitive) and item.type == 2
    assert [i.code for i in issues] == ["altium.pcb-read.short-record"]


def test_pad_name_and_net() -> None:
    pad = _pad(long_pad(185, 0, name="A12", net=4, component=1))
    assert pad.name == "A12" and pad.prefix.net == 4 and pad.prefix.component == 1
    assert len(pad.tail[0]) == 185 - 114
