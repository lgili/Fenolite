# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Validate and merge router-proposed copper into an immutable design."""

from __future__ import annotations

import dataclasses

from fenolite.core.errors import ConsistencyError, Issue
from fenolite.core.ids import content_hash, derived_id
from fenolite.model.board import Arc, Track, Via
from fenolite.model.design import Design
from fenolite.routing.protocol import RoutingResult


class RoutingError(ConsistencyError):
    """One or more invalid copper items prevented the merge; ``issues`` describes each item."""

    def __init__(self, issues: tuple[Issue, ...]) -> None:
        self.issues = issues
        super().__init__("; ".join(issue.message for issue in issues))


def _with_id(item: Track | Arc | Via, net_names: dict[str, str]) -> Track | Arc | Via:
    if item.id:
        return item
    net_name = net_names.get(item.net_id or "", "")
    if isinstance(item, Track):
        prefix = "trk"
        geometry = (item.start.x, item.start.y, item.end.x, item.end.y, item.width, item.layer)
    elif isinstance(item, Arc):
        prefix = "arc"
        geometry = (
            item.start.x,
            item.start.y,
            item.mid.x,
            item.mid.y,
            item.end.x,
            item.end.y,
            item.width,
            item.layer,
        )
    else:
        prefix = "via"
        geometry = (
            item.position.x,
            item.position.y,
            item.diameter,
            item.drill,
            item.layers,
            item.via_type,
        )
    return dataclasses.replace(item, id=derived_id(prefix, "routing", content_hash(net_name, geometry)))


def apply(design: Design, result: RoutingResult) -> Design:
    """Append valid routed copper; reject the entire result when any item is invalid."""
    board = design.board
    if board is None:
        raise RoutingError((Issue("route.bad-item", "error", "design has no board", design.id),))
    net_names = {net.id: net.name for net in design.circuit.nets}
    copper_layers = {layer.name for layer in board.layers if layer.kind == "copper"}
    existing_ids = {entity.id for entity in design.entities()}
    additions: list[Track | Arc | Via] = []
    issues: list[Issue] = []
    candidates = (*result.tracks, *result.arcs, *result.vias)
    candidate_ids: set[str] = set()
    for original in candidates:
        item = _with_id(original, net_names)
        invalid: list[str] = []
        if item.net_id not in net_names:
            invalid.append("unknown net")
        layers = item.layers if isinstance(item, Via) else (item.layer,)
        if any(layer not in copper_layers for layer in layers):
            invalid.append("non-copper board layer")
        if item.id in existing_ids or item.id in candidate_ids:
            invalid.append("duplicate item id")
        if invalid:
            issues.append(
                Issue(
                    "route.bad-item",
                    "error",
                    ", ".join(invalid),
                    item.id or "routing-result",
                )
            )
        else:
            additions.append(item)
            candidate_ids.add(item.id)
    if issues:
        raise RoutingError(tuple(issues))
    tracks = tuple(item for item in additions if isinstance(item, Track))
    arcs = tuple(item for item in additions if isinstance(item, Arc))
    vias = tuple(item for item in additions if isinstance(item, Via))
    return dataclasses.replace(
        design,
        board=dataclasses.replace(
            board,
            tracks=(*board.tracks, *tracks),
            arcs=(*board.arcs, *arcs),
            vias=(*board.vias, *vias),
        ),
    )


__all__ = ["RoutingError", "apply"]
