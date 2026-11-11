# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from dataclasses import replace

from fenolite.backends.kicad import frame
from fenolite.cli.placement_checks import check_placement_constraints
from fenolite.core.coords import Point
from fenolite.model.board import Keepout
from fenolite.placement.constraints import MechanicalConstraints, MechanicalVolume, PlacementConstraints
from fenolite.placement.optimization_contract import ProposedPose
from fenolite.placement.pose_projection import assess_poses
from fenolite.placement.protection import PlacementScope

from ._constrained_fixture import board, part


def rectangle(x0, y0, x1, y1):
    return (Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1))


def test_bottom_connector_remains_on_its_face_at_a_front_antenna_exclusion():
    design = board(part("J", 9, 10, side="bottom", two_pads=True))
    assert design.board is not None
    antenna = Keepout(id="rf", outline=rectangle(14, 6, 29, 16), layers=("F.Cu",), no_pads=True)
    request = (ProposedPose("J", Point(20, 10), 0, "bottom"),)
    scope = PlacementScope(("J",), ())
    front = replace(design, board=replace(design.board, keepouts=(antenna,)))
    first = assess_poses(front, scope, request, frame, PlacementConstraints())
    assert not any(issue.startswith("keepout:rf:") for issue in first.legality.hard)
    assert all(p.side == "bottom" and p.layers == ("B.Cu",) for p in frame.board_pads(first.design))

    both_faces = replace(front, board=replace(front.board, keepouts=(replace(antenna, layers=("B.Cu",)),)))
    second = assess_poses(both_faces, scope, request, frame, PlacementConstraints())
    assert any(issue.startswith("keepout:rf:") for issue in second.legality.hard)


def test_enclosure_volume_and_connector_access_apply_to_the_placed_body():
    design = board(part("J", 8, 8, body=True))
    scope = PlacementScope(("J",), ())
    constraints = PlacementConstraints(
        volumes=MechanicalConstraints(
            board_thickness=4,
            obstacles=(
                MechanicalVolume("cover", rectangle(17, 6, 24, 13), 3, 10),
                MechanicalVolume("access", rectangle(27, 6, 34, 13), 0, 10),
            ),
        )
    )
    for x, name in ((20, "cover"), (30, "access")):
        result = assess_poses(
            design,
            scope,
            (ProposedPose("J", Point(x, 9), 0, "top"),),
            frame,
            constraints,
            checker=check_placement_constraints,
        )
        assert not result.checked
        assert any(name in issue for issue in result.legality.hard)
