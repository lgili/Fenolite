# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The arc vertices of Altium polygons carried through KiCad (change c0463, task 1.3; capability
design-conversion, "Altium arc polygons are never dropped").

The import gives a polygon whose outline holds arc vertices the ring of ``adapter.arcring.record_outline``:
each arc chorded within the polygon's ``ARCRESOLUTION``. KiCad holds that ring. A conversion to KiCad writes,
in the board property ``PROPERTY`` (``backends.kicad.boardcarrier``), each such polygon's vertices as read
and its ``ARCRESOLUTION``, keyed by the uuid the KiCad writer gives its zone (``pcb.kicad_uuid``; derived
from the polygon's ``UNIQUEID`` when it has one, else from its content). The conversion back finds each
KiCad zone's entry by its uuid (``arc_polygons``); the Altium writer writes the source's vertices while the
zone's outline is still their ring, moved by a translation at most (``ArcPolygon.matches``), and the
outline's chords as a ``changed`` zone otherwise (``lower.ZONE_ARCS_EDITED``).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from fractions import Fraction
from typing import cast

from fenolite.backends.altium.adapter.arcring import ArcPolygon
from fenolite.backends.altium.read.pcbstack import OutlineVertex
from fenolite.model.board import Zone

PROPERTY = "Fenolite.Altium.PolygonArcs"
"""The board property that carries the arc polygons (``boardcarrier``)."""
SCHEMA = "fenolite.altium-polygon-arcs.v0"


def _fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _vertex(vertex: OutlineVertex) -> list[object]:
    return [
        vertex.kind,
        _fraction(vertex.x),
        _fraction(vertex.y),
        _fraction(vertex.cx),
        _fraction(vertex.cy),
        vertex.start_angle,
        vertex.end_angle,
        _fraction(vertex.radius),
    ]


def carrier_text(found: Iterable[tuple[str, str, ArcPolygon]]) -> str:
    """The property's JSON text: one entry per ``(uuid, unique id, polygon)``, sorted by uuid. Lengths are
    exact fractions of the file unit, angles the doubles as read (``repr`` gives each back)."""
    polygons = [
        {
            "uuid": uuid,
            "unique_id": unique,
            "arc_resolution": polygon.arc_resolution,
            "vertices": [_vertex(v) for v in polygon.vertices],
        }
        for uuid, unique, polygon in sorted(found, key=lambda item: item[0])
    ]
    return json.dumps({"schema": SCHEMA, "polygons": polygons}, sort_keys=True, separators=(",", ":"))


def _read_vertex(value: object) -> OutlineVertex | None:
    items = cast("list[object]", value) if isinstance(value, list) else []
    if len(items) != 8:
        return None
    kind, x, y, cx, cy, start, end, radius = items
    texts = (x, y, cx, cy, radius)
    if not isinstance(kind, int) or not all(isinstance(t, str) for t in texts):
        return None
    if not all(isinstance(a, int | float) and not isinstance(a, bool) for a in (start, end)):
        return None
    try:
        fx, fy, fcx, fcy, fr = (Fraction(cast(str, t)) for t in texts)
    except (ValueError, ZeroDivisionError):
        return None
    return OutlineVertex(kind, fx, fy, fcx, fcy, float(cast(float, start)), float(cast(float, end)), fr)


def read_carrier(data: bytes | None) -> dict[str, ArcPolygon]:
    """The carried polygons by KiCad zone uuid; nothing for no property, another schema or text that is no
    carrier. An entry that is not well formed is left out: its zone is then written as its outline."""
    if not data:
        return {}
    try:
        loaded: object = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    root = cast("dict[str, object]", loaded) if isinstance(loaded, dict) else {}
    if root.get("schema") != SCHEMA:
        return {}
    entries = root.get("polygons")
    found: dict[str, ArcPolygon] = {}
    for entry in cast("list[object]", entries) if isinstance(entries, list) else []:
        row = cast("dict[str, object]", entry) if isinstance(entry, dict) else {}
        uuid, resolution, raw = row.get("uuid"), row.get("arc_resolution"), row.get("vertices")
        if not isinstance(uuid, str) or not isinstance(resolution, str):
            continue
        vertices = [_read_vertex(v) for v in (cast("list[object]", raw) if isinstance(raw, list) else [])]
        if len(vertices) < 3 or any(v is None for v in vertices):
            continue
        found[uuid] = ArcPolygon(tuple(cast("list[OutlineVertex]", vertices)), resolution)
    return found


def arc_polygons(zones: Iterable[Zone], carried: Mapping[str, ArcPolygon]) -> dict[str, ArcPolygon]:
    """Per zone id of a board read from KiCad, the carried polygon its KiCad uuid names."""
    found: dict[str, ArcPolygon] = {}
    for zone in zones:
        uuid = zone.native_ids.get("kicad")
        if uuid is not None and uuid in carried:
            found[zone.id] = carried[uuid]
    return found


__all__ = ["PROPERTY", "SCHEMA", "arc_polygons", "carrier_text", "read_carrier"]
