# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board-frame geometry of an imported Altium board: every pad where it lies on the board, and the hull of
each footprint's pads (capability altium-verification, "Board frame of an imported board"; change c0088;
facts: ``docs/formats/altium/import.md``, "Pads and padstacks" and "Board frame of the pads").

The import keeps a pad in the frame of its footprint, as a board read from KiCad does: the pad lies at
``footprint.position + R(footprint.rotation)·pad.position`` with no further mirror, and it is turned by
``footprint.rotation + pad.rotation``. A copper entry is the set of points within ``width / 2`` of an
integer core, so circles, ovals and rounded rectangles are exact. The shapes the import does not resolve
(an octagon, a rounded rectangle without its corner percentage, a rounded rectangle of a per-layer stack)
give the rectangle of their size, which contains them, with ``exact`` false. Coordinates are computed with
rationals and rounded half to even once. Nothing here reads a file.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction

from fenolite.backends.altium.import_evidence import EVIDENCE as IMPORT_EVIDENCE
from fenolite.backends.base import BoardPad, PadCopper, PlacedExtent
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.core.units import Nm, Udeg
from fenolite.geometry import (
    FULL_TURN,
    TRIG_BITS,
    GeometryError,
    Polygon,
    Transform,
    convex_hull,
    cos_sin_fixed,
    round_point,
)
from fenolite.model.board import FootprintInstance, Pad, PadShape, Size
from fenolite.model.design import Design

EVIDENCE = Evidence(IMPORT_EVIDENCE.level, hypotheses=("H-A-IMP-FRAME", "H-A-IMP-PADSTACK"))
"""The level of the import: the frame rests on where the import puts a pad (``H-A-IMP-FRAME``) and on the
shapes and stacks it reads (``H-A-IMP-PADSTACK``)."""
BACKEND = "altium"
CORNER_KEY = "corner_percent"
"""The pair of a pad's ``altium`` bag that holds the corner percentage of a rounded rectangle: 0 to 100,
100 fully round, so the radius is that share of half the shorter side."""
_ONE = 1 << TRIG_BITS
_Frac = tuple[Fraction, Fraction]
_Entry = tuple[tuple[_Frac, ...], int, bool, bool]
"""``(core in the pad frame, width, filled, exact)`` before placement."""


def _box(w: int, h: int) -> tuple[_Frac, ...]:
    x, y = Fraction(w, 2), Fraction(h, 2)
    return ((-x, -y), (x, -y), (x, y), (-x, y))


def corner_radius(size: Size, percent: int) -> Nm:
    """The corner radius of a rounded rectangle of ``size`` with the corner percentage ``percent``:
    ``percent / 100`` of half the shorter side, rounded half to even; the percentage is held to 0 … 100."""
    held = max(0, min(100, percent))
    return round_point(Fraction(held * min(size.w, size.h), 200), 0).x


def shape_entries(shape: PadShape, size: Size, percent: int | None) -> list[_Entry]:
    """The entries of a pad shape of ``size`` in the pad's own frame. ``percent`` is the corner percentage
    of a rounded rectangle, ``None`` when it is not known."""
    w, h = size.w, size.h
    zero = Fraction(0)
    if w <= 0 or h <= 0:
        return []
    if shape in ("circle", "oval") and w == h:
        return [(((zero, zero),), w, False, True)]
    if shape == "circle":  # a disc that contains both sizes
        return [(((zero, zero),), max(w, h), False, False)]
    if shape == "oval":
        half = Fraction(abs(w - h), 2)
        ends = ((-half, zero), (half, zero)) if w > h else ((zero, -half), (zero, half))
        return [(ends, min(w, h), False, True)]
    if shape == "rect":
        return [(_box(w, h), 0, True, True)]
    if shape == "roundrect" and percent is not None:
        radius = corner_radius(size, percent)
        inner_w, inner_h = w - 2 * radius, h - 2 * radius
        if radius == 0:
            return [(_box(w, h), 0, True, True)]
        if inner_w > 0 and inner_h > 0:
            return [(_box(inner_w, inner_h), 2 * radius, True, True)]
        if inner_w > 0:
            return [(((Fraction(-inner_w, 2), zero), (Fraction(inner_w, 2), zero)), 2 * radius, False, True)]
        if inner_h > 0:
            return [(((zero, Fraction(-inner_h, 2)), (zero, Fraction(inner_h, 2))), 2 * radius, False, True)]
        return [(((zero, zero),), 2 * radius, False, True)]
    return [(_box(w, h), 0, True, False)]


def _percent(pad: Pad) -> int | None:
    held = pad.ext.get(BACKEND)
    if held is None:
        return None
    text = next((value for key, value in held.payload if key == CORNER_KEY), None)
    return int(text) if text is not None and text.isascii() and text.isdigit() else None


class _Placement:
    """``p ↦ at + R(θ)·p`` for rational ``p``, rounded half to even once."""

    def __init__(self, at: Point, udeg: Udeg) -> None:
        self.at = at
        self._cos, self._sin = cos_sin_fixed(udeg)

    def apply(self, point: _Frac) -> Point:
        x, y = point
        return round_point(
            self.at.x + (x * self._cos + y * self._sin) / _ONE,
            self.at.y + (-x * self._sin + y * self._cos) / _ONE,
        )


def _entry(layer: str, core: Sequence[Point], width: int, filled: bool, exact: bool) -> PadCopper | None:
    points = tuple(core)
    if filled:
        try:
            points = tuple(Polygon(points).normalize().outer)
        except (GeometryError, ValueError):
            return None
    elif len(points) == 2:
        points = tuple(sorted(points))
    try:
        return PadCopper(layer, points, width, filled, exact)
    except ValueError:
        return None


