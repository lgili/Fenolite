# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Resolve movable scope before generating poses."""

from collections.abc import Mapping
from dataclasses import dataclass

from fenolite.model.board import Board
from fenolite.placement.constraints import PlacementConstraints


@dataclass(frozen=True, slots=True)
class PlacementScope:
    movable: tuple[str, ...]
    fixed: tuple[tuple[str, tuple[str, ...]], ...]


def placement_scope(
    board: Board,
    selected: tuple[str, ...],
    constraints: PlacementConstraints,
    *,
    attachments: Mapping[str, tuple[str, ...]],
    source_locks: frozenset[str] = frozenset(),
    protected_members: frozenset[str] = frozenset(),
) -> PlacementScope:
    """Combine effective board/source locks and a physical attachment inspection."""
    footprints = {footprint.id: footprint for footprint in board.footprints}
    chosen = frozenset(selected)
    if len(chosen) != len(selected) or chosen - footprints.keys():
        raise ValueError("scope requires distinct existing footprint identities")
    anchors = {reservation.footprint_id for reservation in constraints.reservations if reservation.fixed}
    fixed: list[tuple[str, tuple[str, ...]]] = []
    movable: list[str] = []
    for ident, footprint in sorted(footprints.items()):
        reasons: list[str] = []
        if ident not in chosen:
            reasons.append("outside_scope")
        if footprint.locked:
            reasons.append("board_lock")
        if ident in source_locks:
            reasons.append("source_lock")
        if ident in anchors:
            reasons.append("mechanical_anchor")
        if ident in protected_members:
            reasons.append("protected_member")
        if ident in chosen:
            reasons.extend(attachments.get(ident, ("attachment_unchecked",)))
        if reasons:
            fixed.append((ident, tuple(dict.fromkeys(reasons))))
        else:
            movable.append(ident)
    return PlacementScope(tuple(movable), tuple(fixed))
