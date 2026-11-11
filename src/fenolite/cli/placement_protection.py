# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project saved board copper into conservative placement attachment diagnostics."""

from collections import defaultdict
from collections.abc import Collection

from fenolite.backends.base import BoardPad
from fenolite.geometry.errors import GeometryError
from fenolite.model.design import Design
from fenolite.tidy.graph import copper_layers, expand_layers, joined_at, net_pieces, pad_piece


def inspect_attachments(
    design: Design, pads: tuple[BoardPad, ...], selected: Collection[str]
) -> dict[str, tuple[str, ...]]:
    """Report direct contact with saved copper, including copper on a different net."""
    board = design.board
    if board is None:
        raise ValueError("attachment inspection needs a board")
    if not selected:
        return {}
    layers = copper_layers(board)
    # Unsupported shapes and netless copper are outside the connectivity projection. Their
    # locations cannot be cleared by a successful check against the represented shapes.
    shaped = net_pieces(design, pads)
    unsupported = (
        bool(shaped.unsupported)
        or any(item.net_id is None for item in (*board.tracks, *board.arcs, *board.vias))
        or any(zone.net_id is None and zone.fills for zone in board.zones)
        or any(graphic.layer in layers for graphic in board.graphics)
    )
    copper = tuple(
        item
        for pieces in shaped.pieces.values()
        for item in pieces
        if item.kind in ("track", "arc", "via", "fill")
    )
    pad_records: dict[str, list[BoardPad]] = defaultdict(list)
    for pad in pads:
        if pad.footprint_id in selected:
            pad_records[pad.footprint_id].append(pad)

    report: dict[str, tuple[str, ...]] = {}
    for fp in board.footprints:
        if fp.id not in selected:
            continue
        expected = {
            pad.id for pad in fp.pads if pad.kind != "np_thru_hole" and expand_layers(pad.layers, layers)
        }
        records = pad_records[fp.id]
        unknown = unsupported or not expected.issubset({pad.pad_id for pad in records if pad.copper})
        touched = False
        for pad in records:
            if pad.kind == "np_thru_hole":
                continue
            try:
                shapes = pad_piece(pad).shapes
            except (GeometryError, ValueError):
                unknown = True
                continue
            if any(joined_at(shape, layer, pad.pad_id, copper) for layer, shape in shapes):
                touched = True
        reasons: list[str] = []
        if touched:
            reasons.append("attached_copper")
        if unknown:
            reasons.append("attachment_unchecked")
        report[fp.id] = tuple(reasons)
    return report
