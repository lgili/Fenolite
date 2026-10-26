# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The cut-outs and milled slots of a board outline as the board cut-out regions of an Altium document
(change c0168; capability altium-pcb-writer, "Board cut-out regions"; ``docs/formats/altium/pcb-records.md``,
"Board cut-outs").

``cutout_items`` gives every inner ring of the outline as the KiCad board holds it (``Outline.cutouts``,
then the stadium of each slot, each group of overlapping ones merged into one ring), with the ``where`` a
report names it by: ``cutout/<k>``, ``slot/<name>``, or the items of a merged group joined by ``+``. It
follows the KiCad lowering (``backends.kicad._lowering``) step for step on the same primitives
(``model.outline.outline_items``, ``geometry.rings.overlap_groups`` and ``merge_groups`` at ``MERGE_TOL``),
which this package may not import; a unit test keeps the two equal. The groups are found without the
``geo`` extra; only their union needs it, and a group that cannot be united carries its ``problem``.
"""

# evidence: see pcbdoc

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from fenolite.core.coords import Point
from fenolite.geometry.errors import BackendUnavailable, GeometryError
from fenolite.geometry.rings import MERGE_TOL, CurvedRing, merge_groups, overlap_groups
from fenolite.model.board import Outline
from fenolite.model.design import Design
from fenolite.model.outline import RingItem, outline_items

CUTOUT_TOL = 1_000
"""The polygonisation of a cut-out's arcs in nanometres (1 µm): Fenolite's reader takes a region from
``Regions6``, which holds no arc (``pcb-records.md``, "Board cut-outs"), so every arc is written as
points within this distance of it."""
JOIN = "+"
"""How the ``where`` of a merged group joins the ``where`` of its items (``slot/S2+slot/S3``)."""
NO_UNION = (
    "these cut-outs overlap and no installed geometry backend unites them (pip install 'fenolite[geo]')"
)
NOT_ONE_RING = "the union of these overlapping cut-outs is not one ring without holes"
GATED = (
    "board cut-out regions are written once the maintainer's kit has confirmed them in Altium Designer "
    "(Part S, cases S3 to S5)"
)
"""Why a cut-out is not written while ``pcbdoc.CUTOUT_REGIONS`` is false."""
CUTOUT_HINT = "the KiCad build writes the cut-outs; in Altium draw them as Board Cutout regions"


@dataclass(frozen=True, slots=True)
class CutoutItem:
    """One region to write: where a report names it, the names of the rings it holds (``cut-out 1``,
    ``slot S1``), its ring, and why it cannot be written (``None`` when it can)."""

    where: str
    names: tuple[str, ...]
    ring: CurvedRing
    problem: str | None = None

    def points(self, tol: int = CUTOUT_TOL) -> tuple[Point, ...]:
        """The ring's vertices with every arc polygonised within ``tol``."""
        return self.ring.polygonize(tol)


def unwritten_reason(item: CutoutItem, *, gate: bool) -> str | None:
    """Why ``item`` is not written, without its name, or ``None`` when it is (``gate`` is
    ``pcbdoc.CUTOUT_REGIONS``): the reason a report counts it under (change c0170)."""
    if gate and item.problem is None:
        return None
    return "; ".join(([] if gate else [GATED]) + ([item.problem] if item.problem is not None else []))


def not_written(item: CutoutItem, *, gate: bool) -> str | None:
    """Why ``item`` is not written, naming it, or ``None`` when it is (``gate`` is
    ``pcbdoc.CUTOUT_REGIONS``)."""
    reason = unwritten_reason(item, gate=gate)
    if reason is None:
        return None
    return f"{' + '.join(item.names)} of the board outline is not written: {reason}"


def item_where(name: str) -> str:
    """``cut-out <k>`` → ``cutout/<k>``, ``slot <name>`` → ``slot/<name>``."""
    if name.startswith("cut-out "):
        return "cutout/" + name.removeprefix("cut-out ")
    if name.startswith("slot "):
        return "slot/" + name.removeprefix("slot ")
    return name


def _curved(item: RingItem) -> CurvedRing:
    return CurvedRing(item.points, item.mids)


