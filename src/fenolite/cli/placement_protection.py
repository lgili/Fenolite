# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project saved board copper into conservative placement attachment diagnostics."""

from collections import defaultdict
from collections.abc import Collection

from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.geometry import Arc as GeoArc
from fenolite.geometry import Circle, Thick
from fenolite.geometry.errors import GeometryError
from fenolite.model.board import Graphic
from fenolite.model.design import Design
from fenolite.tidy.graph import (
    ARC_TOL_NM,
    Piece,
    copper_layers,
    expand_layers,
    joined_at,
    net_pieces,
    pad_piece,
    ring,
)


def graphic_piece(graphic: Graphic) -> Piece:
    """The copper of a netted board graphic (change c0486): a closed kind's interior when ``filled``, and
    its stroke of ``width``; ``GeometryError`` or ``ValueError`` when it cannot be shaped."""
    points = graphic.points
    closed = True
    if graphic.kind == "polygon":
        core = ring(points)
    elif graphic.kind == "rect" and len(points) == 2:
        a, b = points
        core = (a, Point(b.x, a.y), b, Point(a.x, b.y))
    elif graphic.kind == "circle" and len(points) == 2:
        core = ring(Circle.from_kicad(points[0], points[1]).polygonize(ARC_TOL_NM))
    elif graphic.kind == "arc" and len(points) == 3:
        core, closed = GeoArc(*points).polygonize(ARC_TOL_NM), False
    elif graphic.kind == "line" and len(points) >= 2:
        core, closed = points, False
    else:
        raise ValueError(f"cannot shape a {graphic.kind} graphic of {len(points)} points")
    if closed and not graphic.filled:
        core = (*core, core[0])  # the stroke of the closed outline
    shape = Thick(core, graphic.width, filled=closed and graphic.filled)
    return Piece("graphic", graphic.id, ((graphic.layer, shape),))


def inspect_attachments(
    design: Design, pads: tuple[BoardPad, ...], selected: Collection[str]
) -> dict[str, tuple[str, ...]]:
    """Report direct contact with saved copper, including copper on a different net. A copper graphic
    with a net is copper of that net (change c0486); one with no net, or one that cannot be shaped, leaves
    every selected part unchecked."""
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
    )
    copper = [
        item
        for pieces in shaped.pieces.values()
        for item in pieces
        if item.kind in ("track", "arc", "via", "fill")
    ]
    for graphic in board.graphics:
        if graphic.layer not in layers:
            continue
        if graphic.net_id is None:
            unsupported = True
            continue
        try:
            copper.append(graphic_piece(graphic))
        except (GeometryError, ValueError):
            unsupported = True
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