def _copper(
    pad: Pad, footprint: FootprintInstance, copper_layers: Sequence[str], rotation: Udeg
) -> tuple[PadCopper, ...]:
    """The copper entries of ``pad`` on the copper layers of the board that it names."""
    if pad.kind == "np_thru_hole":
        return ()
    move = Transform.placement(footprint.position, footprint.rotation)
    known = set(copper_layers)
    percent = _percent(pad)
    stack = {entry.layer: entry for entry in pad.padstack.layers} if pad.padstack is not None else {}
    found: list[PadCopper | None] = []
    for layer in pad.layers:
        if layer not in known:
            continue
        held = stack.get(layer)
        if held is None:
            entries, centre = shape_entries(pad.shape, pad.size, percent), pad.position
        else:
            # the corner percentage of a per-layer shape is not in the model: its rectangle contains it
            entries = shape_entries(held.shape, held.size, None)
            centre = Point(pad.position.x + held.offset.x, pad.position.y + held.offset.y)
        placement = _Placement(move.apply(centre), rotation)
        for core, width, filled, exact in entries:
            found.append(_entry(layer, [placement.apply(p) for p in core], width, filled, exact))
    return tuple(entry for entry in found if entry is not None)


def _hole(pad: Pad, position: Point, footprint: FootprintInstance) -> tuple[tuple[Point, ...], Nm | None]:
    """The drilled hole in the board frame: a point, or the two ends of a slot, and the drill size. The
    axis of a slot is the stack's ``hole_rotation``, which the import gives relative to the footprint."""
    if pad.drill is None:
        return (), None
    stack = pad.padstack
    if stack is None or stack.hole_shape != "slot" or stack.hole_length is None:
        return (position,), pad.drill
    half = Fraction(stack.hole_length - pad.drill, 2)
    if half <= 0:
        return (position,), pad.drill
    placement = _Placement(position, (footprint.rotation + stack.hole_rotation) % FULL_TURN)
    zero = Fraction(0)
    ends = (placement.apply((-half, zero)), placement.apply((half, zero)))
    return tuple(sorted(ends)), pad.drill


def _copper_layers(design: Design) -> tuple[str, ...]:
    layers = design.board.layers if design.board is not None else ()
    return tuple(la.name for la in sorted(layers, key=lambda la: la.ordinal) if la.kind == "copper")


def _footprint_pads(
    design: Design, footprint: FootprintInstance, copper_layers: Sequence[str]
) -> tuple[BoardPad, ...]:
    component = next((c for c in design.circuit.components if c.id == footprint.component_id), None)
    ref = component.ref if component is not None else ""
    path = component.path if component is not None else ""
    nets = {net.id: net.name for net in design.circuit.nets}
    move = Transform.placement(footprint.position, footprint.rotation)
    records: list[BoardPad] = []
    for pad in footprint.pads:
        position = move.apply(pad.position)
        rotation = (pad.rotation + footprint.rotation) % FULL_TURN
        copper = _copper(pad, footprint, copper_layers, rotation)
        hole, drill = _hole(pad, position, footprint)
        records.append(
            BoardPad(
                footprint_id=footprint.id,
                ref=ref,
                path=path,
                pad_id=pad.id,
                number=pad.number,
                kind=pad.kind,
                position=position,
                rotation=rotation,
                side=footprint.side,
                layers=tuple(pad.layers),
                net_id=pad.net_id,
                net=nets.get(pad.net_id) if pad.net_id is not None else None,
                copper=copper,
                hole=hole,
                drill=drill,
            )
        )
    return tuple(records)


def board_pads(design: Design, *, issues: list[Issue] | None = None) -> tuple[BoardPad, ...]:
    """One record per pad of every footprint of the board, footprints in board order and pads in footprint
    order: board-frame position and rotation, layers, net, copper entries and hole. An entry that is a
    superset of its shape has ``exact`` false, which the copper check counts; ``issues`` is the protocol's
    parameter, and nothing is added to it."""
    del issues
    footprints = design.board.footprints if design.board is not None else ()
    layers = _copper_layers(design)
    return tuple(pad for footprint in footprints for pad in _footprint_pads(design, footprint, layers))


def _hull(pads: Sequence[BoardPad]) -> tuple[Point, ...]:
    corners: list[Point] = []
    for pad in pads:
        for entry in pad.copper:
            grow = -(-entry.width // 2)
            xs, ys = [p.x for p in entry.core], [p.y for p in entry.core]
            x0, y0, x1, y1 = min(xs) - grow, min(ys) - grow, max(xs) + grow, max(ys) + grow
            corners += [Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1)]
    hull = convex_hull(corners)
    return hull if len(hull) >= 3 else ()


def placed_extents(design: Design, *, issues: list[Issue] | None = None) -> tuple[PlacedExtent, ...]:
    """One extent per footprint of the board, in board order: the hull of its pads' copper on the face of
    its side (``source`` is ``pads``, never exact), or nothing when it has no pad copper (``none``). The
    import reads no courtyard, so no extent has the source ``courtyard``. Nothing is added to ``issues``."""
    del issues
    footprints = design.board.footprints if design.board is not None else ()
    layers = _copper_layers(design)
    extents: list[PlacedExtent] = []
    for footprint in footprints:
        hull = _hull(_footprint_pads(design, footprint, layers))
        own = (hull,) if hull else ()
        top = footprint.side == "top"
        extents.append(
            PlacedExtent(
                footprint.id,
                footprint.side,
                front=own if top else (),
                back=() if top else own,
                source="pads" if hull else "none",
                exact=not hull,
            )
        )
    return tuple(extents)


__all__ = [
    "CORNER_KEY",
    "EVIDENCE",
    "board_pads",
    "corner_radius",
    "placed_extents",
    "shape_entries",
]
