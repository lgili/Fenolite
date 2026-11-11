# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bounded joint search over precomputed placement domains."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from fenolite.placement.optimization_contract import (
    OptimizationBudget,
    PlacementCandidate,
    ProposedPose,
    candidate_id,
)

PoseSet = tuple[ProposedPose, ...]
Score = tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SearchJudgment:
    score: Score = ()
    hard: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()


Judge = Callable[[PoseSet, bool], SearchJudgment]
Compatible = Callable[[ProposedPose, ProposedPose], bool]


@dataclass(frozen=True, slots=True)
class RankedPlacement:
    candidate: PlacementCandidate
    score: Score


@dataclass(frozen=True, slots=True)
class SearchResult:
    candidates: tuple[RankedPlacement, ...]
    partial: PoseSet
    unplaced: tuple[str, ...]
    termination: Literal["complete", "budget_exhausted", "cancelled"]
    work: int
    beam_pruned: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _State:
    poses: PoseSet = ()
    score: Score = ()
    domains: tuple[PoseSet, ...] = ()


def _pose_key(pose: ProposedPose) -> tuple[str, int, int, int, str]:
    return (pose.footprint_id, pose.position.x, pose.position.y, pose.rotation, pose.side)


def _state_key(state: _State) -> tuple[Score, tuple[tuple[str, int, int, int, str], ...]]:
    return state.score, tuple(_pose_key(pose) for pose in state.poses)


def beam_search(
    domains: Mapping[str, PoseSet],
    *,
    input_sha256: str,
    budget: OptimizationBudget,
    judge: Judge,
    compatible: Compatible | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> SearchResult:
    """Compare equal-coverage states, retaining only fully checked candidates at the final depth.

    A call to either evaluator spends one work unit. Pair compatibility may reject a proven
    conflict only. An incomplete relationship can be pending until the final whole-board judge.
    """
    if not domains:
        raise ValueError("at least one placement domain is required")
    ids = tuple(sorted(domains, key=lambda key: (len(set(domains[key])), key)))
    choices: tuple[PoseSet, ...] = tuple(tuple(sorted(set(domains[ident]), key=_pose_key)) for ident in ids)
    if any(pose.footprint_id != ident for ident, rows in zip(ids, choices, strict=True) for pose in rows):
        raise ValueError("a domain contains a pose for another footprint")

    work = 0
    beam_pruned = False
    termination: Literal["complete", "budget_exhausted", "cancelled"] = "complete"
    blockers = {f"empty_domain:{ident}" for ident, rows in zip(ids, choices, strict=True) if not rows}
    frontier = [_State(domains=choices)]
    partial = _State()
    final: list[_State] = []

    def charge() -> bool:
        nonlocal work, termination
        if cancelled is not None and cancelled():
            termination = "cancelled"
            return False
        if work >= budget.evaluations:
            termination = "budget_exhausted"
            return False
        work += 1
        return True

    for depth, ident in enumerate(ids if not blockers else ()):
        complete = depth == len(ids) - 1
        following: list[_State] = []
        for state in frontier:
            for pose in state.domains[0]:
                if not charge():
                    break
                poses = tuple(sorted((*state.poses, pose), key=_pose_key))
                judged = judge(poses, complete)
                if judged.hard or judged.missing_inputs:
                    blockers.update(judged.hard)
                    blockers.update(judged.missing_inputs)
                    continue
                pending = state.domains[1:]
                if compatible is not None:
                    narrowed: list[PoseSet] = []
                    for target, options in zip(ids[depth + 1 :], pending, strict=True):
                        allowed: list[ProposedPose] = []
                        for option in options:
                            if not charge():
                                break
                            if compatible(pose, option):
                                allowed.append(option)
                        if termination != "complete":
                            break
                        if not allowed:
                            blockers.add(f"domain_conflict:{ident}:{target}")
                            break
                        narrowed.append(tuple(allowed))
                    if termination != "complete":
                        break
                    if len(narrowed) != len(pending):
                        continue
                    pending = tuple(narrowed)

                proposed = _State(poses, judged.score, pending)
                if not complete and (
                    len(poses) > len(partial.poses)
                    or (len(poses) == len(partial.poses) and _state_key(proposed) < _state_key(partial))
                ):
                    partial = proposed
                following.append(proposed)
                following.sort(key=_state_key)
                if len(following) > budget.beam_width:
                    following.pop()
                    beam_pruned = True
            if termination != "complete":
                break
        if complete:
            final = following
        if termination != "complete" or not following:
            break
        frontier = following

    candidates = tuple(
        RankedPlacement(PlacementCandidate(candidate_id(input_sha256, state.poses), state.poses), state.score)
        for state in final
    )
    placed = {pose.footprint_id for pose in partial.poses}
    return SearchResult(
        candidates,
        () if candidates else partial.poses,
        () if candidates else tuple(sorted(set(ids) - placed)),
        termination,
        work,
        beam_pruned,
        tuple(sorted(blockers)),
    )
