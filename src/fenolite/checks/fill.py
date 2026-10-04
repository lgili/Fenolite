# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Check the board's derived copper against a refill of its project copy set."""

from __future__ import annotations

import dataclasses

from fenolite.backends.base import FillOracle, ProjectSet, ZoneFills
from fenolite.checks.codes import issue
from fenolite.checks.stages import StageResult, ran
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.board import ZoneFill
from fenolite.model.design import Design


def _ring(fill: ZoneFill) -> tuple[tuple[int, int], ...]:
    points = tuple((point.x, point.y) for point in fill.polygon)
    if points and points[0] == points[-1]:
        points = points[:-1]
    if not points:
        return ()
    first = min(range(len(points)), key=lambda index: points[index])
    return points[first:] + points[:first]


def _fills(fills: tuple[ZoneFill, ...]) -> frozenset[tuple[str, bool, tuple[tuple[int, int], ...]]]:
    return frozenset((fill.layer, fill.island, _ring(fill)) for fill in fills)


def fill_stage(oracle: FillOracle, project: ProjectSet, design: Design) -> StageResult:
    """Run one refill and compare only the copper polygons of zones with a net."""
    outcome = oracle.refill(project)
    if not outcome.supported:
        return StageResult(
            "zone.fill",
            "skipped",
            Evidence(),
            (issue("zone.fill-unchecked", outcome.message or "zone refill is unsupported"),),
            reason="oracle-unsupported",
        )
    if not outcome.stable:
        return StageResult(
            "zone.fill",
            "skipped",
            Evidence(),
            (issue("zone.fill-unchecked", "repeated KiCad refills differ"),),
            reason="oracle-unstable",
        )
    summary: dict[str, object] = {
        "tool_version": outcome.tool_version,
        "zones": 0,
        "current": 0,
        "unfilled": 0,
        "stale": 0,
    }
    if outcome.zones is None:
        failure = issue(
            "check.oracle-failed",
            outcome.message or "zone refill returned no saved board",
            retryable=outcome.outcome == "timeout",
        )
        return ran("zone.fill", (failure,), Evidence(), summary)
    saved: dict[str, ZoneFills] = {zone.zone_id: zone for zone in outcome.zones}
    issues: list[Issue] = []
    zones_count = current_count = unfilled_count = stale_count = 0
    if design.board is not None:
        for zone in design.board.zones:
            if zone.net_id is None:
                continue
            zones_count += 1
            target = saved.get(zone.id)
            if target is None:
                issues.append(issue("check.oracle-failed", f"refill omitted zone {zone.id}", where=zone.id))
                continue
            current, expected = _fills(zone.fills), _fills(target.fills)
            where = zone.name or zone.id
            if expected and not current:
                unfilled_count += 1
                issues.append(issue("zone.unfilled", f"zone {where} has no saved copper fill", where=where))
            elif current != expected:
                stale_count += 1
                issues.append(
                    issue("zone.fill-stale", f"zone {where} fill differs from KiCad refill", where=where)
                )
            else:
                current_count += 1
    summary.update(zones=zones_count, current=current_count, unfilled=unfilled_count, stale=stale_count)
    changed = any(i.code in ("zone.unfilled", "zone.fill-stale") for i in issues)
    evidence = dataclasses.replace(outcome.evidence, level=Level.UNVERIFIED) if changed else outcome.evidence
    return ran("zone.fill", issues, evidence, summary)


__all__ = ["fill_stage"]
