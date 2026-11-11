# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project candidate poses without replacing footprint-local geometry."""

from dataclasses import dataclass, replace

from fenolite.backends.base import BoardFrame, DesignRules
from fenolite.model.board import FootprintInstance
from fenolite.model.design import Design
from fenolite.placement.constrained_legality import PlacementChecker, PlacementLegality, check_constraints
from fenolite.placement.constraints import PlacementConstraints
from fenolite.placement.optimization_contract import ProposedPose
from fenolite.placement.protection import PlacementScope

_TURN = 360_000_000
_QUARTER = 90_000_000


def project_poses(design: Design, scope: PlacementScope, poses: tuple[ProposedPose, ...]) -> Design:
    """Change same-face anchors only. The board frame projects existing local pads and bodies."""
    board = design.board
    if board is None:
        raise ValueError("pose projection requires a board")
    by_id = {pose.footprint_id: pose for pose in poses}
    if len(by_id) != len(poses):
        raise ValueError("duplicate footprint pose")
    if by_id.keys() - set(scope.movable):
        raise ValueError("pose outside movable scope")
    remaining = set(by_id)
    footprints: list[FootprintInstance] = []
    for fp in board.footprints:
        pose = by_id.get(fp.id)
        if pose is None:
            footprints.append(fp)
            continue
        remaining.remove(fp.id)
        if fp.locked:
            raise ValueError(f"locked footprint: {fp.id}")
        if pose.side != fp.side:
            raise ValueError(f"unsupported side change: {fp.id}")
        if type(pose.rotation) is not int or not 0 <= pose.rotation < _TURN:
            raise ValueError(f"rotation must be normalized integer microdegrees: {fp.id}")
        if pose.rotation != fp.rotation % _TURN and pose.rotation % _QUARTER:
            raise ValueError(f"unsupported rotation: {fp.id}")
        # Keep the raw angle if the pose did not turn. Relative pad, field, and body data stay intact.
        rotation = fp.rotation if pose.rotation == fp.rotation % _TURN else pose.rotation
        footprints.append(replace(fp, position=pose.position, rotation=rotation))
    if remaining:
        raise ValueError("pose refers to a missing footprint")
    return replace(design, board=replace(board, footprints=tuple(footprints)))


@dataclass(frozen=True, slots=True)
class PoseAssessment:
    design: Design
    legality: PlacementLegality

    @property
    def checked(self) -> bool:
        return not self.legality.hard and not self.legality.missing_inputs and not self.legality.intrinsic


def assess_poses(
    design: Design,
    scope: PlacementScope,
    poses: tuple[ProposedPose, ...],
    frame: BoardFrame,
    constraints: PlacementConstraints,
    *,
    rules: DesignRules | None = None,
    checker: PlacementChecker | None = None,
) -> PoseAssessment:
    """Project the poses and preserve the full checker report, including unavailable providers."""
    placed = project_poses(design, scope, poses)
    return PoseAssessment(placed, check_constraints(placed, frame, constraints, rules=rules, checker=checker))
