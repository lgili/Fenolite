# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A fixing drill with electrical copper remains one unchanged physical pad (c0096)."""

from dataclasses import replace

import pytest

from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.model.board import Board, Hole, MechanicalIntent
from fenolite.model.circuit import Circuit
from fenolite.model.design import Design, DesignHeader
from fenolite.placement.constraints import MechanicalReservation, PlacementConstraints, review_mechanics
from fenolite.placement.constraints import MechanicalVolume as BodyVolume


def fixture():
    pad = BoardPad(
        "mount",
        "J1",
        "J1",
        "drill",
        "1",
        "thru_hole",
        Point(10, 20),
        0,
        "top",
        ("F.Cu", "B.Cu"),
        "earth",
        "EARTH",
        hole=(Point(10, 20),),
        drill=6,
    )
    design = Design(
        DesignHeader(id="d", name="probe", schema_version="fenolite.model.v0", fenolite_version="0.1.0"),
        circuit=Circuit(),
        board=Board(id="b"),
    )
    return design, pad


def test_existing_drill_reservation_does_not_duplicate_or_disconnect() -> None:
    design, pad = fixture()
    volume = BodyVolume("access", (Point(6, 16), Point(14, 16), Point(14, 24), Point(6, 24)), 0, 8)
    reserve = MechanicalReservation(
        "fix",
        "mount",
        "drill",
        (volume,),
        intent=MechanicalIntent("fix", source="authored measurement", status="measured"),
    )
    report = review_mechanics(design, (pad,), (reserve,))
    assert report.linked_drills == (("fix", "drill"),) and not report.duplicate_drills
    assert not report.missing_inputs
    assert design.board is not None and design.board.holes == ()
    assert pad.net_id == "earth" and pad.net == "EARTH" and pad.drill == 6


def test_coincident_intents_and_unknown_access_are_explicit() -> None:
    design, pad = fixture()
    design = replace(design, board=Board(id="b", holes=(Hole(id="extra", position=pad.position, drill=6),)))
    reserve = MechanicalReservation("fix", "mount", "drill")
    report = review_mechanics(design, (pad,), (reserve,))
    assert report.duplicate_drills == (("drill", "extra"),)
    assert "reservation:fix:reservation_geometry" in report.missing_inputs
    missing = review_mechanics(design, (pad,), (replace(reserve, pad_id="absent"),))
    assert "reservation:fix:existing_drill" in missing.missing_inputs
    repeated = review_mechanics(design, (pad,), (reserve, replace(reserve, key="again")))
    assert "reservation:again:duplicate_reference" in repeated.missing_inputs


@pytest.mark.parametrize(
    "kwargs", [{"pitch": 0}, {"gap": -1}, {"max_candidates": True}, {"source_frame": "component"}]
)
def test_invalid_search_contract(kwargs) -> None:
    with pytest.raises(ValueError):
        PlacementConstraints(**kwargs)


@pytest.mark.parametrize(
    "status,source", [("measured", ""), ("estimated", "authored"), ("proposed", "authored")]
)
def test_reservation_requires_measurement_provenance(status, source) -> None:
    design, pad = fixture()
    volume = BodyVolume("clearance", (Point(6, 16), Point(14, 16), Point(14, 24), Point(6, 24)), 0, 8)
    reservation = MechanicalReservation(
        "hold", "mount", "drill", (volume,), intent=MechanicalIntent("hold", status=status, source=source)
    )
    report = review_mechanics(design, (pad,), (reservation,))
    assert report.missing_inputs == ("reservation:hold:source_measurement",)
    assert report.linked_drills == (("hold", "drill"),)
