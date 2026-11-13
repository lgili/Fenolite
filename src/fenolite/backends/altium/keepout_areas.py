# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rule areas of the drawings of an Altium document's Keep-Out layer (change c0501, design D3).

The import keeps the drawings of the Keep-Out layer as graphics of ``Altium.KeepOut``. A conversion to KiCad
(``convert.altium_to_kicad.keepouts``) and the routing world (``AltiumBackend.rule_areas``) both make their
rule areas here, so the two cannot disagree: a filled shape one area, a keep-out track or arc the band of
its width (change c0407), on every copper layer, forbidding what the restrictions value of its keep-out
record forbids (change c0420), or all four kinds for a drawing without one (change c0410;
``pcb-records.md``, "Regions and keep-outs"; ``H-A-PCBX-KEEPOUT``, INFERRED)."""

from __future__ import annotations

import re
from typing import Any

from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.model.board import Keepout, placed_keepout
from fenolite.model.board import rule_areas as model_rule_areas
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-PCBX-KEEPOUT",))
"""The restrictions of a Keep-Out layer area: ``INFERRED`` (``pcb-records.md``, "Regions and keep-outs")."""

KEEPOUT_LAYER = "Altium.KeepOut"
ALL_RESTRICTIONS = 0x1F
"""The restrictions of a drawing of the Keep-Out layer whose value is not known (change c0410): all."""
KEEPOUT_RECORD = re.compile(r"(Tracks6|Arcs6|Fills6|Regions6)/Data#(\d+)")


def restriction_flags(value: int) -> tuple[bool, bool, bool, bool]:
    """The restrictions of the rule areas a drawing of the Keep-Out layer gives, from the restrictions value
    of its keep-out record (S-1711, change c0420, N3): 1 vias, 2 tracks, 4 poured copper, 8 and 16 together
    pads (``pcb-records.md``, "Regions and keep-outs"). (vias, tracks, poured copper, pads)."""
    return bool(value & 0x01), bool(value & 0x02), bool(value & 0x04), value & 0x18 == 0x18


def keepout_rings(graphic: Any) -> list[tuple[Any, ...]] | None:
    """The rings a drawing on the Keep-Out layer keeps out (change c0407): a filled polygon or rectangle (a
    region or a fill) and a closed outline of width 0 their outline; a line, an arc, a circle and each side of
    an outline drawn with a width the band that width covers, one ring per stroke, as KiCad 10.0.6 imports
    keep-out tracks (``pcb-records.md``, "Regions and keep-outs"). ``None`` for a drawing of another kind;
    ``GeometryError`` or ``ValueError`` when it covers no area."""
    from fenolite.geometry.bands import arc_band, segment_band
    from fenolite.geometry.polygon import Polygon

    points = tuple(graphic.points)
    if graphic.kind == "rect" and len(points) == 2:
        a, b = points
        points = (a, Point(b.x, a.y), b, Point(a.x, b.y))
    if graphic.kind in ("polygon", "rect") and (graphic.filled or graphic.width <= 0):
        return [Polygon(points[:-1] if points[0] == points[-1] else points).outer]
    if graphic.kind in ("polygon", "rect"):
        ring = points[:-1] if points[0] == points[-1] else points
        return [segment_band(a, ring[(i + 1) % len(ring)], graphic.width) for i, a in enumerate(ring)]
    if graphic.kind == "line" and len(points) == 2:
        return [segment_band(points[0], points[1], graphic.width)]
    if graphic.kind == "arc" and len(points) == 3:
        return [arc_band(points[0], points[1], points[2], graphic.width)]
    if graphic.kind == "circle" and len(points) == 2:
        centre, edge = points
        dx, dy = edge.x - centre.x, edge.y - centre.y
        far = Point(centre.x - dx, centre.y - dy)
        return [
            arc_band(edge, Point(centre.x - dy, centre.y + dx), far, graphic.width),
            arc_band(far, Point(centre.x + dy, centre.y - dx), edge, graphic.width),
        ]
    return None


def record_value(graphic: Any, document: Any) -> int | None:
    """The restrictions value of the keep-out record of ``graphic`` in ``document`` (a read PCB document),
    found by its provenance locator; ``None`` when the record is not found or is no keep-out (change c0420,
    N2 and N3; ``adapter.copper.keepout_layer_restrictions``)."""
    from fenolite.backends.altium.adapter.copper import keepout_layer_restrictions

    where = graphic.provenance
    match = KEEPOUT_RECORD.fullmatch(where.locator if where else "")
    if match is None or document is None:
        return None
    records = {"Tracks6": document.tracks, "Arcs6": document.arcs, "Fills6": document.fills}
    records["Regions6"] = document.regions
    items, index = records[match.group(1)], int(match.group(2))
    return keepout_layer_restrictions(items[index]) if index < len(items) else None


def areas_of(graphic: Any, copper: tuple[str, ...], value: int | None) -> list[Keepout] | None:
    """The rule areas of one drawing of the Keep-Out layer on the layers ``copper``, one per ring of
    ``keepout_rings`` and unnamed, forbidding what ``value`` forbids (``ALL_RESTRICTIONS`` when ``None``);
    ``None`` for a drawing of a kind without an outline. Raises ``GeometryError`` or ``ValueError`` for a
    drawing that covers no area."""
    rings = keepout_rings(graphic)
    if rings is None:
        return None
    no_vias, no_tracks, no_copper_pour, no_pads = restriction_flags(
        ALL_RESTRICTIONS if value is None else value
    )
    return [
        Keepout(
            id=derived_id("kpo", "conversion", graphic.id if index == 0 else f"{graphic.id}:{index}"),
            outline=ring,
            layers=copper,
            no_tracks=no_tracks,
            no_vias=no_vias,
            no_pads=no_pads,
            no_copper_pour=no_copper_pour,
        )
        for index, ring in enumerate(rings)
    ]


def rule_areas(design: Design, document: Any) -> tuple[Keepout, ...]:
    """Every rule area in force on the board of ``design`` in its frame: the model's own
    (``model.board.rule_areas``) and those of the drawings of the Keep-Out layer, a footprint's placed in
    the board's frame; ``document`` is the read PCB document whose records give the restrictions. A drawing
    that covers no area gives none (the conversion records it as a loss)."""
    from fenolite.geometry.errors import GeometryError

    board = design.board
    if board is None:
        return ()
    copper = tuple(layer.name for layer in board.layers if layer.kind == "copper")
    found = list(model_rule_areas(board))

    def own(graphic: Any) -> list[Keepout]:
        try:
            return areas_of(graphic, copper, record_value(graphic, document)) or []
        except (GeometryError, ValueError, IndexError, TypeError):
            return []

    found += [area for g in board.graphics if g.layer == KEEPOUT_LAYER for area in own(g)]
    for fp in board.footprints:
        found += [
            placed_keepout(fp, area) for g in fp.graphics if g.layer == KEEPOUT_LAYER for area in own(g)
        ]
    return tuple(found)


__all__ = [
    "ALL_RESTRICTIONS",
    "KEEPOUT_LAYER",
    "KEEPOUT_RECORD",
    "areas_of",
    "keepout_rings",
    "record_value",
    "restriction_flags",
    "rule_areas",
]
