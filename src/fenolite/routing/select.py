# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Select the nets that still have open connections, and remove unlocked copper before a rip-up run."""

from __future__ import annotations

import dataclasses
from collections.abc import Collection
from fnmatch import fnmatchcase

from fenolite.model.board import Arc, Track, Via
from fenolite.model.design import Design


def unrouted(
    design: Design,
    open_nets: Collection[str],
    *,
    patterns: tuple[str, ...] = ("*",),
    include_zone_nets: bool = False,
) -> tuple[str, ...]:
    """Return, sorted, the names of the nets to route: two or more pads and an open connection.

    ``open_nets`` holds the names of the nets that have at least one open connection on ``design``
    (``analysis.connectivity``); the caller computes it, because this package may not import
    ``analysis``. Copper of its own does not exclude a net. A net that a zone carries is left out unless
    ``include_zone_nets`` is true. ``patterns`` are ``fnmatch`` globs; one starting with ``!`` excludes.
    """
    board = design.board
    if board is None:
        return ()
    still_open = set(open_nets)
    positive = tuple(pattern for pattern in patterns if not pattern.startswith("!"))
    negative = tuple(pattern[1:] for pattern in patterns if pattern.startswith("!"))
    zone_nets = {zone.net_id for zone in board.zones}
    selected: list[str] = []
    for net in design.circuit.nets:
        name = net.name
        if not any(fnmatchcase(name, pattern) for pattern in positive):
            continue
        if any(fnmatchcase(name, pattern) for pattern in negative):
            continue
        if len(design.by_net.get(name, ())) < 2 or name not in still_open:
            continue
        if not include_zone_nets and net.id in zone_nets:
            continue
        selected.append(name)
    return tuple(sorted(selected))


def rip(design: Design, nets: tuple[str, ...], *, keep: Collection[str] = frozenset()) -> tuple[Design, int]:
    """Remove the tracks, arcs and vias of ``nets`` that are not locked and whose id is not in ``keep``,
    and return their count. Every other item stays, in its order."""
    board = design.board
    if board is None or not nets:
        return design, 0
    requested = set(nets)
    selected = {net.id for net in design.circuit.nets if net.name in requested}

    def stays(item: Track | Arc | Via) -> bool:
        return item.net_id not in selected or item.locked or item.id in keep

    tracks = tuple(item for item in board.tracks if stays(item))
    arcs = tuple(item for item in board.arcs if stays(item))
    vias = tuple(item for item in board.vias if stays(item))
    removed = len(board.tracks) + len(board.arcs) + len(board.vias) - len(tracks) - len(arcs) - len(vias)
    return dataclasses.replace(
        design, board=dataclasses.replace(board, tracks=tracks, arcs=arcs, vias=vias)
    ), removed


__all__ = ["rip", "unrouted"]
