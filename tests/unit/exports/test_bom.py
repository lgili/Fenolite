# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The neutral bill of materials (capability assembly-outputs, "Neutral BOM parts and lines" and "BOM
difference"; change c0064). Hermetic. Every part, value and property here is made up for these tests."""

from __future__ import annotations

import dataclasses

from _assembly import LED, QFP, R_0603, Part, design_of

from fenolite.core.evidence import Level
from fenolite.exports import bom
from fenolite.exports.assembly import DEFAULT, BomTemplate, Column
from fenolite.exports.bom import BomChange, BomPart, difference, group, parts_from_model, table

PARTS = (
    BomPart("R10", "330", R_0603),
    BomPart("R2", "10k", R_0603),
    BomPart("D1", "LED", LED),
    BomPart("R1", "10k", R_0603),
)


def _template(**changes: object) -> BomTemplate:
    return dataclasses.replace(DEFAULT.bom, **changes)  # type: ignore[arg-type]


def test_parts_of_a_model() -> None:
    design = design_of(
        Part("R10", "330"),
        Part("R2", "10k", properties={"Bin": "B", "Description": "made-up resistor", "Datasheet": "none"}),
        Part("D1", "LED", LED, attributes=("through_hole",)),
    )
    parts = parts_from_model(design)
    assert [p.ref for p in parts] == ["D1", "R2", "R10"]  # natural order
    r2 = parts[1]
    assert (r2.value, r2.footprint, r2.dnp) == ("10k", R_0603, False)
    assert (r2.description, r2.datasheet) == ("made-up resistor", "none")
    assert r2.properties == {"Bin": "B"}  # the five reserved names are fields, not properties
    assert parts[0].properties == {} and parts[0].description == ""


def test_parts_that_are_not_on_the_bill() -> None:
    design = design_of(
        Part("R1", "10k"),
        Part("H1", "hole", attributes=("board_only",)),
        Part("R3", "1k", attributes=("smd", "exclude_from_bom")),
        Part("#FLG1", "flag"),
    )
    assert [p.ref for p in parts_from_model(design)] == ["R1"]


def test_dnp_from_the_component_or_the_footprint() -> None:
    design = design_of(
        Part("R1", "10k"),
        Part("R2", "10k", dnp=True),
        Part("R3", "10k", attributes=("smd", "dnp")),
    )
    assert [(p.ref, p.dnp) for p in parts_from_model(design)] == [("R1", False), ("R2", True), ("R3", True)]


def test_a_design_without_a_board_has_no_part() -> None:
    design = dataclasses.replace(design_of(Part("R1", "10k")), board=None)
    assert parts_from_model(design) == ()


def test_grouping_by_value_and_footprint() -> None:
    lines = group(PARTS, _template(group_by=("value", "footprint")))
    assert [line.refs for line in lines] == [("D1",), ("R1", "R2"), ("R10",)]
    assert [line.quantity for line in lines] == [1, 2, 1]
    assert lines[1].key == ("10k", R_0603)
    assert lines[1].fields == {"refs": "R1,R2", "quantity": "2", "value": "10k", "footprint": R_0603}


def test_a_property_splits_a_group() -> None:
    parts = [
        dataclasses.replace(part, properties={"Bin": {"R1": "A", "R2": "B"}.get(part.ref, "")})
        for part in PARTS
    ]
    lines = group(parts, _template(group_by=("value", "footprint", "property:Bin")))
    assert [line.refs for line in lines] == [("D1",), ("R1",), ("R2",), ("R10",)]
    assert lines[1].fields["property:Bin"] == "A" and lines[1].key == ("10k", R_0603, "A")


def test_dnp_parts() -> None:
    design = design_of(Part("R1", "10k"), Part("R2", "10k", dnp=True), Part("R3", "330"))
    parts = parts_from_model(design)
    columns = (Column("refs", "refs"), Column("dnp", "dnp"))
    without = group(parts, _template(columns=columns, exclude_dnp=True))
    assert [line.refs for line in without] == [("R1",), ("R3",)]
    kept = group(parts, _template(columns=columns, group_by=("value", "dnp"), exclude_dnp=False))
    assert [(line.refs, line.fields["dnp"]) for line in kept] == [
        (("R1",), ""),
        (("R2",), "DNP"),
        (("R3",), ""),
    ]


def test_an_empty_group_by_gives_one_line_per_part() -> None:
    lines = group(PARTS, _template(group_by=()))
    assert [line.refs for line in lines] == [("D1",), ("R1",), ("R2",), ("R10",)]
    assert [line.key for line in lines] == [("D1",), ("R1",), ("R2",), ("R10",)]


def test_field_values_of_a_line() -> None:
    parts = (
        BomPart("R1", "10k", R_0603, description="thick film", properties={"Bin": "A"}),
        BomPart("R2", "10k", R_0603, description="thin film", properties={"Bin": "A"}),
        BomPart("U1", "MCU", QFP),
    )
    columns = tuple(
        Column(name, name)
        for name in ("item", "refs", "quantity", "footprint_name", "description", "datasheet", "property:Bin")
    )
    template = _template(columns=columns, ref_separator=" ")
    lines = group(parts, template)
    assert table(lines, template) == (
        ("1", "R1 R2", "2", "Mini_R_0603", "thick film thin film", "", "A"),
        ("2", "U1", "1", "Mini_QFP-32_7x7mm_P0.8mm", "", "", ""),
    )


def test_the_table_follows_the_columns() -> None:
    template = _template(columns=(Column("How many", "quantity"), Column("Which", "refs")))
    assert table(group(PARTS, template), template) == (("1", "D1"), ("2", "R1,R2"), ("1", "R10"))


def test_one_part_more() -> None:
    template = _template()
    first = group(PARTS, template)
    second = group((*PARTS, BomPart("R3", "10k", R_0603)), template)
    assert difference(first, second) == (
        BomChange(("10k", R_0603), "changed", ("R1", "R2"), ("R1", "R2", "R3")),
    )
    assert difference(first, first) == ()


def test_a_value_changed() -> None:
    template = _template()
    changed = tuple(dataclasses.replace(p, value="470") if p.ref == "R10" else p for p in PARTS)
    found = difference(group(PARTS, template), group(changed, template))
    assert found == (
        BomChange(("330", R_0603), "removed", ("R10",), ()),
        BomChange(("470", R_0603), "added", (), ("R10",)),
    )


def test_evidence_is_inferred_until_the_schematic_exists() -> None:
    assert bom.EVIDENCE_MODEL.level is Level.INFERRED
    assert bom.EVIDENCE_MODEL.hypotheses == ("H-K-BOM-MODEL",)
