# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A deterministic two-pad router for examples and tool-free workflows."""

from __future__ import annotations

from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence
from fenolite.core.ids import content_hash, derived_id
from fenolite.model.board import Track
from fenolite.routing.protocol import Router, RouterStatus, RoutingJob, RoutingResult


class DirectRouter:
    """Connect two pads with a straight segment; it checks no clearance and avoids nothing."""

    name = "direct"
    description = "Connects two pads with a straight track; it checks no clearance and avoids nothing."
    sends_data_offsite = False

    def available(self) -> RouterStatus:
        """This built-in router is always available and uses no external tools."""
        return RouterStatus(True, version="builtin")

    def route(self, job: RoutingJob) -> RoutingResult:
        """Route two-pad nets on their first shared copper layer, in stack order, that is not a plane
        layer of the job and, when the net has a layer set, is in it."""
        tracks: list[Track] = []
        routed: list[str] = []
        unrouted: list[str] = []
        for net in job.nets:
            if len(net.pads) != 2:
                unrouted.append(net.name)
                continue
            first, second = net.pads
            shared = next(
                (
                    layer
                    for layer in job.layers
                    if layer in first.layers
                    and layer in second.layers
                    and layer not in job.plane_layers
                    and (net.layers is None or layer in net.layers)
                ),
                None,
            )
            if shared is None:
                unrouted.append(net.name)
                continue
            geometry = (
                first.position.x,
                first.position.y,
                second.position.x,
                second.position.y,
                net.width,
                shared,
            )
            tracks.append(
                Track(
                    id=derived_id("trk", "routing", content_hash(net.name, geometry)),
                    start=Point(first.position.x, first.position.y),
                    end=Point(second.position.x, second.position.y),
                    width=net.width,
                    layer=shared,
                    net_id=net.net_id,
                )
            )
            routed.append(net.name)
        return RoutingResult(
            tracks=tuple(tracks),
            routed=tuple(routed),
            unrouted=tuple(unrouted),
            tool=self.name,
            tool_version="builtin",
            evidence=Evidence(),
        )


_ROUTER: Router = DirectRouter()

__all__ = ["DirectRouter"]
