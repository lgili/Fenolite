# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Refine a complete placement with bounded, explicitly scoped pose changes."""

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from itertools import product
from typing import Literal

from fenolite.placement.optimization_contract import PlacementCandidate, ProposedPose, candidate_id
from fenolite.placement.optimize import Judge, PoseSet, RankedPlacement


@dataclass(frozen=True, slots=True)
class Refinement:
    best: RankedPlacement | None
    work: int
    improvements: int
    termination: Literal["complete", "budget_exhausted", "cancelled", "invalid_seed"]
    blockers: tuple[str, ...] = ()


def _near(a: ProposedPose, b: ProposedPose, limit: int) -> bool:
    return a.side == b.side and abs(a.position.x - b.position.x) + abs(a.position.y - b.position.y) <= limit


def _neighbors(
    current: PoseSet,
    domains: Mapping[str, PoseSet],
    windows: tuple[tuple[str, ...], ...],
    step_nm: int,
) -> Iterator[PoseSet]:
    at = {pose.footprint_id: pose for pose in current}
    for window in windows:
        nearby = [tuple(pose for pose in domains[key] if _near(at[key], pose, step_nm)) for key in window]
        for choices in product(*nearby):
            changed = {pose.footprint_id: pose for pose in choices}
            yield tuple(changed.get(pose.footprint_id, pose) for pose in current)


def refine_placement(
    seed: PoseSet,
    domains: Mapping[str, PoseSet],
    *,
    input_sha256: str,
    judge: Judge,
    max_attempts: int,
    step_nm: int,
    windows: tuple[tuple[str, ...], ...] = (),
    cancelled: Callable[[], bool] | None = None,
) -> Refinement:
    """Restart around the first improving neighbor. Joint windows can escape a one-part minimum.

    Every generated assignment, even a duplicate, spends one unit. The incumbent is rechecked
    first. All poses stay inside the provided domains, and each window freezes every other part.
    """
    if type(max_attempts) is not int or max_attempts < 0 or type(step_nm) is not int or step_nm < 0:
        raise ValueError("refinement needs integer nonnegative budgets")
    if not seed or len({pose.footprint_id for pose in seed}) != len(seed):
        raise ValueError("refinement needs one seed pose per footprint")
    if {pose.footprint_id for pose in seed} != set(domains) or any(
        pose not in domains[pose.footprint_id] for pose in seed
    ):
        raise ValueError("seed must cover the complete scoped domains")
    if any(pose.footprint_id != key for key, choices in domains.items() for pose in choices):
        raise ValueError("a domain contains a pose for another footprint")
    if any(
        len(window) < 2 or len(set(window)) != len(window) or set(window) - domains.keys()
        for window in windows
    ):
        raise ValueError("windows need at least two distinct scoped footprints")
    scopes = (*((key,) for key in sorted(domains)), *sorted({tuple(sorted(window)) for window in windows}))
    ordered = {
        key: tuple(sorted(set(rows), key=lambda p: (p.position.x, p.position.y, p.rotation, p.side)))
        for key, rows in domains.items()
    }
    current = tuple(sorted(seed, key=lambda pose: pose.footprint_id))
    if cancelled is not None and cancelled():
        return Refinement(None, 0, 0, "cancelled")
    if max_attempts == 0:
        return Refinement(None, 0, 0, "budget_exhausted")
    initial = judge(current, True)
    if initial.hard or initial.missing_inputs:
        return Refinement(None, 1, 0, "invalid_seed", (*initial.hard, *initial.missing_inputs))
    best = RankedPlacement(PlacementCandidate(candidate_id(input_sha256, current), current), initial.score)
    work, improvements = 1, 0
    seen = {current}
    while True:
        for poses in _neighbors(best.candidate.poses, ordered, scopes, step_nm):
            if cancelled is not None and cancelled():
                return Refinement(best, work, improvements, "cancelled")
            if work >= max_attempts:
                return Refinement(best, work, improvements, "budget_exhausted")
            work += 1
            if poses in seen:
                continue
            seen.add(poses)
            assessed = judge(poses, True)
            if not assessed.hard and not assessed.missing_inputs and assessed.score < best.score:
                best = RankedPlacement(
                    PlacementCandidate(candidate_id(input_sha256, poses), poses), assessed.score
                )
                improvements += 1
                break
        else:
            return Refinement(best, work, improvements, "complete")
