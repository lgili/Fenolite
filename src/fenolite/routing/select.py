# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Select unrouted nets and optionally remove unlocked copper before rip-up routing."""

from __future__ import annotations

import dataclasses
from fnmatch import fnmatchcase

from fenolite.model.design import Design


def unrouted(
    design: Design, *, patterns: tuple[str, ...] = ("*",), include_zone_nets: bool = False
) -> tuple[str, ...]:
    """Return sorted candidate net names with at least two pads and no copper of their own."""
    board = design.board
    if board is None:
        return ()
    positive = tuple(pattern for pattern in patterns if not pattern.startswith("!"))
    negative = tuple(pattern[1:] for pattern in patterns if pattern.startswith("!"))
    copper_nets = {
        item.net_id for item in (*board.tracks, *board.arcs, *board.vias) if item.net_id is not None
    }
    zone_nets = {zone.net_id for zone in board.zones}
    selected: list[str] = []
    for net in design.circuit.nets:
        name = net.name
        if not any(fnmatchcase(name, pattern) for pattern in positive):
            continue
        if any(fnmatchcase(name, pattern) for pattern in negative):
            continue
        if len(design.by_net.get(name, ())) < 2 or net.id in copper_nets:
            continue
        if not include_zone_nets and net.id in zone_nets:
            continue
        selected.append(name)
    return tuple(sorted(selected))


def rip(design: Design, nets: tuple[str, ...]) -> tuple[Design, int]:
    """Remove unlocked tracks, arcs and vias belonging to ``nets`` and return their count."""
    board = design.board
    if board is None or not nets:
        return design, 0
    requested = set(nets)
    selected = {net.id for net in design.circuit.nets if net.name in requested}

    def keep(item: object) -> bool:
        return getattr(item, "net_id", None) not in selected or bool(getattr(item, "locked", False))

    tracks = tuple(item for item in board.tracks if keep(item))
    arcs = tuple(item for item in board.arcs if keep(item))
    vias = tuple(item for item in board.vias if keep(item))
    removed = len(board.tracks) + len(board.arcs) + len(board.vias) - len(tracks) - len(arcs) - len(vias)
    return dataclasses.replace(
        design, board=dataclasses.replace(board, tracks=tracks, arcs=arcs, vias=vias)
    ), removed


__all__ = ["rip", "unrouted"]
