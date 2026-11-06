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

A keep-out track or arc of a copper layer (second flag byte 2, change c0450) is a rule area of that layer
alone, which the import makes of the band its width covers (change c0407). Its name carries the stroke with
its restriction byte first, ``Altium.KeepOut/flag<r>/<kind>/<numbers>`` (``r`` from 0 to 31), and the writer
gives it back as a keep-out track or arc of the area's layer with that byte (``flags``).

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
_MARKER: Final = re.compile(rf"^{re.escape(PREFIX)}(?:flag(\d+)/)?(line|arc|circle)((?:/{_NUMBER})+)$")
EVERY_RESTRICTION: Final = 0x1F
"""The largest restriction byte: every kind restricted."""


def marker(graphic: Graphic, part: int = 0, *, restrictions: int | None = None) -> str | None:
    """The rule-area name that carries ``graphic``, a stroke, for the ``part``-th ring of its band: a stroke
    of the Keep-Out layer without the keep-out flag, or with ``restrictions`` (0 to 31) a keep-out stroke of
    the area's copper layer with that restriction byte (change c0450); ``None`` for a drawing that is no
    stroke (a filled shape, an outline, a polygon)."""
    count = {"line": 2, "arc": 3, "circle": 2}.get(graphic.kind)
    if count is None or len(graphic.points) != count or graphic.filled or graphic.width <= 0:
        return None
    if restrictions is not None and not 0 <= restrictions <= EVERY_RESTRICTION:
        return None
    numbers = [n for p in graphic.points for n in (p.x, p.y)] + [graphic.width]
    flag = "" if restrictions is None else f"flag{restrictions}/"
    name = PREFIX + flag + graphic.kind + "".join(f"/{n}" for n in numbers)
    return name + "/2" if part else name


def flag(name: str) -> int | None:
    """The restriction byte of a marker name of a keep-out stroke (``flag<r>``), else ``None``."""
    found = _MARKER.fullmatch(name)
    if found is None or found.group(1) is None:
        return None
    value = int(found.group(1))
    return value if value <= EVERY_RESTRICTION else None


def parse(name: str) -> tuple[str, tuple[Point, ...], int, bool] | None:
    """``(kind, points, width, second)`` of a marker name, ``second`` true for the second ring of a circle;
    ``None`` for any other name (a restriction byte above 31 among them)."""
    found = _MARKER.fullmatch(name)
    if found is None or (found.group(1) is not None and int(found.group(1)) > EVERY_RESTRICTION):
        return None
    kind, numbers = found.group(2), [int(n) for n in found.group(3)[1:].split("/")]
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


def restricts(area: Keepout, restrictions: int) -> bool:
    """Whether ``area`` forbids what the restriction byte ``restrictions`` forbids, with the bits of
    ``pcblib.KEEPOUT_BITS`` (1 vias, 2 tracks, 4 poured copper, 8 with 16 pads), and not footprints."""
    wanted = (bool(restrictions & 0x01), bool(restrictions & 0x02), bool(restrictions & 0x04))
    held = (area.no_vias, area.no_tracks, area.no_copper_pour)
    return held == wanted and area.no_pads == (restrictions & 0x18 == 0x18) and not area.no_footprints


def intact(area: Keepout, name: str | None = None) -> bool:
    """Whether ``area`` is still the rule area that the marker ``name`` (its own name by default) gives:
    a plain stroke's area forbids tracks, vias, pads and poured copper on any layers, a keep-out stroke's
    what its byte forbids (``restricts``) on one layer, neither forbids footprints, and the outline is
    the stroke's band within ``TOLERANCE``. An area edited since (another outline, another restriction,
    another layer) stays an area."""
    marker_name = area.name if name is None else name
    found = parse(marker_name)
    if found is None:
        return False
    byte = flag(marker_name)
    if byte is not None and len(set(area.layers)) != 1:
        return False
    return restricts(area, EVERY_RESTRICTION if byte is None else byte) and _outline_intact(area, found)


def _outline_intact(area: Keepout, found: tuple[str, tuple[Point, ...], int, bool]) -> bool:
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
    """``(graphics, others, marked)``: the strokes that the marked rule areas of ``areas`` carry, one per
    stroke (a circle's second ring gives none), as graphics of the Keep-Out layer, or of the area's layer for
    a keep-out stroke (``flags`` gives its byte); the other areas, among them a marked area that is no longer
    its stroke's (``intact``) and a circle whose two rings are not both intact; and how many areas gave a
    stroke."""
    graphics: list[Graphic] = []
    others: list[Keepout] = []
    marked = 0
    held = {area.name: area for area in areas if parse(area.name) is not None}
    for area in areas:
        found = parse(area.name)
        if found is not None and found[0] == "circle":
            # the first ring and the second, from either one
            pair = (
                (held.get(area.name.removesuffix("/2")), area)
                if found[3]
                else (area, held.get(area.name + "/2"))
            )
            whole = [one for one in pair if one is not None]
            if len(whole) != 2 or not all(intact(one) for one in whole):
                found = None
        elif found is not None and not intact(area):
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
                    layer=LAYER if flag(area.name) is None else area.layers[0],
                    points=points,
                    width=width,
                )
            )
    return tuple(graphics), tuple(others), marked


def read_stroke(text: str, layer: str) -> tuple[Graphic, int] | None:
    """The stroke and the restriction byte that the import records in a rule area's bag
    (``adapter.copper.STROKE_KEY``: ``<kind>/<x>/<y>/…/<width>/<r>``), as a graphic of ``layer``; ``None``
    for a value that is not one."""
    kind, _, rest = text.partition("/")
    count = {"line": 2, "arc": 3, "circle": 2}.get(kind)
    try:
        numbers = [int(n) for n in rest.split("/")]
    except ValueError:
        return None
    if count is None or len(numbers) != 2 * count + 2:
        return None
    *coordinates, width, restrictions = numbers
    points = tuple(Point(coordinates[i], coordinates[i + 1]) for i in range(0, len(coordinates), 2))
    graphic = Graphic(id="stroke", kind=kind, layer=layer, points=points, width=width)  # type: ignore[arg-type]
    return graphic, restrictions


def flags(areas: Sequence[Keepout]) -> dict[str, int]:
    """The restriction byte of each keep-out stroke that ``strokes`` gives of ``areas``, by the id of the
    stroke (its first area's)."""
    return {area.id: byte for area in areas if (byte := flag(area.name)) is not None}


def unmarked(area: Keepout) -> Keepout:
    """``area`` without its marker name, for a writer that does not give the stroke back."""
    return dataclasses.replace(area, name="") if parse(area.name) is not None else area


__all__ = [
    "EVERY_RESTRICTION",
    "LAYER",
    "LAYER_ID",
    "PREFIX",
    "flag",
    "flags",
    "intact",
    "marker",
    "parse",
    "read_stroke",
    "restricts",
    "strokes",
    "unmarked",
]
