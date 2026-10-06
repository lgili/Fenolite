# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent extrusion geometry, side, board and assembly constraints."""

from dataclasses import replace

from fenolite.analysis.body_volumes import BodyVolume, VolumeConstraints, body_volume, check_body_volumes
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.board import ComponentBody, FootprintInstance, Hole, Outline
from fenolite.model.design import Design

RING = (Point(0, 0), Point(100, 0), Point(100, 100), Point(0, 100))


def fp(name: str, low: int, high: int, side: str = "top", x: int = 0) -> FootprintInstance:
    b = ComponentBody(
        id=derived_id("bdy", "test", name), kind="extruded", height=high, z_min=low, z_max=high, outline=RING
    )
    return FootprintInstance(
        id=derived_id("fp", "test", name),
        component_id="",
        lib_ref="",
        position=Point(x, 0),
        bodies=(b,),
        side=side,
    )  # type: ignore[arg-type]


def design(*parts: FootprintInstance) -> Design:
    d = Design.new("volumes", seed=10)
    assert d.board
    outline = Outline(
        id=derived_id("out", "test", "boundary"),
        points=(Point(-100, -100), Point(1000, -100), Point(1000, 1000), Point(-100, 1000)),
    )
    return replace(d, board=replace(d.board, footprints=parts, outline=outline))


def test_opposite_faces_use_thickness_and_report_interference() -> None:
    a, b = fp("a", -60, 50), fp("b", -60, 50, "bottom")
    report = check_body_volumes(design(a, b), VolumeConstraints(board_thickness=100))
    assert any(f.code == "body.intersection" and f.status == "exact" for f in report.findings)
    assert body_volume(b.bodies[0], b, board_thickness=100).volume.z_max == -40  # type: ignore[union-attr]


def test_missing_thickness_and_model_bounds_never_qualify_clear() -> None:
    a = fp("a", 0, 50, "bottom")
    report = check_body_volumes(design(a))
    assert not report.qualified_clear and "board_thickness" in report.missing_inputs
    assert report.projections[0].status == "unknown"


def test_separated_extrusions_are_clear() -> None:
    report = check_body_volumes(
        design(fp("a", 0, 50), fp("b", 0, 50, x=300)), VolumeConstraints(board_thickness=100)
    )
    assert report.qualified_clear


def test_explicit_penetration_and_hole_preserve_board_material_checks() -> None:
    a = fp("a", -30, 20)
    d = design(a)
    assert d.board
    assert check_body_volumes(d, VolumeConstraints(board_thickness=100)).findings
    permit = BodyVolume("mounting", RING, -100, 0)
    assert not check_body_volumes(
        d, VolumeConstraints(board_thickness=100, allowed_penetrations=(permit,))
    ).findings
    hole = Hole(id=derived_id("hol", "test", "hole"), position=Point(50, 50), drill=150)
    d = replace(d, board=replace(d.board, holes=(hole,)))
    assert not check_body_volumes(d, VolumeConstraints(board_thickness=100)).findings


def test_assembly_obstacle_and_missing_screw_access_are_explicit() -> None:
    obstacle = BodyVolume("screw", RING, 20, 80)
    report = check_body_volumes(
        design(fp("a", 0, 50)),
        VolumeConstraints(board_thickness=100, obstacles=(obstacle,), missing_assembly=("enclosure",)),
    )
    assert any(f.code == "body.assembly-intersection" for f in report.findings)
    assert "enclosure" in report.missing_inputs and not report.qualified_clear


def test_preserved_unknown_projection_never_qualifies_clear() -> None:
    part = fp("unknown", 0, 50)
    part = replace(part, bodies=(replace(part.bodies[0], projection_unknown=True),))
    report = check_body_volumes(design(part), VolumeConstraints(board_thickness=100))
    assert report.projections[0].status == "unknown"
    assert report.projections[0].volume is None and not report.qualified_clear


def test_model_and_non_cardinal_extents_are_conservative() -> None:
    part = fp("envelope", 0, 50)
    model = replace(part, bodies=(replace(part.bodies[0], kind="model"),))
    assert body_volume(model.bodies[0], model).status == "conservative"
    turned = replace(part, rotation=30_000_000)
    assert body_volume(turned.bodies[0], turned).status == "conservative"
