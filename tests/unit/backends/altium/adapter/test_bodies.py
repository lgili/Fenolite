# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Component bodies of imported footprints (capability altium-import, "Component body records"; c0043)."""

from __future__ import annotations

import _altium_records as rec

from fenolite.backends.altium.adapter import import_board
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.model.board import FootprintInstance

MIL = rec.MIL


def footprints(
    data: bytes, issues: list[Issue] | None = None, **extra: object
) -> tuple[FootprintInstance, ...]:
    document = rec.document(
        components=[rec.component("U1", x="1000mil", y="500mil", rotation=90.0), rec.component("U2")],
        storages={"ComponentBodies6": {"Data": data, "Header": b"\x01\0\0\0"}},
        **extra,  # type: ignore[arg-type]
    )
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    assert design.board is not None
    assert [i for i in design.validate() if i.severity == "error"] == []
    return design.board.footprints


def test_extruded_body_of_a_footprint() -> None:
    square = [(1000, 500), (1100, 500), (1100, 600), (1000, 600)]
    first, second = footprints(rec.body_bytes(square, component=0))
    assert second.bodies == ()
    (body,) = first.bodies
    assert (body.kind, body.height, body.standoff) == ("extruded", 1_016_000, 0)
    assert (body.layer, body.model, body.name) == ("Mech.13", "", "")
    # The footprint is turned by 90 degrees: the board's +X (Altium) is the footprint's −Y... in its frame.
    assert body.outline == (
        Point(0, 0),
        Point(0, 2_540_000),
        Point(2_540_000, 2_540_000),
        Point(2_540_000, 0),
    )
    assert body.id.startswith("bdy_") and body.provenance is not None
    assert body.provenance.locator == "ComponentBodies6/Data#0"


def test_model_body_with_heights_and_identifier() -> None:
    fields = {"MODEL.NAME": "part.step", "OVERALLHEIGHT": "100mil", "STANDOFFHEIGHT": "10mil",
              "IDENTIFIER": "66,49"}  # fmt: skip
    first, _ = footprints(rec.body_bytes(component=0, layer=57, fields=fields))
    (body,) = first.bodies
    assert (body.kind, body.model, body.name) == ("model", "part.step", "B1")
    assert (body.height, body.standoff, body.layer) == (2_540_000, 254_000, "Mech.1")


def test_bodies_in_stream_order_and_free_bodies_unmapped() -> None:
    issues: list[Issue] = []
    data = b"".join(
        [
            rec.body_bytes(component=1, fields={"IDENTIFIER": "65"}),
            rec.body_bytes(component=None),
            rec.body_bytes(component=1, fields={"IDENTIFIER": "66"}),
            rec.body_bytes(component=1, fields={"OVERALLHEIGHT": "tall"}),
            rec.body_bytes(component=9),
        ]
    )
    first, second = footprints(data, issues)
    assert first.bodies == () and [body.name for body in second.bodies] == ["A", "B"]
    (unmapped,) = [i for i in issues if i.code == "altium.import.unmapped"]
    assert "bodies 3" in unmapped.message and "ComponentBodies6" not in unmapped.message
    (bad,) = [i for i in issues if i.code == "altium.import.bad-length"]
    assert bad.where == "ComponentBodies6/Data#3"


def test_two_equal_bodies_get_two_ids() -> None:
    first, _ = footprints(rec.body_bytes(component=0) * 2)
    assert len(first.bodies) == 2 and first.bodies[0].id != first.bodies[1].id


def test_the_shape_based_storage_is_named_as_kept_bytes() -> None:
    issues: list[Issue] = []
    storages = {"ShapeBasedComponentBodies6": {"Data": rec.body_bytes(shape_based=True)}}
    document = rec.document(components=[rec.component("U1")], storages=storages)
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    assert design.board is not None and design.board.footprints[0].bodies == ()
    (unmapped,) = [i for i in issues if i.code == "altium.import.unmapped"]
    assert "ShapeBasedComponentBodies6 1" in unmapped.message
