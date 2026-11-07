# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Semantic immutable-board delta checks, before any selected-net filtering (c0368)."""

from __future__ import annotations

import dataclasses
from collections import Counter
from dataclasses import dataclass, replace
from typing import Any

from fenolite.core.ids import content_hash
from fenolite.model.base import Entity
from fenolite.model.board import Arc, Board, Track, Via
from fenolite.model.design import Design
from fenolite.routing.protocol import RoutingResult

Copper = Track | Arc | Via


def _references(design: Design) -> dict[str, str]:
    result = {net.id: f"net:{net.name}" for net in design.circuit.nets}
    result.update({part.id: f"component:{part.ref}" for part in design.circuit.components})
    if design.board:
        result.update({layer.id: f"layer:{layer.name}" for layer in design.board.layers})
    return result


def _plain(value: Any, refs: dict[str, str], *, ordered: bool = True) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            "type": type(value).__name__,
            **{
                f.name: _plain(getattr(value, f.name), refs, ordered=bool(f.metadata.get("ordered", False)))
                for f in dataclasses.fields(value)
                if f.name not in {"id", "native_ids", "provenance"}
            },
        }
    if isinstance(value, dict):
        return {str(k): _plain(v, refs) for k, v in value.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    if isinstance(value, (tuple, list)):
        rows = [_plain(v, refs) for v in value]  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
        # Entity collections are unordered unless explicitly declared ORDERED by the model.
        if not ordered and value and all(isinstance(v, Entity) for v in value):  # pyright: ignore[reportUnknownVariableType]
            rows.sort(key=content_hash)
        return rows
    return refs.get(value, value) if isinstance(value, str) else value


def _signature(item: Copper, design: Design) -> str:
    return content_hash(_plain(item, _references(design)))


@dataclass(frozen=True, slots=True)
class Delta:
    copper: RoutingResult = RoutingResult()
    reason: str = ""


def _protected_board(board: Board) -> Board:
    # A reader adds this internal modeled slot when the first copper item is appended.
    # Preserve every opaque fragment and all other slot declarations.
    ext = {
        backend: replace(
            bag,
            payload=tuple(
                pair
                for pair in bag.payload
                if not (pair[0] == "slot:.:modeled" and pair[1] in {"tracks", "arcs", "vias"})
            ),
        )
        for backend, bag in board.ext.items()
    }
    return replace(board, tracks=(), arcs=(), vias=(), ext=ext)


def board_delta(before: Design, after: Design, selected: tuple[str, ...]) -> Delta:
    """Validate the complete returned board; never restore edits and retain a partial delta.

    Call on the parsed board actually sent to the tool, before backend lifting. Net IDs in
    the returned additions are mapped back to that baseline by name. Opaque state is protected.
    """
    if before.board is None or after.board is None:
        return Delta(reason="external-board-missing")
    a = _protected_board(before.board)
    b = _protected_board(after.board)
    # Headers contain import/file identity, not topology. Everything else stays protected.
    for left, right in ((a, b), (before.circuit, after.circuit), (before.rules, after.rules)):
        if _plain(left, _references(before)) != _plain(right, _references(after)):
            return Delta(reason="external-topology-changed")
    original = (*before.board.tracks, *before.board.arcs, *before.board.vias)
    output = (*after.board.tracks, *after.board.arcs, *after.board.vias)
    remaining = Counter(_signature(item, before) for item in original)
    additions: list[Copper] = []
    baseline_ids = {net.name: net.id for net in before.circuit.nets}
    returned_names = {net.id: net.name for net in after.circuit.nets}
    seen: set[str] = set()
    for item in output:
        signature = _signature(item, after)
        if remaining[signature]:
            remaining[signature] -= 1
            continue
        name = returned_names.get(item.net_id or "", "")
        if name not in selected:
            return Delta(reason="external-unselected-copper")
        if signature in seen or signature in remaining:
            return Delta(reason="external-duplicate-copper")
        seen.add(signature)
        additions.append(replace(item, net_id=baseline_ids[name]))
    if any(remaining.values()):
        return Delta(reason="external-copper-changed")
    return Delta(
        RoutingResult(
            tracks=tuple(t for t in additions if isinstance(t, Track)),
            arcs=tuple(t for t in additions if isinstance(t, Arc)),
            vias=tuple(t for t in additions if isinstance(t, Via)),
        )
    )
