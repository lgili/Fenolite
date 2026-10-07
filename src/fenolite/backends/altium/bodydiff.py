# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The kind ``body`` of the Altium round trips (capability altium-verification, "Component bodies in the
round trips"; change c0121; ``H-A-PCBX-BODY-READBACK``).

Component bodies are written on request only, so they are no kind of ``roundtrip.RT_A2_SCOPE``.
``body_differences`` compares the bodies of a model that holds exactly the bodies that were written with
those of the reading of the written document, inside ``roundtrip.BODY_SCOPE``, and gives plain values
(``roundtrip.body_changes`` makes the ``Change`` values of a report from them): RT-A2 hands it the model
a build stored, and RT-A3 the first reading without the bodies that the write left out. Fenolite reads
what Fenolite wrote: a comparison that holds says that the writer and the import agree, not that Altium reads
the body.
"""

# evidence: see roundtrip

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import fenolite.backends.altium.pcbrecords as rec
from fenolite.backends.altium.roundtrip import BODY_SCOPE
from fenolite.model.design import Design


def _ring(points: Sequence[Any]) -> list[tuple[int, int]]:
    """An outline as the writer takes it: without equal neighbours and without a repeated last point."""
    ring: list[tuple[int, int]] = []
    for point in points:
        if not ring or ring[-1] != (point.x, point.y):
            ring.append((point.x, point.y))
    while len(ring) > 1 and ring[-1] == ring[0]:
        ring.pop()
    return ring


def _same_ring(a: Sequence[tuple[int, int]], b: Sequence[tuple[int, int]], tolerance: int) -> bool:
    """Whether two rings hold the same points in the same order, from any start, within ``tolerance``."""
    if len(a) != len(b):
        return False
    if not a:
        return True
    count = len(a)
    return any(
        all(
            abs(a[i][0] - b[(i + turn) % count][0]) <= tolerance
            and abs(a[i][1] - b[(i + turn) % count][1]) <= tolerance
            for i in range(count)
        )
        for turn in range(count)
    )


def body_view(body: Any, *, bottom: bool) -> dict[str, Any]:
    """The fields of ``BODY_SCOPE`` of one body as they are compared: the outline as a ring that starts at
    its smallest point, and the layer as the import names the layer that the writer's rule gives the body
    (``pcbrecords.body_layer``), so a body without a layer equals its default layer."""
    ring = _ring(body.outline)
    if ring:
        start = ring.index(min(ring))
        ring = ring[start:] + ring[:start]
    return {
        "kind": body.kind,
        "height": body.height,
        "standoff": body.standoff,
        "outline": [list(point) for point in ring],
        "layer": f"Mech.{rec.body_layer(body.layer, bottom=bottom) - 56}",
        "name": body.name,
    }


def _same_body(a: Mapping[str, Any], b: Mapping[str, Any], tolerance: int) -> bool:
    return (
        all(a[name] == b[name] for name in ("kind", "layer", "name"))
        and abs(a["height"] - b["height"]) <= tolerance
        and abs(a["standoff"] - b["standoff"]) <= tolerance
        and _same_ring([tuple(p) for p in a["outline"]], [tuple(p) for p in b["outline"]], tolerance)
    )


def _bodies_by_owner(design: Design) -> dict[str, list[dict[str, Any]]]:
    """Footprint key → the views of its bodies, in order. The key is the component's reference, numbered
    when it repeats, as the model difference keys a footprint."""
    board = design.board
    if board is None:
        return {}
    refs = {component.id: component.ref for component in design.circuit.components}
    seen: dict[str, int] = {}
    found: dict[str, list[dict[str, Any]]] = {}
    for footprint in board.footprints:
        key = refs.get(footprint.component_id, footprint.component_id)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            key = f"{key}#{seen[key] - 1}"
        bottom = footprint.side == "bottom"
        found[key] = [body_view(body, bottom=bottom) for body in footprint.bodies]
    return found


BodyDifference = tuple[str, str, Mapping[str, Any] | None, Mapping[str, Any] | None]
"""One difference of the kind ``body``: the path ``/body/<n>``, the change (``changed``, ``removed`` or
``added``), and the compared view of each side (``None`` for none)."""


def body_differences(reference: Design, reading: Design) -> tuple[BodyDifference, ...]:
    """The differences of the kind ``body`` between ``reference`` (a model that holds exactly the bodies
    that were written) and ``reading`` (the model of the written document), inside ``BODY_SCOPE``: the
    bodies of each footprint are compared in order, lengths within the scope's tolerance and the outline as
    a ring. Each difference has the path ``/body/<n>``, ``n`` counting the bodies of ``reference`` and then
    those that only ``reading`` holds."""
    tolerance = BODY_SCOPE.length_tolerance
    mine, theirs = _bodies_by_owner(reference), _bodies_by_owner(reading)
    changes: list[BodyDifference] = []
    number = 0
    extra: list[dict[str, Any]] = []
    for owner, bodies in mine.items():
        read = theirs.get(owner, [])
        for index, view in enumerate(bodies):
            if index >= len(read):
                changes.append((f"/body/{number}", "removed", view, None))
            elif not _same_body(view, read[index], tolerance):
                changes.append((f"/body/{number}", "changed", view, read[index]))
            number += 1
        extra += read[len(bodies) :]
    for owner, read in theirs.items():
        if owner not in mine:
            extra += read
    for view in extra:
        changes.append((f"/body/{number}", "added", None, view))
        number += 1
    return tuple(changes)


def body_count(design: Design) -> int:
    """The component bodies that the footprints of ``design`` hold."""
    board = design.board
    return sum(len(footprint.bodies) for footprint in board.footprints) if board is not None else 0


__all__ = ["BodyDifference", "body_count", "body_differences", "body_view"]
