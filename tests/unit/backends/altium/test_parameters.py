# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Component parameters (capability altium-schematic-writer, "Component parameters"; change c0086): which
properties become hidden parameters, their records, and what happens to one that cannot be written."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from _altium_tree import documents, read_back, tree_build, tree_model

from fenolite.backends.altium.project import parameters_of, unique_id
from fenolite.backends.altium.read.sch import Parameter
from fenolite.model.circuit import Component
from fenolite.model.design import Design


def part(**properties: str) -> Component:
    return Component(id="cmp_1", ref="R1", lib_symbol_ref="L:R", properties=properties)


def with_properties(model: Design, ref: str, properties: dict[str, str]) -> Design:
    component = model.by_ref[ref]
    changed = dataclasses.replace(component, properties={**component.properties, **properties})
    return model.replace_entity(changed)


def test_which_properties_are_parameters() -> None:
    component = part(**{"fenolite.path": "a/R1", "MPN": "X-1", "Footprint": "L:F", "Value": "1k", "Empty": "",
                        "Comment": "c", "Datasheet": "https://example.org/r.pdf", "Alpha": "a"})  # fmt: skip
    kept, skipped = parameters_of(component)
    assert (
        kept == [("Alpha", "a"), ("Datasheet", "https://example.org/r.pdf"), ("MPN", "X-1")] and not skipped
    )


def test_properties_that_cannot_be_written() -> None:
    component = part(
        **{"MPN": "X-1", "mpn": "x-2", "Nome": "Indutância", "Ré": "x", "Ref": "=Other", "Pipe": "a|b"}
    )
    kept, skipped = parameters_of(component)
    assert kept == [("MPN", "X-1")]
    assert {name: why.split(" ", 2)[1] for name, why in skipped} == {
        "mpn": "name", "Nome": "value", "Ré": "name", "Ref": "value", "Pipe": "value",
    }  # fmt: skip
    kept, skipped = parameters_of(component, form="binary")
    assert ("Nome", "Indutância") in kept and "Nome" not in dict(skipped)


def test_manufacturer_part_number(tmp_path: Path) -> None:
    """Scenario "Manufacturer part number": the component holds a hidden parameter ``MPN`` with the value
    ``X-1``, in both forms, and the importer gives it back as a property."""
    for form in ("binary", "ascii"):
        output = tree_build(form=form)
        power = documents(output)["tree_power.SchDoc"]
        (c1,) = [c for c in power.components() if any(
            isinstance(r, Parameter) and r.name == "MPN" for r in power.children_of(c))]  # fmt: skip
        found = [r for r in power.children_of(c1) if isinstance(r, Parameter) and r.name not in ("Comment",)]
        assert [(p.name, p.hidden) for p in found] == [("MPN", True), ("Note", True)]  # name order
        assert found[0].text == "X-1" and found[0].location == c1.location
        assert found[0].unique_id == unique_id(f"{tree_model().by_ref['C1'].id}:parameter:MPN")
        design = read_back(tmp_path / form, output)
        assert {
            c.ref: c.properties.get("MPN") for c in design.circuit.components if "MPN" in c.properties
        } == {"C1": "X-1"}
    summary = tree_build().summary["schematic"]
    assert isinstance(summary, dict) and summary["parameters"] == 2


def test_unwritable_property_is_kept_in_the_model_and_reported() -> None:
    model = with_properties(tree_model(), "U1", {"Supplier": "a|b", "Class": "A"})
    output = tree_build(model)
    assert output.files
    (found,) = [i for i in output.issues if i.code == "altium.not-lowered" and i.where == "parameters"]
    assert found.severity == "info" and "U1 'Supplier'" in found.message
    top = documents(output)["tree.SchDoc"]
    names = sorted(p.name for p in top.of_type(Parameter) if p.name not in ("Comment",))
    assert names == ["Class"]


def test_a_design_without_properties_keeps_its_bytes() -> None:
    model = tree_model()
    plain = tree_build(model)
    internal = with_properties(model, "U1", {"fenolite.note": "x", "Empty": ""})
    assert tree_build(internal).files["tree.SchDoc"] == plain.files["tree.SchDoc"]
