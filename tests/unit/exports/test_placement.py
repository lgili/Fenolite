# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The neutral placement table (capability assembly-outputs, "Neutral placement rows"; change c0064).
Hermetic. Every part, position, offset and name here is made up for these tests."""

from __future__ import annotations

import dataclasses

import pytest
from _assembly import DATA, DEG, LED, MM, QFP, R_0603, Part, design_of, rectangle
from hypothesis import given
from hypothesis import strategies as st

from fenolite.backends.kicad.outline import BoardOutline, board_outline
from fenolite.core.errors import Issue
from fenolite.core.evidence import Level
from fenolite.exports import placement
from fenolite.exports.assembly import (
    DEFAULT,
    FULL_TURN,
    FootprintRotation,
    PlacementTemplate,
    RotationRule,
    SideRotation,
    read_template,
)
from fenolite.exports.placement import NoOutlineError, apply, rotate, rows_from_model, table


def _template(**changes: object) -> PlacementTemplate:
    return dataclasses.replace(DEFAULT.placement, **changes)  # type: ignore[arg-type]


def test_rows_of_a_model() -> None:
    design = design_of(
        Part("R10", "330", x=20, y=15, rot=90),
        Part("D1", "LED", LED, x=35, y=15, rot=30, side="bottom", attributes=("through_hole",)),
        Part("R2", "10k", properties={"Bin": "A"}, dnp=True),
        Part("FID1", "mark", attributes=("smd", "exclude_from_pos_files")),
        Part("H1", "hole", attributes=("board_only",)),
    )
    rows = rows_from_model(design)
    assert [row.ref for row in rows] == ["D1", "H1", "R2", "R10"]  # natural order, FID1 left out
    d1, h1, r2, r10 = rows
    assert (d1.position.x, d1.position.y, d1.rotation, d1.side) == (35 * MM, 15 * MM, 30 * DEG, "bottom")
    assert (d1.mount, h1.mount, r10.mount) == ("through_hole", "other", "smd")
    assert (r2.dnp, r2.properties, r2.footprint, r2.value) == (True, {"Bin": "A"}, R_0603, "10k")
    assert (r10.position.x, r10.rotation, r10.dnp) == (20 * MM, 90 * DEG, False)


def test_kicad_frame_by_default() -> None:
    design = design_of(Part("R1", "330", x=132, y=109))
    (row,) = apply(rows_from_model(design), DEFAULT.placement)
    assert (row.x, row.y, row.rotation, row.side) == (132 * MM, -109 * MM, 0, "top")
    assert table((row,), DEFAULT.placement) == (
        ("R1", "330", "Mini_R_0603", "132.0000", "-109.0000", "0.00", "top"),
    )


def test_origin_at_the_outline() -> None:
    design = design_of(Part("U1", "MCU", QFP, x=114, y=115), outline=rectangle(100, 100, 50, 30))
    outline = board_outline(design)
    (up,) = apply(rows_from_model(design), _template(origin="outline", y_axis="up"), outline=outline)
    assert (up.x, up.y) == (14 * MM, 15 * MM)  # from the lower-left corner, Y upward
    (down,) = apply(rows_from_model(design), _template(origin="outline", y_axis="down"), outline=outline)
    assert (down.x, down.y) == (14 * MM, 15 * MM)  # from the upper-left corner, Y downward
    (page,) = apply(rows_from_model(design), _template(y_axis="down"))
    assert (page.x, page.y) == (114 * MM, 115 * MM)  # the file's own numbers


def test_rotation_rule() -> None:
    rule = RotationRule(
        bottom=SideRotation(-1, 180 * DEG), footprint=(FootprintRotation("Mini:Mini_QFP*", 90 * DEG),)
    )
    design = design_of(
        Part("U1", "MCU", QFP, rot=90, side="bottom"),
        Part("U2", "MCU", QFP, rot=90),
        Part("R1", "330", rot=90, side="bottom"),
    )
    rows = apply(rows_from_model(design), _template(rotation=rule))
    assert [(row.ref, row.rotation // DEG) for row in rows] == [("R1", 90), ("U1", 180), ("U2", 180)]


def test_the_first_matching_footprint_entry_wins() -> None:
    rule = RotationRule(
        footprint=(
            FootprintRotation("Mini:Mini_R_0603", 10 * DEG),
            FootprintRotation("Mini:*", 20 * DEG),
            FootprintRotation("mini:*", 40 * DEG),  # the match is case-sensitive
        )
    )
    template = _template(rotation=rule)
    assert rotate(0, "top", R_0603, template) == 10 * DEG
    assert rotate(0, "top", LED, template) == 20 * DEG
    assert rotate(0, "top", "Other:Thing", template) == 0
    assert rotate(350 * DEG, "top", LED, template) == 10 * DEG


@given(
    rotation=st.integers(-(10**10), 10**10),
    sign=st.sampled_from([1, -1]),
    offset=st.integers(-(10**10), 10**10),
    extra=st.integers(-(10**10), 10**10),
    side=st.sampled_from(["top", "bottom"]),
)
def test_rotations_stay_in_one_turn(rotation: int, sign: int, offset: int, extra: int, side: str) -> None:
    rule = RotationRule(
        top=SideRotation(sign, offset),
        bottom=SideRotation(sign, offset),
        footprint=(FootprintRotation("*", extra),),
    )
    found = rotate(rotation, side, R_0603, _template(rotation=rule))  # type: ignore[arg-type]
    assert 0 <= found < FULL_TURN
    assert (found - (sign * rotation + offset + extra)) % FULL_TURN == 0
    assert rotate(rotation, side, R_0603, DEFAULT.placement) == rotation % FULL_TURN  # type: ignore[arg-type]


def test_filters() -> None:
    design = design_of(
        Part("R1", "330"),
        Part("D1", "LED", LED, attributes=("through_hole",)),
        Part("R2", "10k", dnp=True),
        Part("H1", "hole", attributes=()),
    )
    rows = rows_from_model(design)
    both = apply(rows, _template(smd_only=True, exclude_dnp=True))
    assert [row.ref for row in both] == ["R1"]
    assert [row.ref for row in apply(rows, _template(exclude_dnp=False))] == ["D1", "H1", "R1", "R2"]
    assert [row.ref for row in apply(rows, _template(smd_only=True, exclude_dnp=False))] == ["R1", "R2"]


def test_no_outline() -> None:
    design = design_of(Part("R1", "330", x=10, y=10))
    outline = board_outline(design)
    assert outline.problem == "no-edge-content"
    issues: list[Issue] = []
    assert apply(rows_from_model(design), _template(origin="outline"), outline=outline, issues=issues) == ()
    assert [(i.code, i.severity, i.where) for i in issues] == [
        ("pnp.no-outline", "error", "placement.origin")
    ]
    with pytest.raises(NoOutlineError) as caught:
        apply(rows_from_model(design), _template(origin="outline"))
    assert caught.value.issues[0].code == "pnp.no-outline"
    assert len(apply(rows_from_model(design), DEFAULT.placement, outline=outline)) == 1  # page needs none


def test_the_outline_is_the_largest_ring() -> None:
    ring = rectangle(100, 100, 50, 30)
    hole = rectangle(110, 110, 5, 5)
    design = design_of(Part("R1", "330", x=100, y=130))
    (row,) = apply(
        rows_from_model(design), _template(origin="outline"), outline=BoardOutline((ring, hole), "model")
    )
    assert (row.x, row.y) == (0, 0)


def test_table_under_an_authored_template() -> None:
    template = read_template((DATA / "rotated.toml").read_text(encoding="utf-8")).placement
    design = design_of(
        Part("U1", "MCU", QFP, x=114, y=115, rot=45),
        Part("R1", "330", x=132, y=109, properties={"Bin": "A"}),
        Part("D1", "LED", LED, x=138, y=120, rot=30, side="bottom", attributes=("through_hole",)),
        outline=rectangle(100, 100, 50, 30),
    )
    rows = apply(rows_from_model(design), template, outline=board_outline(design))
    assert table(rows, template) == (
        ("D1", "Mini_LED_THT_3mm", "1496.1", "393.7", "150.0", "lower"),  # -30 + 180
        ("R1", "Mini_R_0603", "1259.8", "826.8", "337.5", "upper"),  # 0 - 22.5
        ("U1", "Mini_QFP-32_7x7mm_P0.8mm", "551.2", "590.6", "135.0", "upper"),  # 45 + 90
    )


def test_property_and_unit_cells() -> None:
    design = design_of(Part("R1", "330", x=1, y=-2, rot=270, properties={"Bin": "A"}))
    (row,) = apply(rows_from_model(design), DEFAULT.placement)
    template = _template(units="in", decimals=3, rotation_decimals=0)
    assert [placement.cell(row, name, template) for name in ("x", "y", "rotation", "footprint")] == [
        "0.039", "0.079", "270", R_0603,
    ]  # fmt: skip
    assert placement.cell(row, "property:Bin", template) == "A"
    assert placement.cell(row, "property:None", template) == ""
    with pytest.raises(ValueError, match="not a field"):
        placement.cell(row, "quantity", template)


def test_evidence_names_both_rows() -> None:
    assert placement.EVIDENCE.level is Level.KICAD_VERIFIED
    assert placement.EVIDENCE.hypotheses == ("H-K-PCB-POS", "H-K-POS-ROWS")


def test_the_pin_to_pad_map_does_not_reach_the_placement_rows() -> None:
    """A pin bonded to several pads (change c0123) is no fact of a placement row: a row is a footprint."""
    design = design_of(Part("U1", "IC", x=10, y=10), Part("R1", "330", x=20, y=15, rot=90))
    mapped = dataclasses.replace(
        design,
        circuit=dataclasses.replace(
            design.circuit,
            components=tuple(
                dataclasses.replace(c, pin_pad_map=(("3", "3"), ("3", "EP"))) if c.ref == "U1" else c
                for c in design.circuit.components
            ),
        ),
    )
    assert mapped != design and rows_from_model(mapped) == rows_from_model(design)
    assert table(apply(rows_from_model(mapped), DEFAULT.placement), DEFAULT.placement) == table(
        apply(rows_from_model(design), DEFAULT.placement), DEFAULT.placement
    )
