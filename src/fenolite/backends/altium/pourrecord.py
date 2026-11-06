# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The record of a board that Altium repoured (change c0463, tasks 3.1 and 4.1;
``docs/formats/altium/pcb-pour.md``, "Records of Altium's repour").

``polygon_summaries`` reads, per polygon of a saved PCB document, what its pour holds: its regions (count,
holes, vertices, area and a SHA-256 of the rings), and the tracks and arcs that name it (a hatched pour). A
record of a board authored for Fenolite (``detail=True``, the kit sample ``pour-hatched``) also lists each
poured track, in file units, so that the hatch can be built from it (task 3.2). A record of a public row
holds aggregates and hashes only: it never copies a stretch of third-party geometry (the coordinator's rule
of 2026-11-06). The rings' hash lets a test that is given the saved document (its folder named by an
environment variable) check that it is the one the record was made from.

Pure: it takes a document's bytes and returns plain data. Reading the files and writing the JSON are the
tool's (``tools/kit_pour_c0463.py``), since this package does no file access.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence

from fenolite.backends.altium.adapter.copper import region_points
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.pcbprims import ArcRecord, RegionRecord, TrackRecord
from fenolite.core.coords import Point

SCHEMA = "fenolite.altium-kit-pour-record.v0"
"""The schema of a record file under ``tests/data/altium/kit/``."""


def _signed(ring: Sequence[Point]) -> int:
    """Twice the signed area of ``ring`` in nm², positive counter-clockwise."""
    return sum(a.x * b.y - b.x * a.y for a, b in zip(ring, (*ring[1:], ring[0]), strict=True))


def _area(ring: Sequence[Point]) -> int:
    """The area of ``ring`` in nm², rounded down."""
    return abs(_signed(ring)) // 2


def _canonical(ring: Sequence[Point]) -> tuple[tuple[int, int], ...]:
    """``ring`` starting at its least point, counter-clockwise: the same ring gives the same tuple however it
    was stored."""
    points = [(p.x, p.y) for p in ring]
    if _signed(ring) < 0:
        points.reverse()
    start = points.index(min(points))
    return tuple(points[start:] + points[:start])


def _ring_text(ring: Sequence[tuple[int, int]]) -> str:
    return ";".join(f"{x},{y}" for x, y in ring)


def _rings_digest(
    rings: Sequence[tuple[tuple[tuple[int, int], ...], tuple[tuple[tuple[int, int], ...], ...]]],
) -> str:
    """The SHA-256 of the rings as ASCII text: the regions sorted, one per line, each its outline then its
    sorted holes, ``|`` between rings, ``;`` between vertices and ``x,y`` in nanometres."""
    lines = ["|".join(_ring_text(ring) for ring in (outer, *holes)) for outer, holes in sorted(rings)]
    return hashlib.sha256("\n".join(lines).encode("ascii")).hexdigest()


def _regions(regions: Iterable[RegionRecord]) -> dict[str, object]:
    rings: list[tuple[tuple[tuple[int, int], ...], tuple[tuple[tuple[int, int], ...], ...]]] = []
    vertices = holes = area = 0
    for region in regions:
        outer = region_points(region.outline)
        inner = [region_points(hole) for hole in region.holes]
        if len(outer) < 3:
            continue
        inner = [hole for hole in inner if len(hole) >= 3]
        vertices += len(outer) + sum(len(hole) for hole in inner)
        holes += len(inner)
        area += _area(outer) - sum(_area(hole) for hole in inner)
        rings.append((_canonical(outer), tuple(sorted(_canonical(hole) for hole in inner))))
    return {
        "regions": len(rings),
        "holes": holes,
        "vertices": vertices,
        "area_nm2": area,
        "rings_sha256": _rings_digest(rings),
    }


def _gcd(a: int, b: int) -> int:
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a


def _direction(track: TrackRecord) -> str:
    """The direction of a track as ``dx:dy``, the least whole vector along it with ``dx`` above 0 (or ``dx``
    0 and ``dy`` above 0): exact, and the same for a track and its reverse; ``0:0`` for a point."""
    dx, dy = track.x2 - track.x1, track.y2 - track.y1
    common = _gcd(dx, dy)
    if common == 0:
        return "0:0"
    dx, dy = dx // common, dy // common
    if dx < 0 or (dx == 0 and dy < 0):
        dx, dy = -dx, -dy
    return f"{dx}:{dy}"


def _tracks(tracks: Sequence[TrackRecord], arcs: Sequence[ArcRecord], *, detail: bool) -> dict[str, object]:
    directions: dict[str, int] = {}
    widths: dict[str, int] = {}
    for track in tracks:
        directions[_direction(track)] = directions.get(_direction(track), 0) + 1
        widths[str(track.width)] = widths.get(str(track.width), 0) + 1
    found: dict[str, object] = {
        "tracks": len(tracks),
        "arcs": len(arcs),
        "directions": dict(sorted(directions.items())),
        "widths": dict(sorted(widths.items())),
    }
    if detail:
        found["track_list"] = sorted([t.x1, t.y1, t.x2, t.y2, t.width] for t in tracks)
        found["arc_list"] = sorted(
            [a.cx, a.cy, a.radius, round(a.start_angle, 6), round(a.end_angle, 6), a.width] for a in arcs
        )
    return found


def polygon_summaries(document: PcbDocument, *, detail: bool = False) -> list[dict[str, object]]:
    """One entry per polygon of ``document``, in record order: its name, ``LAYER``, ``HATCHSTYLE``,
    ``GRIDSIZE``, ``TRACKWIDTH`` and ``POURINDEX`` as read, what its regions hold and the tracks and arcs that
    name it; with ``detail``, each track and arc too (lengths in file units, as the record stores them)."""
    tracks = [t for t in document.tracks if isinstance(t, TrackRecord)]
    arcs = [a for a in document.arcs if isinstance(a, ArcRecord)]
    out: list[dict[str, object]] = []
    for index, polygon in enumerate(document.polygons):
        record = polygon.record
        entry: dict[str, object] = {
            "index": index,
            "name": polygon.name,
            "layer": record.get("LAYER") or "",
            "hatch_style": record.get("HATCHSTYLE") or "",
            "grid_size": record.get("GRIDSIZE") or "",
            "track_width": record.get("TRACKWIDTH") or "",
            "pour_index": record.get("POURINDEX") or "",
            "shelved": record.get("SHELVED") or "",
        }
        entry.update(_regions(document.regions_of(index)))
        mine = [t for t in tracks if t.prefix.polygon == index]
        entry.update(_tracks(mine, [a for a in arcs if a.prefix.polygon == index], detail=detail))
        out.append(entry)
    return out


def document_record(data: bytes, name: str, *, detail: bool = False) -> dict[str, object]:
    """The record of the saved document ``data`` named ``name``: its name, SHA-256 and size, and its
    polygons."""
    document = read_pcbdoc(data, file=name)
    return {
        "file": name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "polygons": polygon_summaries(document, detail=detail),
    }


__all__ = ["SCHEMA", "document_record", "polygon_summaries"]
