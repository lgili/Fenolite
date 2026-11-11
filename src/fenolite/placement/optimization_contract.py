# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Neutral request and pose identity for schematic-aware placement (c0477)."""

import hashlib
from dataclasses import dataclass, field
from typing import Literal

from fenolite.core.coords import Point
from fenolite.model.canonical import dumps
from fenolite.placement.constraints import PlacementConstraints
from fenolite.placement.intent import PlacementIntent, ResolvedIntent


@dataclass(frozen=True, slots=True)
class AllowedRotations:
    footprint_id: str
    rotations: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.footprint_id or not self.rotations or len(set(self.rotations)) != len(self.rotations):
            raise ValueError("allowed rotations need a footprint and distinct angles")
        if any(type(angle) is not int or not 0 <= angle < 360_000_000 for angle in self.rotations):
            raise ValueError("rotations must be normalized integer microdegrees")


@dataclass(frozen=True, slots=True)
class OptimizationBudget:
    evaluations: int
    beam_width: int
    probe_expansions: int = 0

    def __post_init__(self) -> None:
        for label, number, minimum in (
            ("evaluations", self.evaluations, 1),
            ("beam_width", self.beam_width, 1),
            ("probe_expansions", self.probe_expansions, 0),
        ):
            if type(number) is not int or number < minimum:
                raise ValueError(f"{label} must be an integer >= {minimum}")


@dataclass(frozen=True, slots=True)
class OptimizationRequest:
    schema: Literal["fenolite.placement-optimization.v0"]
    selected: tuple[str, ...]
    budget: OptimizationBudget
    constraints: PlacementConstraints = PlacementConstraints()
    rotations: tuple[AllowedRotations, ...] = ()
    seed: int = 0
    intent: tuple[PlacementIntent, ...] = ()

    def __post_init__(self) -> None:
        if self.schema != "fenolite.placement-optimization.v0":
            raise ValueError("unsupported placement optimization schema")
        if not self.selected or any(not item for item in self.selected):
            raise ValueError("select at least one footprint identity")
        if len(set(self.selected)) != len(self.selected):
            raise ValueError("duplicate selected footprint")
        keys = [row.footprint_id for row in self.rotations]
        if len(set(keys)) != len(keys) or set(keys) - set(self.selected):
            raise ValueError("rotation constraints must refer to distinct selected footprints")
        if type(self.seed) is not int:
            raise ValueError("seed must be an integer")


@dataclass(frozen=True, slots=True)
class ProposedPose:
    footprint_id: str
    position: Point
    rotation: int
    side: Literal["top", "bottom"]


@dataclass(frozen=True, slots=True)
class PlacementCandidate:
    id: str
    poses: tuple[ProposedPose, ...]


@dataclass(frozen=True, slots=True)
class PadProbe:
    key: str
    status: str
    length_nm: int | None = field(default=None, metadata={"optional": True})
    expanded: int = field(default=0, metadata={"optional": True})


@dataclass(frozen=True, slots=True)
class OptimizationCandidate(PlacementCandidate):
    score: tuple[int, ...]
    missing_inputs: tuple[str, ...]
    channel_overflow_by_layer: dict[str, int] = field(default_factory=lambda: {}, metadata={"optional": True})
    probes: tuple[PadProbe, ...] = field(default=(), metadata={"optional": True})


@dataclass(frozen=True, slots=True)
class PlacementOptimization:
    input_sha256: str
    termination: Literal["complete", "budget_exhausted", "cancelled", "missing_inputs"]
    candidates: tuple[OptimizationCandidate, ...] = ()
    unplaced: tuple[str, ...] = ()
    fixed: dict[str, tuple[str, ...]] = field(default_factory=lambda: {})
    movable: tuple[str, ...] = ()
    sampled: dict[str, int] = field(default_factory=lambda: {})
    domain_truncated: tuple[str, ...] = ()
    intent: tuple[ResolvedIntent, ...] = ()
    score_fields: tuple[str, ...] = ()
    work: int = 0
    beam_pruned: bool = False
    blockers: tuple[str, ...] = ()
    partial: tuple[ProposedPose, ...] = ()
    schema: Literal["fenolite.placement-optimization-result.v0"] = "fenolite.placement-optimization-result.v0"


def candidate_id(input_sha256: str, poses: tuple[ProposedPose, ...]) -> str:
    """Identify an exact pose set on one input snapshot, regardless of enumeration order."""
    ordered = tuple(sorted(poses, key=lambda pose: pose.footprint_id))
    if len({pose.footprint_id for pose in ordered}) != len(ordered):
        raise ValueError("a candidate must have one pose per footprint")
    return hashlib.sha256(dumps((input_sha256, ordered)).encode()).hexdigest()
