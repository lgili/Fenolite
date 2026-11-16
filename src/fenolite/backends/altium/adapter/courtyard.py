# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The derived courtyard of an imported footprint (change c0489; capability altium-import, "Derived
courtyard of an imported footprint"; facts: ``docs/formats/altium/import.md``, "Derived courtyard").

Altium has no fixed courtyard layer, and no public source states the kind of a mechanical layer
(``pcb-records.md``, "Mechanical layer kind", ``UNKNOWN``), so every footprint takes the last step of the
order: the convex hull of its known component bodies' outlines and its pads' copper, grown by
``DERIVED_COURTYARD_MARGIN``, in the footprint frame. The growth is the Minkowski sum with the octagon that
circumscribes the circle of the margin, in integers, so it holds the hull grown by the margin.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from math import isqrt

from fenolite.backends.altium.adapter.ids import BACKEND, bag
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.provenance import Provenance
from fenolite.geometry import convex_hull
from fenolite.geometry.transform import Transform
from fenolite.model.board import ComponentBody, Graphic, Pad, Side

DERIVED_COURTYARD_MARGIN = 250_000
"""How far the derived courtyard lies outside the hull, in nm: a Fenolite choice (``import.md``)."""
DERIVED_KEY = "derived"
DERIVED_VALUE = "courtyard"
"""The pair of the ``altium`` bag that marks a derived courtyard: never a source item."""
HYPOTHESIS = "H-A-IMP-COURTYARD"
EVIDENCE = Evidence(Level.INFERRED, hypotheses=(HYPOTHESIS,))
LAYERS: dict[Side, str] = {"top": "F.CrtYd", "bottom": "B.CrtYd"}
LINE_WIDTH = 50_000
"""The stroke of the drawn polygon (0.05 mm, KiCad's usual courtyard line); it is no part of the extent."""


def _octagon(margin: int) -> tuple[tuple[int, int], ...]:
    root = isqrt(2 * margin * margin)
    root += root * root < 2 * margin * margin  # ceil(m·√2): the octagon holds the circle of radius m
    side = root - margin
    return ((margin, side), (side, margin), (-side, margin), (-margin, side),
            (-margin, -side), (-side, -margin), (side, -margin), (margin, -side))  # fmt: skip


def grown_hull(points: Sequence[Point], margin: int = DERIVED_COURTYARD_MARGIN) -> tuple[Point, ...]:
    """The convex hull of ``points`` grown by ``margin``; nothing for fewer than three hull points."""
    octagon = _octagon(margin)
    hull = convex_hull([Point(p.x + dx, p.y + dy) for p in points for dx, dy in octagon])
    return tuple(hull) if len(hull) >= 3 else ()


def pad_corners(pads: Sequence[Pad]) -> list[Point]:
    """The corners of the rectangle of each copper shape of ``pads`` (its size, at the pad's position plus a
    stack layer's offset, turned by the pad's angle) in the footprint frame. The rectangle holds every pad
    shape the model names, as ``frame`` checks one it does not resolve."""
    corners: list[Point] = []
    for pad in pads:
        if pad.kind == "np_thru_hole":
            continue
        shapes = [(pad.size, Point(0, 0))]
        shapes += [(entry.size, entry.offset) for entry in pad.padstack.layers] if pad.padstack else []
        for size, offset in shapes:
            move = Transform.placement(
                Point(pad.position.x + offset.x, pad.position.y + offset.y), pad.rotation
            )
            w, h = -(-size.w // 2), -(-size.h // 2)
            corners += [move.apply(Point(x, y)) for x, y in ((-w, -h), (w, -h), (w, h), (-w, h))]
    return corners


def is_derived(entity: object) -> bool:
    """Whether ``entity`` is a derived courtyard (the pair ``derived=courtyard`` in its ``altium`` bag)."""
    held = getattr(entity, "ext", {}).get(BACKEND)
    return held is not None and (DERIVED_KEY, DERIVED_VALUE) in held.payload


def derived_courtyard(
    owner_id: str,
    side: Side,
    pads: Sequence[Pad],
    bodies: Sequence[ComponentBody],
    graphics: Sequence[Graphic],
    provenance: Provenance,
) -> Graphic | None:
    """The derived courtyard of a footprint, in its frame, or ``None`` when it has a courtyard of its own
    or nothing to derive one from. A body whose projection or heights are unknown (c0099) is left out."""
    if any(graphic.layer in LAYERS.values() for graphic in graphics):
        return None
    points = pad_corners(pads)
    points += [p for b in bodies if not b.projection_unknown and len(b.outline) >= 3 for p in b.outline]
    ring = grown_hull(points) if points else ()
    if not ring:
        return None
    return Graphic(
        id=derived_id("gfx", BACKEND, f"{owner_id}#courtyard"),
        provenance=dataclasses.replace(provenance, evidence=EVIDENCE),
        ext=bag([(DERIVED_KEY, DERIVED_VALUE)]),
        kind="polygon",
        layer=LAYERS[side],
        points=ring,
        width=LINE_WIDTH,
    )


__all__ = [
    "DERIVED_COURTYARD_MARGIN",
    "DERIVED_KEY",
    "DERIVED_VALUE",
    "EVIDENCE",
    "HYPOTHESIS",
    "derived_courtyard",
    "grown_hull",
    "is_derived",
    "pad_corners",
]
