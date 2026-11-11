# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from dataclasses import replace

import pytest

from fenolite.backends.kicad import frame
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Point
from fenolite.placement.constraints import PlacementConstraints
from fenolite.placement.optimization_contract import ProposedPose
from fenolite.placement.pose_projection import assess_poses, project_poses
from fenolite.placement.protection import PlacementScope

from ._constrained_fixture import board, part


def test_asymmetric_pads_and_owned_rule_area_follow_pose_and_survive_board_readback():
    source = """(kicad_pcb (version 20250513) (generator "pcbnew") (generator_version "10.0")
      (general (thickness 1.6)) (paper "A4")
      (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user))
      (setup (pad_to_mask_clearance 0))
      (footprint "Authored:Asymmetric" (layer "F.Cu") (at 10 10)
        (uuid "01010101-0000-4000-8000-000000000001")
        (pad "1" smd rect (at 0 0) (size 1 2) (layers "F.Cu")
          (uuid "01010101-0000-4000-8000-000000000002"))
        (pad "2" smd rect (at 5 0) (size 2 1) (layers "F.Cu")
          (uuid "01010101-0000-4000-8000-000000000003"))
        (zone (net 0) (net_name "") (layer "F.Cu")
          (uuid "01010101-0000-4000-8000-000000000004")
          (keepout (tracks not_allowed))
          (polygon (pts (xy 13 12) (xy 19 12) (xy 19 17) (xy 13 17))))))
    """
    design = read_board(source)
    assert design.board is not None
    (fp,) = design.board.footprints
    pose = ProposedPose(fp.id, Point(20_000_000, 15_000_000), 90_000_000, "top")
    placed = project_poses(design, PlacementScope((fp.id,), ()), (pose,))
    assert placed.board is not None and placed.board.footprints[0].pads == fp.pads
    before_write = frame.board_pads(placed)
    assert {p.number: p.position for p in before_write} == {
        "1": Point(20_000_000, 15_000_000),
        "2": Point(20_000_000, 10_000_000),
    }
    reread = read_board(write_board(placed, target=10).text)
    assert frame.board_pads(reread) == before_write
    assert reread.board is not None
    assert reread.board.footprints[0].keepouts[0].outline == fp.keepouts[0].outline


def test_enclosed_cutout_and_overhang_are_rejected_and_missing_checks_remain_visible():
    design = board(part("A", 10, 10))
    hole = (Point(19, 19), Point(21, 19), Point(21, 21), Point(19, 21))
    design = replace(
        design, board=replace(design.board, outline=replace(design.board.outline, cutouts=(hole,)))
    )
    scope = PlacementScope(("A",), ())
    pose = ProposedPose("A", Point(20, 20), 0, "top")
    result = assess_poses(design, scope, (pose,), frame, PlacementConstraints())
    assert "cutout:A" in result.legality.hard
    assert not result.checked and "copper:checker-unavailable" in result.legality.missing_inputs
    edge = assess_poses(design, scope, (replace(pose, position=Point(0, 10)),), frame, PlacementConstraints())
    assert any("outside" in issue for issue in edge.legality.hard)


def test_projection_rejects_changes_outside_scope_or_supported_rotations():
    design = board(part("A", 10, 10, locked=True), part("B", 20, 20))
    scope = PlacementScope(("B",), ())
    with pytest.raises(ValueError, match="outside movable scope"):
        project_poses(design, scope, (ProposedPose("A", Point(10, 11), 0, "top"),))
    with pytest.raises(ValueError, match="unsupported rotation"):
        project_poses(design, scope, (ProposedPose("B", Point(10, 11), 30_000_000, "top"),))
    with pytest.raises(ValueError, match="unsupported side"):
        project_poses(design, scope, (ProposedPose("B", Point(10, 11), 0, "bottom"),))
