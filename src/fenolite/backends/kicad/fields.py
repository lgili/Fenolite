# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint fields in the board frame: where a field is, how to move it, and a place beside the courtyard.

Facts and Fenolite choices: ``docs/formats/kicad/board.md`` ("Footprint fields"). The model keeps a field
in the pad frame (a footprint-local position and an angle relative to the footprint); a script and a DRC
report speak in the board frame. ``field_anchor`` and ``field_angle`` convert one way and ``set_field`` the
other. ``place_outside`` puts a field beside the box of the footprint's courtyard on a chosen side, with its
justification pointing away from the box, so no text extent is needed: KiCad's glyphs are not modelled.
"""

from __future__ import annotations

import dataclasses
from typing import Literal, get_args

from fenolite.backends.kicad.frame import placed_extent
from fenolite.backends.kicad.pcb import FULL_TURN, pad_angle_from_board
from fenolite.core.coords import Point, Size
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm, Udeg, round_half_even_div
from fenolite.geometry.shapes import BBox
from fenolite.geometry.transform import Transform
from fenolite.model.board import FieldJustifyH, FieldJustifyV, FootprintField, FootprintInstance

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-FIELD-FRAME", "H-K-FIELD-JUSTIFY", "H-K-FIELD-OUTSIDE"))
"""Stays ``INFERRED``: the frames are settled on 9.0.9 and 10.0.6, but ``place_outside`` is checked for the
bench references only, and the ink of other strings is not measured."""
OutsideSide = Literal["top", "bottom", "left", "right"]
SIDES: tuple[str, ...] = get_args(OutsideSide)
DEFAULT_GAP: Nm = 250_000
"""The distance between the courtyard box and a field placed outside it (a Fenolite choice)."""


def _field(fp: FootprintInstance, name: str) -> FootprintField:
    for field in fp.fields:
        if field.name == name:
            return field
    raise KeyError(f"footprint {fp.lib_ref or fp.id} has no field named {name!r}")


def field_anchor(fp: FootprintInstance, field: FootprintField) -> Point:
    """The anchor of ``field`` on the board: ``fp.position + R(fp.rotation)·field.position``, with no
    further mirror on the bottom side."""
    return Transform.placement(fp.position, fp.rotation).apply(field.position)


def field_angle(fp: FootprintInstance, field: FootprintField) -> Udeg:
    """The angle of ``field`` on the board: ``(field.rotation + fp.rotation) mod 360°``."""
    return (field.rotation + fp.rotation) % FULL_TURN


def set_field(
    fp: FootprintInstance,
    name: str,
    *,
    anchor: Point | None = None,
    angle: Udeg | None = None,
    layer: str | None = None,
    visible: bool | None = None,
    size: Size | None = None,
    thickness: Nm | None = None,
    justify: tuple[FieldJustifyH, FieldJustifyV] | None = None,
    mirrored: bool | None = None,
) -> FootprintInstance:
    """A copy of ``fp`` whose field ``name`` takes every given value; ``anchor`` and ``angle`` are board-frame
    values. An unknown name raises ``KeyError``.

    The field keeps its stored position when ``field_anchor`` already gives ``anchor``; otherwise it stores
    the inverse placement of ``anchor``, rounded half to even, so a round trip never drifts.
    """
    field = _field(fp, name)
    changes: dict[str, object] = {}
    if anchor is not None and field_anchor(fp, field) != anchor:
        changes["position"] = Transform.placement(fp.position, fp.rotation).inverse().apply(anchor)
    if angle is not None:
        changes["rotation"] = pad_angle_from_board(angle % FULL_TURN, fp.rotation)
    if layer is not None:
        changes["layer"] = layer
    if visible is not None:
        changes["visible"] = visible
    if size is not None:
        changes["size"] = size
    if thickness is not None:
        changes["thickness"] = thickness
    if justify is not None:
        changes["h_justify"], changes["v_justify"] = justify
    if mirrored is not None:
        changes["mirrored"] = mirrored
    new = dataclasses.replace(field, **changes)  # type: ignore[arg-type]
    if new == field:
        return fp
    return dataclasses.replace(fp, fields=tuple(new if f is field else f for f in fp.fields))


def outside_box(fp: FootprintInstance) -> BBox:
    """The bounding box of the footprint's own courtyard face in the board frame (its pad hull when it has no
    courtyard), or the point box at its position when it has neither."""
    points = [point for ring in placed_extent(fp).own for point in ring]
    return (
        BBox.of_points(points) if points else BBox(fp.position.x, fp.position.y, fp.position.x, fp.position.y)
    )


def place_outside(
    fp: FootprintInstance, name: str, *, side: OutsideSide, gap: Nm = DEFAULT_GAP
) -> FootprintInstance:
    """A copy of ``fp`` whose field ``name`` sits beside the courtyard box on ``side``, at board angle 0.

    The anchor lies ``gap`` plus half the field's stroke outside the box, centred on the other axis, and the
    justification points away from the box: the horizontal sense is reversed for a mirrored field, whose
    text runs the other way (``H-K-FIELD-JUSTIFY``).
    """
    if side not in SIDES:
        raise ValueError(f"side must be one of {', '.join(SIDES)}, not {side!r}")
    if gap < 0:
        raise ValueError(f"gap must be at least 0, not {gap}")
    field = _field(fp, name)
    box = outside_box(fp)
    cx = round_half_even_div(box.x0 + box.x1, 2)
    cy = round_half_even_div(box.y0 + box.y1, 2)
    d = gap + (field.thickness or 0) // 2
    away_left: FieldJustifyH = "left" if field.mirrored else "right"
    away_right: FieldJustifyH = "right" if field.mirrored else "left"
    h_justify: FieldJustifyH = "center"
    v_justify: FieldJustifyV = "center"
    if side == "top":
        anchor, v_justify = Point(cx, box.y0 - d), "bottom"
    elif side == "bottom":
        anchor, v_justify = Point(cx, box.y1 + d), "top"
    elif side == "left":
        anchor, h_justify = Point(box.x0 - d, cy), away_left
    else:
        anchor, h_justify = Point(box.x1 + d, cy), away_right
    return set_field(fp, name, anchor=anchor, angle=0, justify=(h_justify, v_justify))


__all__ = [
    "DEFAULT_GAP",
    "EVIDENCE",
    "OutsideSide",
    "field_anchor",
    "field_angle",
    "outside_box",
    "place_outside",
    "set_field",
]
