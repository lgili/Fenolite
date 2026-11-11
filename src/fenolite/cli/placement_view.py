# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Read-only placement overlays on the source board of a saved proposal."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from fenolite.backends.base import BoardFrame
from fenolite.core.coords import Point
from fenolite.core.units import round_half_even_div
from fenolite.geometry import ceil_sqrt
from fenolite.model import canonical
from fenolite.model.design import Design
from fenolite.placement.intent import probe_intent_legs
from fenolite.placement.optimization_contract import PlacementOptimization, candidate_id
from fenolite.placement.pose_projection import project_poses
from fenolite.placement.protection import PlacementScope
from fenolite.placement.topology import PadIdentity

_COLORS = ("#2daeff", "#ffae45", "#f36abf", "#55dba8")


@dataclass(frozen=True, slots=True)
class PlacementOverlay:
    source_sha256: str
    proposal: PlacementOptimization

    @classmethod
    def read(cls, raw: Any) -> PlacementOverlay:
        if not isinstance(raw, dict):
            raise ValueError("expected a complete place reply")
        reply = cast(dict[str, Any], raw)
        if reply.get("command") != "place":
            raise ValueError("expected a complete place reply")
        source = reply["input"]["sha256"]
        if not isinstance(source, str) or not re.fullmatch(r"[a-f0-9]{64}", source):
            raise ValueError("place reply has no board digest")
        proposal = cast(
            PlacementOptimization,
            canonical.loads(json.dumps(reply["result"]["optimization"]), PlacementOptimization),
        )
        if not re.fullmatch(r"[a-f0-9]{64}", proposal.input_sha256):
            raise ValueError("placement fingerprint is invalid")
        if len({candidate.id for candidate in proposal.candidates}) != len(proposal.candidates):
            raise ValueError("duplicate placement candidate")
        for candidate in proposal.candidates:
            if candidate_id(proposal.input_sha256, candidate.poses) != candidate.id:
                raise ValueError("placement candidate identity does not match its poses")
        return cls(source, proposal)

    def overlays(
        self, design: Design, frame: BoardFrame, scene: Mapping[str, Any]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if scene["meta"].get("sha256") != self.source_sha256 or design.board is None:
            return [], []
        result = self.proposal
        scope = PlacementScope(result.movable, tuple(result.fixed.items()))
        footprints = {fp.id: fp for fp in design.board.footprints}
        components = {component.id: component.ref for component in design.circuit.components}

        def pads_at(board: Design) -> dict[PadIdentity, Point]:
            return {PadIdentity(p.footprint_id, p.pad_id): p.position for p in frame.board_pads(board)}

        before = pads_at(design)
        items: list[dict[str, Any]] = []
        groups: list[dict[str, Any]] = []
        for rank, candidate in enumerate(result.candidates, 1):
            group = "placement-" + candidate.id
            color = _COLORS[(rank - 1) % len(_COLORS)]
            start = len(items)

            def line(
                first: Point,
                second: Point,
                label: str,
                subjects: dict[str, Any],
                group: str = group,
                color: str = color,
            ) -> None:
                items.append(
                    {
                        "group": group,
                        "kind": "path",
                        "pts": [
                            [round_half_even_div(p.x, 1000), round_half_even_div(p.y, 1000)]
                            for p in (first, second)
                        ],
                        "color": color,
                        "label": label,
                        **subjects,
                    }
                )

            projected = project_poses(design, scope, candidate.poses)
            for pose in candidate.poses:
                original = footprints[pose.footprint_id]
                ref = components.get(original.component_id, original.lib_ref)
                if original.position != pose.position or original.rotation % 360_000_000 != pose.rotation:
                    line(
                        original.position,
                        pose.position,
                        f"{ref} · {pose.side} · {pose.rotation / 1e6:g}°",
                        {"component_id": original.component_id},
                    )
            after = pads_at(projected)
            for row in result.intent:
                intent = row.effective
                if intent is None:
                    continue
                links = (intent,) if len(intent.endpoints) == 2 else probe_intent_legs(intent)
                for link in links:
                    first, second = link.endpoints
                    if all(key in before and key in after for key in (first, second)):
                        old = _distance(before[first], before[second])
                        new = _distance(after[first], after[second])
                        line(
                            after[first],
                            after[second],
                            f"{link.key} · pad distance {old} → {new} nm",
                            {"pad_ids": [first.pad_id, second.pad_id]},
                        )
            scores = ", ".join(
                f"{name}={value}" for name, value in zip(result.score_fields, candidate.score, strict=True)
            )
            details = [scores, f"{len(result.movable)} movable, {len(result.fixed)} fixed"]
            if candidate.channel_overflow_by_layer:
                details.append(
                    "Overflow (nm) "
                    + ", ".join(
                        f"{layer}={width}"
                        for layer, width in sorted(candidate.channel_overflow_by_layer.items())
                    )
                )
            if candidate.probes:
                details.append(
                    "Probes "
                    + ", ".join(
                        f"{row.key} {row.status}"
                        + (f" {row.length_nm} nm" if row.length_nm is not None else "")
                        for row in candidate.probes
                    )
                )
            if candidate.missing_inputs:
                details.append("Missing checks: " + ", ".join(candidate.missing_inputs))
            groups.append(
                {
                    "id": group,
                    "title": f"Placement {rank} · {candidate.id[:12]}",
                    "color": color,
                    "n": len(items) - start,
                    "note": " · ".join(filter(None, details)),
                }
            )
        return items, groups


def _distance(a: Point, b: Point) -> int:
    return ceil_sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)
