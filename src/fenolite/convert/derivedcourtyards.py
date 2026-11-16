# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The courtyards the Altium import derived, carried through KiCad (change c0489; capability
design-conversion, "A derived courtyard is not written back to Altium").

A conversion to KiCad writes each derived courtyard (``adapter.courtyard``) as a footprint polygon on
``F.CrtYd`` or ``B.CrtYd``, so KiCad's placement and DRC see it, and carries in the board property
``PROPERTY`` (``backends.kicad.boardcarrier``) its footprint's reference, its layer and its points in the
footprint frame. The way back leaves out a courtyard polygon of the footprint of that reference on that
layer whose points are the carried ones within ``TOLERANCE_NM``: the content finds it, not a uuid. One that a
person edited matches no entry and is written as a drawing of the footprint.
"""

from __future__ import annotations

import dataclasses
import json
from typing import cast

from fenolite.backends.altium.adapter.courtyard import LAYERS, is_derived
from fenolite.core.coords import Point
from fenolite.model.board import FootprintInstance
from fenolite.model.design import Design

PROPERTY = "Fenolite.Altium.DerivedCourtyards"
"""The board property that carries the derived courtyards (``boardcarrier``)."""
SCHEMA = "fenolite.altium-derived-courtyards.v0"
TOLERANCE_NM = 1
Carried = tuple[str, str, tuple[Point, ...]]
"""``(reference, layer, points in the footprint frame)``."""


def _refs(design: Design) -> dict[str, str]:
    return {c.id: c.ref for c in design.circuit.components}


def found(design: Design) -> list[Carried]:
    """The derived courtyards of ``design``'s board, by their footprint's reference."""
    board = design.board
    if board is None:
        return []
    refs = _refs(design)
    return [
        (refs.get(fp.component_id, ""), g.layer, tuple(g.points))
        for fp in board.footprints
        for g in fp.graphics
        if is_derived(g)
    ]


def carrier_text(courtyards: list[Carried]) -> str:
    """The property's JSON text, one entry per courtyard, sorted."""
    rows = sorted(
        (
            {"ref": ref, "layer": layer, "points": [[p.x, p.y] for p in points]}
            for ref, layer, points in courtyards
        ),
        key=lambda row: json.dumps(row, sort_keys=True),
    )
    return json.dumps({"schema": SCHEMA, "courtyards": rows}, sort_keys=True, separators=(",", ":"))


def _point(item: object) -> Point | None:
    xy = cast("list[object]", item) if isinstance(item, list) else []
    if len(xy) == 2 and all(type(v) is int for v in xy):
        return Point(cast("int", xy[0]), cast("int", xy[1]))
    return None


def read_carrier(data: bytes | None) -> list[Carried]:
    """The carried courtyards; nothing for no property, another schema or text that is no carrier. An entry
    that is not well formed is left out: its polygon is then written as a drawing."""
    if not data:
        return []
    try:
        loaded: object = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return []
    root = cast("dict[str, object]", loaded) if isinstance(loaded, dict) else {}
    entries = root.get("courtyards") if root.get("schema") == SCHEMA else None
    kept: list[Carried] = []
    for entry in cast("list[object]", entries) if isinstance(entries, list) else []:
        row = cast("dict[str, object]", entry) if isinstance(entry, dict) else {}
        ref, layer, raw = row.get("ref"), row.get("layer"), row.get("points")
        points = [_point(p) for p in cast("list[object]", raw)] if isinstance(raw, list) else []
        if (
            isinstance(ref, str)
            and layer in LAYERS.values()
            and points
            and all(p is not None for p in points)
        ):
            kept.append((ref, cast("str", layer), tuple(p for p in points if p is not None)))
    return kept


def _same(a: tuple[Point, ...], b: tuple[Point, ...]) -> bool:
    return len(a) == len(b) and all(
        abs(p.x - q.x) <= TOLERANCE_NM and abs(p.y - q.y) <= TOLERANCE_NM for p, q in zip(a, b, strict=True)
    )


def without_carried(design: Design, carried: list[Carried]) -> Design:
    """``design`` without each footprint polygon that matches a carried courtyard."""
    board = design.board
    if board is None or not carried:
        return design
    refs = _refs(design)
    footprints: list[FootprintInstance] = []
    for fp in board.footprints:
        ref = refs.get(fp.component_id, "")
        mine = [(layer, points) for r, layer, points in carried if r == ref]
        kept = tuple(
            g
            for g in fp.graphics
            if not (g.kind == "polygon" and any(g.layer == la and _same(g.points, pts) for la, pts in mine))
        )
        footprints.append(fp if len(kept) == len(fp.graphics) else dataclasses.replace(fp, graphics=kept))
    return dataclasses.replace(design, board=dataclasses.replace(board, footprints=tuple(footprints)))


__all__ = ["PROPERTY", "SCHEMA", "TOLERANCE_NM", "carrier_text", "found", "read_carrier", "without_carried"]
