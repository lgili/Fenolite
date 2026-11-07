# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Narrow canonical BOM-only representation and incompatible physical/electrical claims (c0334)."""

from dataclasses import replace

import pytest

from fenolite.backends.altium.lower import LossyWriteError, write_design
from fenolite.checks.equivalence.levels import level_components
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import Part
from fenolite.dsl.errors import DslError
from fenolite.exports.assembly import DEFAULT
from fenolite.exports.bom import group, parts_from_model
from fenolite.model import Component, Design, FootprintInstance, Pin
from fenolite.model.canonical import dumps, loads


def accessory(**kwargs) -> Component:
    return Component(id=derived_id("cmp", "bom-only", "M1"), ref="M1", **kwargs)


def test_default_canonical_bytes_are_unchanged_and_old_component_decodes() -> None:
    component = accessory()
    old = f'{{\n  "id": "{component.id}",\n  "ref": "M1"\n}}\n'
    assert dumps(component) == old
    assert not loads(old, Component).bom_only
    marked = replace(component, bom_only=True)
    assert loads(dumps(marked), Component) == marked
    assert '"bom_only": true' in dumps(marked)


@pytest.mark.parametrize(
    "defect", ["board_only", "pins", "pin_pad_map", "footprint_definition_ref", "placed"]
)
def test_model_bom_only_rejects_incompatible_claims(defect: str) -> None:
    changes = {
        "board_only": True,
        "pins": (Pin(id=derived_id("pin", "bom-only", "1"), number="1"),),
        "pin_pad_map": (("1", "1"),),
        "footprint_definition_ref": "Mini:Mini_R_0603",
    }
    component = accessory(bom_only=True, **({defect: changes[defect]} if defect in changes else {}))
    design = Design.new("bom-only", seed=1)
    design = replace(design, circuit=replace(design.circuit, components=(component,)))
    if defect == "placed":
        assert design.board is not None
        footprint = FootprintInstance(
            id=derived_id("fp", "bom-only", "1"),
            component_id=component.id,
            lib_ref="Mini:Mini_R_0603",
            position=Point(0, 0),
        )
        design = replace(design, board=replace(design.board, footprints=(footprint,)))
    assert any(issue.code == "model.bom-only" and issue.severity == "error" for issue in design.validate())


def test_dsl_bom_only_has_no_electrical_or_physical_interface() -> None:
    part = Part("M1", "Mini:Accessory", bom_only=True)
    with pytest.raises(DslError, match="no electrical pins"):
        part[1]
    with pytest.raises(DslError, match="no physical placement"):
        part.place(0, 0)
    with pytest.raises(DslError, match="bom_only excludes"):
        Part("M1", "Mini:Accessory", bom_only=True, board_only=True)


def test_canonical_bom_keeps_identity_dnp_metadata_and_quantity_without_board() -> None:
    first = accessory(bom_only=True, value="AUTHORED", lib_footprint_ref="Description:Only")
    second = replace(first, id=derived_id("cmp", "bom-only", "M2"), ref="M2", dnp=True)
    design = Design.new("bom-only", seed=1)
    design = replace(design, circuit=replace(design.circuit, components=(first, second)), board=None)
    parts = parts_from_model(design)
    assert [(part.ref, part.value, part.footprint, part.dnp) for part in parts] == [
        ("M1", "AUTHORED", "Description:Only", False),
        ("M2", "AUTHORED", "Description:Only", True),
    ]
    assert sum(line.quantity for line in group(parts, replace(DEFAULT.bom, exclude_dnp=False))) == 2
    removed = replace(design, circuit=replace(design.circuit, components=(first,)))
    assert any(d.kind == "component-missing" for d in level_components(design, removed)[0].differences)
    unmarked = replace(
        design, circuit=replace(design.circuit, components=(replace(first, bom_only=False), second))
    )
    assert any(d.kind == "bom-only" for d in level_components(design, unmarked)[0].differences)


@pytest.mark.parametrize("allow_lossy", [False, True])
def test_unsupported_altium_refuses_before_output_even_with_loss_acceptance(allow_lossy: bool) -> None:
    design = Design.new("bom-only", seed=1)
    design = replace(design, circuit=replace(design.circuit, components=(accessory(bom_only=True),)))
    with pytest.raises(LossyWriteError) as caught:
        write_design(design, allow_lossy=allow_lossy)
    assert caught.value.cli_code == "FEN-7001"
    assert caught.value.issues[0].where == "M1"
