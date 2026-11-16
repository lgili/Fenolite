# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored document of change c0492 (design D1): Fenolite's own two-layer sample with its two
footprints, one on each side, each with its designator and four footprint texts at 0°, 90°, 180° and 270°,
and eight free stroke texts at those angles on ``F.SilkS`` and ``B.SilkS``. Every text is justified left and
bottom, as the import of an Altium document gives it, so the document holds each position as written; the
centred variant tests the writer's corner (design D3).

``ink`` gives the ink box of a text on the board, in the model frame (Y down), from the stroke glyph table
(``silk.extents.estimate``): the box of its justification, mirrored as the text is, turned by its angle and
moved to its anchor."""

from __future__ import annotations

import dataclasses

from _convert import two_layer

from fenolite.backends.altium import lower
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.geometry.transform import Transform, rotate_point
from fenolite.model.board import FieldJustifyH, FieldJustifyV, FootprintField, Size, Text
from fenolite.model.design import Design
from fenolite.silk.extents import TextKey, estimate

MM = 1_000_000
DEG = 1_000_000
ANGLES = (0, 90, 180, 270)
HEIGHT = MM
STROKE = 150_000
Box = tuple[int, int, int, int]
Justify = tuple[FieldJustifyH, FieldJustifyV]


def _text(name: str, at: Point, layer: str, angle: int, justify: Justify) -> Text:
    return Text(
        id=derived_id("txt", "c0492", name),
        text=name,
        position=at,
        layer=layer,
        size=Size(HEIGHT, HEIGHT),
        thickness=STROKE,
        rotation=angle * DEG,
        h_justify=justify[0],
        v_justify=justify[1],
    )


def anchor_design(justify: Justify = ("left", "bottom")) -> Design:
    """The authored design, every text and designator justified ``justify``: names ``F<angle>`` and
    ``B<angle>`` for free texts, ``<ref>-<angle>`` for footprint texts."""
    design = two_layer()
    board = design.board
    assert board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    footprints = []
    for fp in board.footprints:
        ref = refs[fp.component_id]
        silk = "B.SilkS" if fp.side == "bottom" else "F.SilkS"
        fields = tuple(
            dataclasses.replace(
                f, h_justify=justify[0], v_justify=justify[1], rotation=90 * DEG, size=Size(HEIGHT, HEIGHT)
            )
            if f.name == "Reference"
            else f
            for f in fp.fields
        )
        texts = tuple(
            _text(f"{ref}-{a}", Point((i - 1) * 3 * MM, 4 * MM), silk, a, justify)
            for i, a in enumerate(ANGLES)
        )
        footprints.append(dataclasses.replace(fp, fields=fields, texts=texts))
    free = tuple(
        _text(
            f"{side}{a}",
            Point((10 + 8 * i) * MM, (35 if side == "F" else 42) * MM),
            f"{side}.SilkS",
            a,
            justify,
        )
        for side in "FB"
        for i, a in enumerate(ANGLES)
    )
    return dataclasses.replace(
        design, board=dataclasses.replace(board, footprints=tuple(footprints), texts=free)
    )


def document(design: Design) -> bytes:
    return lower.write_design(design, allow_lossy=True).files[f"{design.header.name}.PcbDoc"]


def _box(text: str, item: Text | FootprintField, anchor: Point, angle: int, mirrored: bool) -> Box:
    stroke = item.thickness or STROKE
    found = estimate(TextKey(text, item.size.w, item.size.h, stroke, item.h_justify, item.v_justify))
    assert found is not None
    xs, ys = [], []
    for x, y in ((found.x0, found.y0), (found.x1, found.y0), (found.x0, found.y1), (found.x1, found.y1)):
        turned = rotate_point(Point(-x if mirrored else x, y), angle)
        xs.append(anchor.x + turned.x)
        ys.append(anchor.y + turned.y)
    return min(xs), min(ys), max(xs), max(ys)


def ink(design: Design) -> dict[str, Box]:
    """The ink box of every text and designator of ``design`` by its string (a designator by its
    reference), relative to the position of the footprint ``R1``."""
    board = design.board
    assert board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    origin = next(fp.position for fp in board.footprints if refs.get(fp.component_id) == "R1")
    found: dict[str, Box] = {}
    for fp in board.footprints:
        place = Transform.placement(fp.position, fp.rotation)
        for field in fp.fields:
            if field.name == "Reference":
                at, angle = place.apply(field.position), field.rotation + fp.rotation
                found[refs[fp.component_id]] = _box(refs[fp.component_id], field, at, angle, field.mirrored)
        for text in fp.texts:
            at, angle = place.apply(text.position), text.rotation + fp.rotation
            found[text.text] = _box(text.text, text, at, angle, text.layer.startswith("B."))
    for text in board.texts:
        found[text.text] = _box(text.text, text, text.position, text.rotation, text.layer.startswith("B."))
    return {
        name: (b[0] - origin.x, b[1] - origin.y, b[2] - origin.x, b[3] - origin.y)
        for name, b in found.items()
    }
