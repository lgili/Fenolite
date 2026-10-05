# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pads and padstacks of imported footprints (capability altium-import, "Footprint instances and pads"
and "Padstacks of imported pads"; ``docs/formats/altium/import.md``, "Pads and padstacks"; change c0043).

A pad's position is brought into the footprint frame by the inverse of the footprint's placement, without
a mirror: a bottom footprint holds mirrored pad coordinates, as one read from a KiCad board does.
"""

from __future__ import annotations

from fenolite.backends.altium.adapter import units
from fenolite.backends.altium.adapter.codes import issue
from fenolite.backends.altium.adapter.context import Context
from fenolite.backends.altium.adapter.ids import Exact, bag
from fenolite.backends.altium.adapter.layers import BOTTOM, MULTI, TOP
from fenolite.backends.altium.read.pcbprims import PadRecord
from fenolite.core.coords import Point, Size
from fenolite.core.units import Udeg
from fenolite.geometry.transform import FULL_TURN, Transform, rotate_point
from fenolite.model.board import HoleShape, Pad, PadKind, PadShape, Padstack, PadstackLayer

SHAPE_ROUND, SHAPE_RECT, SHAPE_OCTAGON = 1, 2, 3
ALTERNATE_ROUNDRECT = 9
MODE_SIMPLE, MODE_TOP_MID_BOTTOM, MODE_FULL = 0, 1, 2
HOLE_SHAPES: dict[int, HoleShape] = {0: "round", 1: "square", 2: "slot"}
EXPANSION_FROM_RULE = 1
MID_LAYERS = 29
"""The number of mid-layer entries of a pad's full stack: Mid-Layer 1 to 29 (layer ids 2 to 30)."""
WILDCARD_ALL, WILDCARD_INNER = "*.Cu", "In*.Cu"


def pad_shape(shape: int, alternate: int | None, size: tuple[int, int]) -> PadShape:
    """The model shape of an Altium shape number, its alternate shape and its size."""
    if shape == SHAPE_ROUND:
        if alternate == ALTERNATE_ROUNDRECT:
            return "roundrect"
        return "circle" if size[0] == size[1] else "oval"
    if shape == SHAPE_RECT:
        return "rect"
    return "custom"


def pad_kind(record: PadRecord) -> PadKind:
    if record.hole > 0:
        return "thru_hole" if record.plated else "np_thru_hole"
    return "smd"


def _alternate(record: PadRecord, index: int) -> int | None:
    shapes = record.alternate_shapes
    return shapes[index] if shapes is not None and index < len(shapes) else None


def _offset(record: PadRecord, index: int, rotation: Udeg) -> Point:
    """The hole offset of layer slot ``index`` in the footprint frame (zero without the sixth subrecord)."""
    offsets = record.hole_offsets
    if offsets is None or index >= len(offsets) or offsets[index] == (0, 0):
        return Point(0, 0)
    x, y = offsets[index]
    return rotate_point(Point(units.pcb_length(x), -units.pcb_length(y)), rotation)


def _slot(layer_id: int) -> int:
    """The index of a layer in the per-layer tables of a pad: 0 the top, 31 the bottom, ``id − 1`` between."""
    return 31 if layer_id == BOTTOM else layer_id - 1


def padstack(
    record: PadRecord,
    ctx: Context,
    *,
    locator: str,
    rotation: Udeg,
    native: str | None,
    multi: bool,
    definition: bool,
    pairs: list[tuple[str, str]],
) -> Padstack | None:
    """The padstack of ``record``, or ``None`` for one shape on all layers with a round hole (or none) and
    no offset. ``rotation`` is the pad's angle relative to its footprint. An unknown stack mode or hole
    shape gives ``altium.import.padstack-unknown``, ``None`` and the pair ``stack_mode``."""
    mode = record.stack_mode
    hole_number = record.hole_shape if record.hole_shape is not None else 0
    if mode not in (MODE_SIMPLE, MODE_TOP_MID_BOTTOM, MODE_FULL) or hole_number not in HOLE_SHAPES:
        ctx.issues.append(
            issue(
                "altium.import.padstack-unknown",
                f"stack mode {mode} or hole shape {hole_number} is outside the table: no padstack",
                locator,
            )
        )
        if ("stack_mode", str(mode)) not in pairs:
            pairs.append(("stack_mode", str(mode)))
        return None
    hole_shape = HOLE_SHAPES[hole_number] if record.hole > 0 else "round"
    exact = Exact(ctx.census)
    hole_length = None
    hole_rotation = 0
    if hole_shape == "slot" and record.slot_length is not None:
        hole_length = exact.length("hole_length", record.slot_length)
    if hole_shape != "round" and record.slot_rotation is not None:
        hole_rotation = (rotation + exact.angle("hole_rotation", record.slot_rotation)) % FULL_TURN
    entries: list[PadstackLayer] = []
    layers = ctx.layers
    chain = layers.chain

    def entry(name: str, shape: int, size: tuple[int, int], slot: int) -> PadstackLayer:
        width = exact.length(f"layers.{name}.w", size[0])
        height = exact.length(f"layers.{name}.h", size[1])
        return PadstackLayer(
            name, pad_shape(shape, _alternate(record, slot), size), Size(width, height),
            _offset(record, slot, rotation),
        )  # fmt: skip

    offsets = record.hole_offsets or ()
    has_offset = any(pair != (0, 0) for pair in offsets)
    if multi and (mode != MODE_SIMPLE or has_offset):
        top = (record.shape_top, record.size_top)
        mid = (record.shape_mid, record.size_mid) if mode != MODE_SIMPLE else top
        bottom = (record.shape_bottom, record.size_bottom) if mode != MODE_SIMPLE else top
        entries.append(entry("F.Cu", *top, 0))
        if definition:
            if mode == MODE_FULL and record.inner_sizes is not None and record.inner_shapes is not None:
                for n in range(1, MID_LAYERS + 1):
                    entries.append(
                        entry(f"In{n}.Cu", record.inner_shapes[n - 1], record.inner_sizes[n - 1], n)
                    )
            else:
                entries.append(entry(WILDCARD_INNER, *mid, 1))
        else:
            for layer_id in chain[1:-1]:
                name = layers.copper[layer_id]
                mid_number = layer_id - TOP  # Mid-Layer n has the id n + 1
                signal = TOP < layer_id < BOTTOM
                if (
                    mode == MODE_FULL
                    and signal
                    and record.inner_sizes is not None
                    and record.inner_shapes is not None
                    and mid_number <= len(record.inner_sizes)
                ):
                    entries.append(
                        entry(
                            name,
                            record.inner_shapes[mid_number - 1],
                            record.inner_sizes[mid_number - 1],
                            _slot(layer_id),
                        )
                    )
                else:
                    entries.append(entry(name, *mid, _slot(layer_id) if signal else 1))
        entries.append(entry("B.Cu", *bottom, 31))
    if not entries and hole_shape == "round":
        return None
    if native is None:
        ident = ctx.ids.content(
            "pst",
            "pad",
            "stack",
            hole_shape,
            hole_length or 0,
            hole_rotation,
            [[e.layer, e.shape, e.size.w, e.size.h, e.offset.x, e.offset.y] for e in entries],
        )
        native_ids: dict[str, str] = {}
    else:
        ident, native_ids = ctx.ids.native("pst", f"{native}:stack")
    return Padstack(
        id=ident,
        native_ids=native_ids,
        provenance=ctx.provenance(locator),
        ext=bag(exact.pairs()),
        layers=tuple(entries),
        hole_shape=hole_shape,
        hole_length=hole_length,
        hole_rotation=hole_rotation,
    )


