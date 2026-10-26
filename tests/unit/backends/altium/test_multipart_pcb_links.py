# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""PCB links follow the multipart identity observed in native compilation (c0166)."""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

import pytest
from _altium import example_model

from fenolite.backends.altium import hierarchy, project
from fenolite.backends.altium.pcbdoc import PcbDocSpec, PlacedComponent, write_pcbdoc
from fenolite.backends.altium.pcblib import LibFootprint
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.sch import Component, read_schematic
from fenolite.core.coords import Point, Size
from fenolite.model.board import Pad
from fenolite.model.library import FootprintDef


@pytest.mark.parametrize("parts", [1, 2, 3])
@pytest.mark.parametrize("sheets", ["flat", "modules"])
@pytest.mark.parametrize("form", ["binary", "ascii"])
def test_pcb_links_to_last_written_symbol_part(
    parts: int, sheets: Literal["flat", "modules"], form: Literal["binary", "ascii"]
) -> None:
    model, symbols = example_model()
    component = next(c for c in model.circuit.components if c.ref == "U1")
    body = symbols[component.lib_symbol_ref]
    symbols[component.lib_symbol_ref] = replace(
        body,
        parts=parts,
        pins=tuple(
            replace(pin, part=0 if pin.part == 0 else index % parts + 1)
            for index, pin in enumerate(body.pins)
        ),
        rectangles=tuple(replace(body.rectangles[0], part=part) for part in range(1, parts + 1)),
        graphics=(),
    )
    if sheets == "modules":
        component = replace(component, properties={**component.properties, project.PATH_PROPERTY: "amp/U1"})
        model = model.replace_entity(component)
    primary = project.unique_id(component.id)
    sheet_id = project.unique_id(hierarchy.symbol_key("amp"))
    footprint = FootprintDef(
        id="fp_uid_probe",
        name="UID_PROBE",
        pads=tuple(
            Pad(
                id=f"pad_uid_{pin.number}",
                number=pin.number,
                shape="circle",
                position=Point(index * 2_000_000, 0),
                size=Size(1_000_000, 1_000_000),
                layers=("F.Cu",),
            )
            for index, pin in enumerate(component.pins)
        ),
    )
    pcb = PcbDocSpec(
        outline=(Point(0, 0), Point(30_000_000, 0), Point(30_000_000, 20_000_000), Point(0, 20_000_000)),
        components=(
            PlacedComponent(
                ref="U1",
                unique_id=primary,
                comment=component.value,
                footprint=LibFootprint(footprint),
                footprint_library="probe.PcbLib",
                lib_reference="DUAL",
                component_library="probe.SchLib",
                at=Point(5_000_000, 5_000_000),
                sheet=(sheet_id, "amp") if sheets == "modules" else None,
            ),
        ),
    )
    files = project.write_project(model, name="probe", pcb=pcb, symbols=symbols, sheets=sheets, form=form)
    source_ids = []
    for name, data in files.items():
        if not name.endswith(".SchDoc"):
            continue
        document = read_schematic(data)
        by_ref = {record.ref: record for record in document.records}
        for record in document.records:
            if isinstance(record, Component) and any(
                by_ref[child].props.text("TEXT") == "U1" and by_ref[child].props.text("RECORD") == "34"
                for child in record.children
            ):
                source_ids.append((record.props.int("CURRENTPARTID"), record.props.text("UNIQUEID")))
    assert [part for part, _uid in source_ids] == list(range(1, parts + 1))
    expected = primary if parts == 1 else project.unique_id(f"{component.id}#{parts}")
    assert source_ids[-1][1] == expected
    document = read_pcbdoc(files["probe.PcbDoc"])
    (linked,) = document.components
    prefix = f"\\{sheet_id}" if sheets == "modules" else ""
    assert linked.source_unique_id == f"{prefix}\\{expected}"
    original = read_pcbdoc(write_pcbdoc(pcb, filename="probe.PcbDoc"))
    assert linked.unique_id == original.components[0].unique_id
    assert document.unique_id == original.unique_id
    assert pcb.components[0].unique_id == primary
    if parts == 1:
        assert files["probe.PcbDoc"] == write_pcbdoc(pcb, filename="probe.PcbDoc")
