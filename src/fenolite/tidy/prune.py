# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Prune dangling copper (capability copper-tidy, "Prune dangling copper"; ``docs/copper.md``, "Copper
tidy").

A track or an arc dangles when one of its ends touches nothing else of its net on its layer: the disc of
the track's width at the end touches no other piece and no zone outline of the net. A via dangles when
it is joined on fewer than two copper layers. Each pass takes the dangling items of a net in id order and
removes one only when the net keeps its groups without it (``graph.keeps_groups``); passes repeat until
one removes nothing, so a dead branch goes segment by segment. Locked items and the ids of ``keep`` (the
CLI passes the script copper) are never removed. An item that dangles but joins two groups stays, with
``tidy.kept``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Collection, Sequence

from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.geometry import Thick
from fenolite.model.board import Arc, Track, Via
from fenolite.model.design import Design
from fenolite.tidy.codes import issue
from fenolite.tidy.edits import Edit, TidyResult
from fenolite.tidy.graph import Piece, copper_layers, joined_at, keeps_groups, net_pieces, via_span

_KIND_ORDER = {"track": 0, "arc": 1, "via": 2}
FREE_END = "free-end"
"""The reason of the removal of a track or an arc with a free end."""
VIA_REASON = "via-under-two-layers"
"""The reason of the removal of a via joined on fewer than two copper layers."""


def _free_end(item: Track | Arc, pieces: Sequence[Piece], outlines: Sequence[Piece]) -> Point | None:
    """The first end of ``item`` that touches nothing else of its net, or ``None``."""
    for end in (item.start, item.end):
        if not joined_at(Thick((end,), item.width), item.layer, item.id, pieces, outlines):
            return end
    return None


def _joined_layers(
    via: Via, copper: tuple[str, ...], pieces: Sequence[Piece], outlines: Sequence[Piece]
) -> int:
    disc = Thick((via.position,), via.diameter)
    return sum(1 for layer in via_span(via, copper) if joined_at(disc, layer, via.id, pieces, outlines))


def selected_nets(design: Design, nets: Collection[str] | None) -> list[tuple[str, str]]:
    """``(net id, name)`` of the nets whose names are in ``nets`` (every net for ``None``), by name."""
    chosen = [(net.id, net.name) for net in design.circuit.nets if nets is None or net.name in nets]
    return sorted(chosen, key=lambda pair: (pair[1], pair[0]))


def prune(
    design: Design,
    *,
    pads: Sequence[BoardPad],
    nets: Collection[str] | None = None,
    keep: Collection[str] = (),
) -> TidyResult:
    """``design`` without the dangling copper of the nets named by ``nets`` (every net for ``None``).
    ``pads`` are the board-frame pad records of ``design``; ``keep`` names items that stay."""
    board = design.board
    if board is None:
        return TidyResult(design)
    copper = copper_layers(board)
    shaped = net_pieces(design, pads)
    held: dict[str, Track | Arc | Via] = {
        item.id: item for item in (*board.tracks, *board.arcs, *board.vias) if item.net_id is not None
    }
    kept_ids = set(keep)
    removed: set[str] = set()
    edits: list[Edit] = []
    issues: list[Issue] = []
    for net_id, name in selected_nets(design, nets):
        own = [item for item in held.values() if item.net_id == net_id]
        if not own:
            continue
        if net_id in shaped.unsupported:
            issues.append(
                issue(
                    "tidy.net-skipped",
                    f"net {name} has copper that could not be shaped, so tidy leaves it as it is",
                    where=name,
                )
            )
            continue
        pieces = list(shaped.pieces.get(net_id, ()))
        outlines = shaped.outlines.get(net_id, ())
        movable = sorted(
            (item for item in own if not item.locked and item.id not in kept_ids),
            key=lambda item: (_KIND_ORDER[_kind(item)], item.id),
        )
        blocked: set[str] = set()
        changed = True
        while changed:
            changed = False
            blocked = set()
            for item in movable:
                if item.id in removed:
                    continue
                edit = _dangling(item, name, copper, pieces, outlines)
                if edit is None:
                    continue
                after = [piece for piece in pieces if piece.ident != item.id]
                if not keeps_groups(pieces, after, removed=(item.id,)):
                    blocked.add(item.id)
                    continue
                pieces = after
                removed.add(item.id)
                edits.append(edit)
                changed = True
        for ident in sorted(blocked):
            issues.append(
                issue(
                    "tidy.kept",
                    f"{_kind(held[ident])} {ident} of net {name} has a free end but joins copper of its net "
                    "that would fall apart without it, so it stays",
                    where=ident,
                    hint="trim it by hand, or route the net again",
                )
            )
    if not removed:
        return TidyResult(design, (), tuple(issues))
    pruned = dataclasses.replace(
        board,
        tracks=tuple(item for item in board.tracks if item.id not in removed),
        arcs=tuple(item for item in board.arcs if item.id not in removed),
        vias=tuple(item for item in board.vias if item.id not in removed),
    )
    return TidyResult(dataclasses.replace(design, board=pruned), tuple(edits), tuple(issues))


def _kind(item: Track | Arc | Via) -> str:
    return "via" if isinstance(item, Via) else "arc" if isinstance(item, Arc) else "track"


def _dangling(
    item: Track | Arc | Via,
    name: str,
    copper: tuple[str, ...],
    pieces: Sequence[Piece],
    outlines: Sequence[Piece],
) -> Edit | None:
    """The edit that removes ``item`` when it dangles, else ``None``."""
    if isinstance(item, Via):
        joined = _joined_layers(item, copper, pieces, outlines)
        if joined >= 2:
            return None
        return Edit("prune", VIA_REASON, name, "", item.position, removed=(item.id,))
    free = _free_end(item, pieces, outlines)
    if free is None:
        return None
    return Edit("prune", FREE_END, name, item.layer, free, removed=(item.id,))


__all__ = ["prune", "selected_nets"]