def pad(
    record: PadRecord,
    ctx: Context,
    *,
    locator: str,
    native: str | None,
    frame: Transform | None,
    footprint_rotation: Udeg = 0,
    net_id: str | None = None,
    definition: bool = False,
) -> Pad:
    """The model pad of ``record``. ``frame`` is the inverse of the footprint's placement (``None``: the
    footprint is at the origin with angle 0, as in a library); ``native`` is the pad's native id, ``None``
    for a content id."""
    exact = Exact(ctx.census)
    absolute = exact.point("position", record.x, record.y)
    position = absolute if frame is None else frame.apply(absolute)
    rotation = (exact.angle("rotation", record.rotation) - footprint_rotation) % FULL_TURN
    layers = ctx.layers
    multi = record.prefix.layer == MULTI
    own = record.prefix.layer
    if multi:
        size, shape_number, slot = record.size_top, record.shape_top, 0
        names: tuple[str, ...] = (WILDCARD_ALL,) if definition else layers.copper_names
    else:
        bottom = own == BOTTOM or (layers.is_copper(own) and own == layers.chain[-1])
        size = record.size_bottom if bottom and record.stack_mode != MODE_SIMPLE else record.size_top
        shape_number = (
            record.shape_bottom if bottom and record.stack_mode != MODE_SIMPLE else record.shape_top
        )
        slot = 0
        names = (layers.name(own),)
    alternate = _alternate(record, slot)
    shape = pad_shape(shape_number, alternate, size)
    pairs: list[tuple[str, str]] = []
    if record.stack_mode != MODE_SIMPLE:
        pairs.append(("stack_mode", str(record.stack_mode)))
    if shape == "roundrect" and record.corner_percentages is not None:
        pairs.append(("corner_percent", str(record.corner_percentages[slot])))
    if shape == "custom":
        pairs.append(("shape", str(shape_number)))
    if record.paste_mode != EXPANSION_FROM_RULE:
        pairs.append(("paste", f"{record.paste_mode},{record.paste_expansion}"))
    if record.solder_mode != EXPANSION_FROM_RULE:
        pairs.append(("mask", f"{record.solder_mode},{record.solder_expansion}"))
    if record.hole > 0 and not record.plated:
        pairs.append(("plated", "0"))
    stack = padstack(
        record,
        ctx,
        locator=locator,
        rotation=rotation,
        native=native,
        multi=multi,
        definition=definition,
        pairs=pairs,
    )
    width, height = exact.length("size.w", size[0]), exact.length("size.h", size[1])
    drill = exact.length("drill", record.hole) if record.hole > 0 else None
    if native is None:
        ident = ctx.ids.content(
            "pad",
            "pad",
            record.name,
            shape,
            [width, height],
            [position.x, position.y],
            rotation,
            drill or 0,
            list(names),
        )
        native_ids: dict[str, str] = {}
    else:
        ident, native_ids = ctx.ids.native("pad", native)
    return Pad(
        id=ident,
        native_ids=native_ids,
        provenance=ctx.provenance(locator),
        ext=bag([*exact.pairs(), *pairs]),
        number=record.name,
        shape=shape,
        size=Size(width, height),
        position=position,
        kind=pad_kind(record),
        rotation=rotation,
        drill=drill,
        layers=names,
        net_id=net_id,
        padstack=stack,
    )


__all__ = ["HOLE_SHAPES", "pad", "pad_kind", "pad_shape", "padstack"]
