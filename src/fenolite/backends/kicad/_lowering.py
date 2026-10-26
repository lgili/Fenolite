# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The outline a KiCad board holds: the board ring, the cut-outs and the stadiums of the slots, every
group of overlapping cut-outs and slots merged into one ring (change c0167; capability kicad-file-backend,
"Slots and merged rings in the board file").

``lower_outline`` is the second layer of the one lowering of an outline (``model.outline.outline_items``
gives the rings, ``geometry.rings.merge_groups`` merges them). The board writer, the edge signature
(``_edgesign``), ``outline.board_outline``, ``outline.outline_box``, ``outline.check_outline`` and the
fill digest of the lens all read its ``outline``, so they see one geometry. It imports neither ``pcb`` nor
``outline``. An outline without slots and without overlapping cut-outs is returned as it is, so its bytes
do not change.
"""

# evidence: see pcb, outline

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass

from fenolite.core.coords import Point
from fenolite.geometry.boolean import available_backends
from fenolite.geometry.errors import BackendUnavailable, GeometryError
from fenolite.geometry.rings import MERGE_TOL, CurvedRing, merge_groups, overlap_groups
from fenolite.model.board import Outline, OutlineArc
from fenolite.model.outline import RingItem, outline_items

MERGED_JOIN = " + "
"""How the name of a merged ring joins the names of its items (``slot S2 + slot S3``)."""


@dataclass(frozen=True, slots=True)
class Lowering:
    """The lowered ``outline`` (no slots; ring 0 the board) with one name per ring, in ring order, and the
    groups of overlapping items by their names: ``merged`` into one ring, ``unmerged`` because no
    installed backend unites (the ``geo`` extra is missing), and ``refused`` because their union is not one
    ring without holes. The rings of an unmerged or refused group are left as they are."""

    outline: Outline
    names: tuple[str, ...]
    merged: tuple[tuple[str, ...], ...] = ()
    unmerged: tuple[tuple[str, ...], ...] = ()
    refused: tuple[tuple[str, ...], ...] = ()


def _curved(item: RingItem) -> CurvedRing:
    return CurvedRing(item.points, item.mids)


def _arcs(rings: Sequence[tuple[Point | None, ...]]) -> tuple[OutlineArc, ...]:
    return tuple(
        OutlineArc(r, k, mid) for r, mids in enumerate(rings) for k, mid in enumerate(mids) if mid is not None
    )


def _lower(outline: Outline) -> Lowering:
    items = outline_items(outline)
    inner = items[1:]
    if not outline.slots and len(inner) < 2:
        return Lowering(outline, tuple(item.name for item in items))
    rings = [_curved(item) for item in inner]
    groups = overlap_groups(rings, tol=MERGE_TOL)
    if not outline.slots and all(len(group) == 1 for group in groups):
        return Lowering(outline, tuple(item.name for item in items))
    lowered: list[tuple[str, tuple[Point, ...], tuple[Point | None, ...]]] = []
    merged: list[tuple[str, ...]] = []
    unmerged: list[tuple[str, ...]] = []
    refused: list[tuple[str, ...]] = []
    for group in groups:
        names = tuple(inner[i].name for i in group)
        if len(group) > 1:
            try:
                (found,) = merge_groups([rings[i] for i in group], tol=MERGE_TOL, names=names)
            except BackendUnavailable:
                unmerged.append(names)
            except GeometryError:
                refused.append(names)
            else:
                merged.append(names)
                lowered.append((MERGED_JOIN.join(names), found.ring.points, found.ring.mids))
                continue
        lowered += [(inner[i].name, inner[i].points, inner[i].mids) for i in group]
    board = items[0]
    result = dataclasses.replace(
        outline,
        cutouts=tuple(points for _, points, _ in lowered),
        arcs=_arcs([board.mids, *(mids for _, _, mids in lowered)]),
        slots=(),
    )
    return Lowering(
        result,
        (board.name, *(name for name, _, _ in lowered)),
        tuple(merged),
        tuple(unmerged),
        tuple(refused),
    )


_LAST: list[tuple[Outline, tuple[str, ...], Lowering]] = []


def lower_outline(outline: Outline) -> Lowering:
    """The lowering of ``outline``, remembered for the last outline asked (the writer, the checks and the
    signature ask for it in turn) and for the boolean backends installed at the time."""
    if not outline.slots and len(outline.cutouts) < 2:
        return Lowering(outline, tuple(item.name for item in outline_items(outline)))
    backends = available_backends()
    for known, held, found in _LAST:
        if known is outline and held == backends:
            return found
    found = _lower(outline)
    _LAST[:] = [(outline, backends, found)]
    return found


def lowered_outline(outline: Outline) -> Outline:
    """The outline a KiCad board holds: ``Outline.points``, the cut-outs and the slots' stadiums, each
    group of overlapping ones merged, and no slots. Without the ``geo`` extra an overlapping group is left
    as it is; ``check_outline`` and the writer refuse it."""
    return lower_outline(outline).outline


__all__ = ["MERGED_JOIN", "Lowering", "lower_outline", "lowered_outline"]
