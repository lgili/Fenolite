# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Keep-out lines of the Keep-Out layer carried through a rule area's name (change c0442).

An Altium board may draw a keep-out as a plain track or arc on the Keep-Out layer, without the keep-out flag
(``pcb-records.md``, "Regions and keep-outs"). A conversion to KiCad gives each such stroke the rule area of
the band its width covers (change c0410), which KiCad holds as a zone. Written back from those areas, the
stroke would become a flagged region of the Keep-Out layer: another primitive, which a rule scoped to
regions selects and a rule scoped to tracks does not.

The rule area therefore carries its stroke in its name, ``Altium.KeepOut/<kind>/<numbers>``:

- ``line/x1/y1/x2/y2/w``: a track from (x1, y1) to (x2, y2) of width w;
- ``arc/x1/y1/xm/ym/x2/y2/w``: an arc through its start, a middle point and its end;
- ``circle/cx/cy/ex/ey/w``: a full circle about (cx, cy) through (ex, ey); its band is two rule areas, and
  the second carries the name with ``/2`` added.

Every number is in nanometres, in the frame of the rule area (a footprint's pad frame for its own areas).
The alphabet is the one a rule-area name of the DSL takes (``dsl.items.AREA_NAME``), and a KiCad zone keeps
its name, so the stroke survives both a KiCad file and ``import --to python``. The Altium writer gives a
marked rule area back as its stroke on the Keep-Out layer (``strokes``)."""

# evidence: see lower, pcbdoc

from __future__ import annotations

import dataclasses
import re
from collections.abc import Sequence
from typing import Final

from fenolite.core.coords import Point
from fenolite.model.board import Graphic, Keepout

LAYER: Final = "Altium.KeepOut"
"""The model's name of the Keep-Out layer (``adapter.layers``)."""
LAYER_ID: Final = 56
"""The Altium id of the Keep-Out layer."""
PREFIX: Final = f"{LAYER}/"
_COUNTS: Final = {"line": 5, "arc": 7, "circle": 5}
_NUMBER: Final = r"-?\d+"
_MARKER: Final = re.compile(rf"^{re.escape(PREFIX)}(line|arc|circle)((?:/{_NUMBER})+)$")


def marker(graphic: Graphic, part: int = 0) -> str | None:
    """The rule-area name that carries ``graphic``, a stroke of the Keep-Out layer, for the ``part``-th ring
    of its band; ``None`` for a drawing that is no stroke (a filled shape, an outline, a polygon)."""
    count = {"line": 2, "arc": 3, "circle": 2}.get(graphic.kind)
    if count is None or len(graphic.points) != count or graphic.filled or graphic.width <= 0:
        return None
    numbers = [n for p in graphic.points for n in (p.x, p.y)] + [graphic.width]
    name = PREFIX + graphic.kind + "".join(f"/{n}" for n in numbers)
    return name + "/2" if part else name


def parse(name: str) -> tuple[str, tuple[Point, ...], int, bool] | None:
    """``(kind, points, width, second)`` of a marker name, ``second`` true for the second ring of a circle;
    ``None`` for any other name."""
    found = _MARKER.fullmatch(name)
    if found is None:
        return None
    kind, numbers = found.group(1), [int(n) for n in found.group(2)[1:].split("/")]
    second = kind == "circle" and len(numbers) == _COUNTS[kind] + 1 and numbers[-1] == 2
    if second:
        numbers.pop()
    if len(numbers) != _COUNTS[kind] or numbers[-1] <= 0:
        return None
    points = tuple(Point(numbers[i], numbers[i + 1]) for i in range(0, len(numbers) - 1, 2))
    return kind, points, numbers[-1], second


TOLERANCE: Final = 10
"""How far, in nanometres, a vertex of a marked area may lie from the band of its stroke: a footprint's area
is stored in board coordinates by KiCad and turned back into the pad frame, which rounds."""


def band(kind: str, points: Sequence[Point], width: int, second: bool) -> tuple[Point, ...]:
    """The ring of the band that a stroke covers, as a conversion makes its rule area (``convert``'s
    ``_keepout_rings``): a segment's or an arc's band, or one half of a circle's."""
    from fenolite.geometry.bands import arc_band, segment_band

    if kind == "line":
        return tuple(segment_band(points[0], points[1], width))
    if kind == "arc":
        return tuple(arc_band(points[0], points[1], points[2], width))
    centre, edge = points
    dx, dy = edge.x - centre.x, edge.y - centre.y
    far = Point(centre.x - dx, centre.y - dy)
    if second:
        return tuple(arc_band(far, Point(centre.x + dy, centre.y - dx), edge, width))
    return tuple(arc_band(edge, Point(centre.x - dy, centre.y + dx), far, width))


def _intact(area: Keepout, found: tuple[str, tuple[Point, ...], int, bool]) -> bool:
    """Whether ``area`` is still the rule area its marker gives: it forbids tracks, vias, pads and poured
    copper, as a plain keep-out stroke does, and not footprints, and its outline is its stroke's band
    within ``TOLERANCE``. An area edited since (another outline, another restriction) stays an area."""
    if not (area.no_tracks and area.no_vias and area.no_pads and area.no_copper_pour) or area.no_footprints:
        return False
    try:
        ring = band(*found)
    except (ValueError, ArithmeticError):
        return False
    outline = (
        area.outline[:-1] if len(area.outline) > 1 and area.outline[0] == area.outline[-1] else area.outline
    )
    return len(ring) == len(outline) and all(
        abs(a.x - b.x) <= TOLERANCE and abs(a.y - b.y) <= TOLERANCE
        for a, b in zip(ring, outline, strict=True)
    )


def strokes(areas: Sequence[Keepout]) -> tuple[tuple[Graphic, ...], tuple[Keepout, ...], int]:
    """``(graphics, others, marked)``: the strokes that the marked rule areas of ``areas`` carry, as graphics
    of the Keep-Out layer, one per stroke (a circle's second ring gives none); the other areas, among them a
    marked area that is no longer its stroke's (``_intact``) and a circle whose two rings are not both
    intact; and how many areas gave a stroke."""
    graphics: list[Graphic] = []
    others: list[Keepout] = []
    marked = 0
    held = {area.name: area for area in areas if parse(area.name) is not None}
    for area in areas:
        found = parse(area.name)
        if found is not None and found[0] == "circle":
            pair = (
                (held.get(area.name.removesuffix("/2")), held.get(area.name + "/2"))
                if found[3]
                else (area, held.get(area.name + "/2"))
            )
            whole = [one for one in pair if one is not None]
            if len(whole) != 2 or not all(_intact(one, parse(one.name)) for one in whole):  # type: ignore[arg-type]
                found = None
        elif found is not None and not _intact(area, found):
            found = None
        if found is None:
            others.append(area)
            continue
        marked += 1
        kind, points, width, second = found
        if not second:
            graphics.append(
                Graphic(
                    id=area.id,
                    provenance=area.provenance,
                    kind=kind,  # type: ignore[arg-type]
                    layer=LAYER,
                    points=points,
                    width=width,
                )
            )
    return tuple(graphics), tuple(others), marked


def unmarked(area: Keepout) -> Keepout:
    """``area`` without its marker name, for a writer that does not give the stroke back."""
    return dataclasses.replace(area, name="") if parse(area.name) is not None else area


__all__ = ["LAYER", "LAYER_ID", "PREFIX", "marker", "parse", "strokes", "unmarked"]