def cutout_items(outline: Outline | None) -> tuple[CutoutItem, ...]:
    """The inner rings of ``outline`` in the order of the KiCad lowering: each group of overlapping rings
    (``overlap_groups``) is one item, merged when a backend unites it."""
    if outline is None:
        return ()
    inner = outline_items(outline)[1:]
    if not inner:
        return ()
    rings = [_curved(item) for item in inner]
    found: list[CutoutItem] = []
    for group in overlap_groups(rings, tol=MERGE_TOL):
        names = tuple(inner[i].name for i in group)
        where = JOIN.join(item_where(name) for name in names)
        if len(group) == 1:
            found.append(CutoutItem(where, names, rings[group[0]]))
            continue
        members: Sequence[CurvedRing] = [rings[i] for i in group]
        try:
            (merged,) = merge_groups(members, tol=MERGE_TOL, names=names)
        except BackendUnavailable:
            found.append(CutoutItem(where, names, members[0], NO_UNION))
        except GeometryError:
            found.append(CutoutItem(where, names, members[0], NOT_ONE_RING))
        else:
            found.append(CutoutItem(where, names, merged.ring))
    return tuple(found)


EDGE_LAYER = "Edge.Cuts"


def written_rings(model: Design, *, gate: bool) -> dict[str, tuple[Point, ...]]:
    """``where`` → the polygonised ring of each cut-out that a write of ``model`` holds as a region."""
    board = model.board
    items = cutout_items(board.outline if board is not None else None)
    return {item.where: item.points() for item in items if not_written(item, gate=gate) is None}


def read_rings(reading: Design) -> list[tuple[Point, ...]]:
    """The rings of the board cut-out regions of a reading: the import gives each as one ``Edge.Cuts``
    polygon (``adapter.copper.shapes``); the board's own outline is lines and arcs."""
    board = reading.board
    if board is None:
        return []
    return [g.points for g in board.graphics if g.layer == EDGE_LAYER and g.kind == "polygon"]


def _text(ring: Sequence[Point]) -> str:
    return " ".join(f"({p.x},{p.y})" for p in ring)


def _same(a: Sequence[Point], b: Sequence[Point], tol: int) -> bool:
    return len(a) == len(b) and all(
        abs(p.x - q.x) <= tol and abs(p.y - q.y) <= tol for p, q in zip(a, b, strict=True)
    )


CutoutChange = tuple[str, Literal["changed", "removed", "added"], str, str]
"""One difference of ``cutout_differences``: its path, its change (``changed``, ``removed`` or ``added``)
and the two sides' texts, the fields of ``backends.base.Change``, which this module may not import."""


def cutout_differences(
    model: Design, reading: Design, *, gate: bool, tol: int = CUTOUT_TOL
) -> tuple[CutoutChange, ...]:
    """The written cut-out rings of ``model`` against the cut-out rings of ``reading`` (RT-A2; capability
    altium-verification, "Slots and cut-outs in the round trips"): a ring matches a read ring of as many
    vertices, each within ``tol``. An unmatched written ring is paired with an unmatched read ring of as many
    vertices and gives one ``changed``; the rest are ``removed`` and ``added``. Paths ``/cutout/<where>``,
    an added ring numbered in read order."""
    written = written_rings(model, gate=gate)
    read = read_rings(reading)
    free = list(range(len(read)))
    unmatched: list[str] = []
    for where, ring in written.items():
        hit = next((i for i in free if _same(ring, read[i], tol)), None)
        if hit is None:
            unmatched.append(where)
        else:
            free.remove(hit)
    changes: list[CutoutChange] = []
    for where in unmatched:
        ring = written[where]
        pair = next((i for i in free if len(read[i]) == len(ring)), None)
        if pair is None:
            changes.append((f"/cutout/{where}", "removed", _text(ring), ""))
        else:
            free.remove(pair)
            changes.append((f"/cutout/{where}", "changed", _text(ring), _text(read[pair])))
    for n, i in enumerate(free):
        changes.append((f"/cutout/{n}", "added", "", _text(read[i])))
    return tuple(changes)


__all__ = [
    "CUTOUT_HINT",
    "CUTOUT_TOL",
    "GATED",
    "JOIN",
    "CutoutChange",
    "CutoutItem",
    "cutout_differences",
    "cutout_items",
    "read_rings",
    "written_rings",
    "item_where",
    "not_written",
    "unwritten_reason",
]
