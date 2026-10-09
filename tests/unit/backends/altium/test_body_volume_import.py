# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0099 retains every authored ambiguous body without duplicating native bytes in ext."""

import _altium_records as rec
import pytest

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.read.bodies import encode, read_bodies
from fenolite.core.errors import Issue


@pytest.mark.parametrize("side,projection", [("TOP", 0), ("BOTTOM", 1)])
def test_signed_body_matches_mounted_face(side: str, projection: int) -> None:
    data = rec.body_bytes(fields={"STANDOFFHEIGHT": "-12mil", "BODYPROJECTION": str(projection)})
    doc = rec.document(
        components=[rec.component("U1", layer=side)], storages={"ComponentBodies6": {"Data": data}}
    )
    design = import_board(doc, file="authored.PcbDoc", sha256=rec.SHA)
    assert design.board
    (body,) = design.board.footprints[0].bodies
    assert (body.z_min, body.z_max) == (-304_800, 1_016_000)
    assert (body.z_min, body.z_max) == (body.standoff, body.height)
    assert not body.projection_unknown
    assert not [i for i in design.validate() if i.severity == "error"]
    assert "body" not in dict(body.ext.get("altium").payload) if "altium" in body.ext else True
    assert encode(read_bodies(data)) == data


@pytest.mark.parametrize(
    "fields",
    [
        {"BODYPROJECTION": "73"},
        {"BODYPROJECTION": "1"},
        {"MODEL.MODELTYPE": "73", "MODEL.NAME": "authored.step"},
        {"OVERALLHEIGHT": "4mil", "STANDOFFHEIGHT": "8mil"},
        {"OVERALLHEIGHT": "tall"},
        {"STANDOFFHEIGHT": "unknown"},
    ],
)
def test_unknown_projection_retains_body_and_source(fields: dict[str, str]) -> None:
    data = rec.body_bytes(fields=fields)
    doc = rec.document(components=[rec.component("U1")], storages={"ComponentBodies6": {"Data": data}})
    issues: list[Issue] = []
    design = import_board(doc, file="authored.PcbDoc", sha256=rec.SHA, issues=issues)
    assert design.board
    (body,) = design.board.footprints[0].bodies
    assert body.projection_unknown and body.z_min is body.z_max is None
    assert any(i.code == "altium.import.body-unknown" and i.where.endswith("#0") for i in issues)
    assert body.model == fields.get("MODEL.NAME", "")
    assert body.provenance and body.provenance.locator.endswith("#0")
    assert encode(read_bodies(data)) == data
    assert not [i for i in design.validate() if i.severity == "error"]
    assert all("raw" not in value for ext in body.ext.values() for _, value in ext.payload)


def test_reversed_source_heights_are_not_clamped() -> None:
    data = rec.body_bytes(fields={"OVERALLHEIGHT": "4mil", "STANDOFFHEIGHT": "8mil"})
    doc = rec.document(components=[rec.component("U1")], storages={"ComponentBodies6": {"Data": data}})
    design = import_board(doc, file="authored.PcbDoc", sha256=rec.SHA)
    assert design.board
    (body,) = design.board.footprints[0].bodies
    assert (body.height, body.standoff) == (101_600, 203_200)


def test_only_unknown_body_is_mapped_without_unmapped_issue() -> None:
    data = rec.body_bytes(fields={"BODYPROJECTION": "73"})
    doc = rec.document(components=[rec.component("U1")], storages={"ComponentBodies6": {"Data": data}})
    issues: list[Issue] = []
    design = import_board(doc, file="authored.PcbDoc", sha256=rec.SHA, issues=issues)
    assert design.board and len(design.board.footprints[0].bodies) == 1
    assert any(i.code == "altium.import.body-unknown" for i in issues)
    assert not any(i.code == "altium.import.unmapped" for i in issues)
