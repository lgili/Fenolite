# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pads and padstacks of imported footprints (capability altium-import, "Footprint instances and pads" and
"Padstacks of imported pads"; change c0043)."""

from __future__ import annotations

from collections.abc import Sequence

import _altium_records as rec
import pytest

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.adapter.pads import pad_shape
from fenolite.backends.altium.read.pcbprims import PadRecord
from fenolite.core.coords import Point, Size
from fenolite.core.errors import Issue
from fenolite.model.board import Pad

MIL = rec.MIL
FOUR = (1, 2, 3, 32)


def pads_of(
    records: Sequence[PadRecord], chain: Sequence[int] = (1, 32), issues: list[Issue] | None = None
) -> tuple[Pad, ...]:
    """The pads of one component at (2000 mil, 1500 mil) that holds records."""
    document = rec.document(
        rec.board(chain), components=[rec.component("U1")], nets=["GND"], pads=list(records)
    )
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    assert design.board is not None
    return design.board.footprints[0].pads


def bag(pad: Pad) -> dict[str, str]:
    return dict(pad.ext["altium"].payload) if pad.ext else {}


@pytest.mark.parametrize(
    ("shape", "alternate", "size", "expected"),
    [
        (1, None, (60, 60), "circle"),
        (1, 0, (60, 40), "oval"),
        (2, None, (60, 40), "rect"),
        (1, 9, (60, 40), "roundrect"),
        (3, None, (60, 60), "custom"),
        (7, None, (60, 60), "custom"),
    ],
)
def test_shapes(shape: int, alternate: int | None, size: tuple[int, int], expected: str) -> None:
    assert pad_shape(shape, alternate, size) == expected


def test_kind_drill_number_and_net() -> None:
    at = (2000 * MIL, 1500 * MIL)
    records = [
        rec.pad("A1", at, component=0, net=0),
        rec.pad("2", at, hole=30 * MIL, layer=74, component=0),
        rec.pad("3", at, hole=30 * MIL, layer=74, plated=False, component=0),
    ]
    smd, plated, bare = pads_of(records)
    assert (smd.number, smd.kind, smd.drill, smd.layers) == ("A1", "smd", None, ("F.Cu",))
    assert smd.net_id is not None and plated.net_id is None
    assert (plated.kind, plated.drill, plated.layers) == ("thru_hole", 762_000, ("F.Cu", "B.Cu"))
    assert (bare.kind, bag(bare)) == ("np_thru_hole", {"plated": "0"})
    assert smd.size == Size(1_524_000, 1_524_000) and smd.position == Point(0, 0)


def test_pad_on_multi_layer_lists_every_copper_layer() -> None:
    (pad,) = pads_of([rec.pad("1", hole=30 * MIL, layer=74, component=0)], FOUR)
    assert pad.layers == ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
    (bottom,) = pads_of([rec.pad("1", layer=32, component=0)], FOUR)
    assert bottom.layers == ("B.Cu",)
    (paste,) = pads_of([rec.pad("1", layer=35, component=0)])
    assert paste.layers == ("F.Paste",)


def test_rounded_rectangle_and_octagon_keep_their_numbers() -> None:
    rounded, octagon = pads_of(
        [rec.pad("1", shape=1, size=(60 * MIL, 40 * MIL), alternate=9, corner=50, component=0),
         rec.pad("2", shape=3, component=0)]
    )  # fmt: skip
    assert rounded.shape == "roundrect" and bag(rounded) == {"corner_percent": "50"}
    assert octagon.shape == "custom" and bag(octagon) == {"shape": "3"}
    assert rounded.padstack is None and octagon.padstack is None


def test_mask_and_paste_layers_are_not_listed() -> None:
    import dataclasses

    record = dataclasses.replace(
        rec.pad("1", component=0),
        paste_mode=2,
        paste_expansion=-20_000,
        solder_mode=2,
        solder_expansion=40_000,
    )
    (pad,) = pads_of([record])
    assert pad.layers == ("F.Cu",)
    assert bag(pad) == {"paste": "2,-20000", "mask": "2,40000"}


def test_simple_pad_has_no_padstack() -> None:
    for pad in pads_of([rec.pad("1", component=0), rec.pad("2", hole=30 * MIL, layer=74, component=0)]):
        assert pad.padstack is None


def test_top_middle_and_bottom_sizes() -> None:
    record = rec.pad(
        "1", hole=30 * MIL, layer=74, shape=1, stack_mode=1, size=(60 * MIL, 60 * MIL),
        mid=(50 * MIL, 50 * MIL), bottom=(70 * MIL, 70 * MIL), component=0,
    )  # fmt: skip
    (pad,) = pads_of([record], FOUR)
    assert pad.size == Size(1_524_000, 1_524_000) and pad.padstack is not None
    assert [(layer.layer, layer.size.w) for layer in pad.padstack.layers] == [
        ("F.Cu", 1_524_000),
        ("In1.Cu", 1_270_000),
        ("In2.Cu", 1_270_000),
        ("B.Cu", 1_778_000),
    ]
    assert {layer.shape for layer in pad.padstack.layers} == {"circle"}
    assert pad.padstack.hole_shape == "round" and bag(pad) == {"stack_mode": "1"}
    assert pad.padstack.native_ids["altium"].endswith(":stack")


def test_full_stack_takes_the_mid_layer_the_chain_names() -> None:
    record = rec.pad(
        "1", hole=30 * MIL, layer=74, stack_mode=2, size=(60 * MIL, 60 * MIL), mid=(55 * MIL, 55 * MIL),
        bottom=(70 * MIL, 70 * MIL), inner={0: (40 * MIL, 40 * MIL), 1: (45 * MIL, 45 * MIL)}, component=0,
    )  # fmt: skip
    (pad,) = pads_of([record], (1, 3, 39, 32))  # Mid-Layer 2 (id 3), then a plane
    assert pad.padstack is not None
    assert [(layer.layer, layer.size.w) for layer in pad.padstack.layers] == [
        ("F.Cu", 1_524_000),
        ("In1.Cu", 1_143_000),  # 45 mil: the entry of Mid-Layer 2
        ("In2.Cu", 1_397_000),  # 55 mil: a plane takes the middle values
        ("B.Cu", 1_778_000),
    ]


def test_slot() -> None:
    record = rec.pad(
        "1", hole=40 * MIL, layer=74, hole_shape=2, slot_length=100 * MIL, slot_rotation=90.0, component=0
    )
    (pad,) = pads_of([record])
    assert pad.drill == 1_016_000 and pad.padstack is not None
    assert pad.padstack.hole_shape == "slot" and pad.padstack.hole_length == 2_540_000
    assert pad.padstack.hole_rotation == 90_000_000 and pad.padstack.layers == ()
    (square,) = pads_of([rec.pad("1", hole=30 * MIL, layer=74, hole_shape=1, component=0)])
    assert square.padstack is not None
    assert (square.padstack.hole_shape, square.padstack.hole_length) == ("square", None)


def test_offsets_are_per_layer_in_the_footprint_frame() -> None:
    record = rec.pad(
        "1", hole=30 * MIL, layer=74, rotation=90.0, hole_shape=0,
        offsets={0: (10 * MIL, 0), 31: (0, 20 * MIL)}, component=0,
    )  # fmt: skip
    (pad,) = pads_of([record])
    assert pad.rotation == 90_000_000 and pad.padstack is not None
    top, bottom = pad.padstack.layers
    # (10 mil, 0) in the pad's frame, turned by 90 degrees: straight up, which is −Y in the model.
    assert (top.layer, top.offset) == ("F.Cu", Point(0, -254_000))
    assert (bottom.layer, bottom.offset) == ("B.Cu", Point(-508_000, 0))
    assert top.size == bottom.size == pad.size


def test_unknown_stack_mode_or_hole_shape() -> None:
    issues: list[Issue] = []
    records = [
        rec.pad("1", hole=30 * MIL, layer=74, stack_mode=5, component=0),
        rec.pad("2", hole=30 * MIL, layer=74, hole_shape=4, component=0),
    ]
    first, second = pads_of(records, issues=issues)
    assert first.padstack is None and second.padstack is None
    assert bag(first) == {"stack_mode": "5"} and bag(second) == {"stack_mode": "0"}
    found = [i for i in issues if i.code == "altium.import.padstack-unknown"]
    assert [i.where for i in found] == ["Pads6/Data#0", "Pads6/Data#1"]


def test_pad_ids_from_the_unique_id_table_or_by_name() -> None:
    document = rec.document(
        components=[rec.component("U1")],
        pads=[rec.pad("1", component=0), rec.pad("GND", component=0), rec.pad("GND", component=0)],
        pad_unique_ids={0: "PADUID00"},
    )
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA)
    assert design.board is not None
    assert [pad.native_ids["altium"] for pad in design.board.footprints[0].pads] == [
        "pad:PADUID00",
        "fp:UIDU1:pad:GND:0",
        "fp:UIDU1:pad:GND:1",
    ]
