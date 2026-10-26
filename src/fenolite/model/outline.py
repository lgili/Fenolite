# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every ring of a board outline with its name: the board ring, the cut-outs and the stadiums of the slots
(change c0167; capability design-model, "Board slots").

``outline_items`` is the first layer of the one lowering of an outline: ``geometry.rings.merge_rings``
merges the items that overlap, and the KiCad backend's ``outline.lowered_outline`` and the analyses read
the result. It needs the model and ``core.stadium`` only, so ``analysis``, ``checks`` and ``placement``,
which may not import a backend, can call it.
"""

from __future__ import annotations

from dataclasses import dataclass

from fenolite.core.coords import Point
from fenolite.core.stadium import stadium
from fenolite.model.board import Outline, OutlineSlot

BOARD_RING = "board"


@dataclass(frozen=True, slots=True)
class RingItem:
    """One ring of an outline: its name (``board``, ``cut-out <k>`` or ``slot <name>``), its vertices and,
    per edge, the mid of the arc it is or ``None`` for a line (edge i joins vertex i to vertex i + 1
    mod n)."""

    name: str
    points: tuple[Point, ...]
    mids: tuple[Point | None, ...]

    @property
    def is_slot(self) -> bool:
        return self.name.startswith("slot ")


def cutout_name(k: int) -> str:
    """The name of cut-out ``k`` (counted from 1), as the findings give it."""
    return f"cut-out {k}"


def slot_name(slot: OutlineSlot) -> str:
    """The name of a slot as the findings give it: ``slot <name>``, or ``slot <id>`` when it has none."""
    return f"slot {slot.name or slot.id}"


def slot_ring(slot: OutlineSlot) -> RingItem:
    """The ring of one slot. ``ValueError`` when its size is not a slot's (``core.stadium.check_size``)."""
    found = stadium(slot.center, slot.length, slot.width, slot.rotation)
    mids: list[Point | None] = [None, None, None, None]
    for edge, mid in found.arcs():
        mids[edge] = mid
    return RingItem(slot_name(slot), found.points, tuple(mids))


def outline_items(outline: Outline) -> tuple[RingItem, ...]:
    """The board ring, each cut-out in order, then each slot's stadium in order. An arc of ``Outline.arcs``
    that names no edge is ignored here (``check_outline`` reports it), and so is a slot whose size is not a
    slot's."""
    rings = (tuple(outline.points), *(tuple(ring) for ring in outline.cutouts))
    mids = {(arc.ring, arc.edge): arc.mid for arc in outline.arcs}
    items = [
        RingItem(
            BOARD_RING if r == 0 else cutout_name(r),
            ring,
            tuple(mids.get((r, k)) for k in range(len(ring))),
        )
        for r, ring in enumerate(rings)
    ]
    for slot in outline.slots:
        try:
            items.append(slot_ring(slot))
        except (TypeError, ValueError):
            continue
    return tuple(items)


__all__ = ["BOARD_RING", "RingItem", "cutout_name", "outline_items", "slot_name", "slot_ring"]
