# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Derived PCB library, first instance by reference and edited-instance report (c0160, task 3.2)."""

from __future__ import annotations

import dataclasses

import pytest
from _convert import source_of, two_layer

from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcblib import read_pcblib
from fenolite.convert import to_altium
from fenolite.convert.direction import Options
from fenolite.core.coords import Point, Size
from fenolite.model.board import Graphic, Text


@pytest.mark.parametrize("link", ("public:R_0603", "public:nested:R_0603"))
def test_two_instances_one_edited(link: str) -> None:
    design = two_layer()
    assert design.board is not None
    first = design.board.footprints[0]
    original = next(c for c in design.circuit.components if c.id == first.component_id)
    one = dataclasses.replace(original, ref="R1", lib_footprint_ref=link)
    two = dataclasses.replace(original, id="cmp-second", ref="R2", lib_footprint_ref=link)
    graphic = Graphic(
        id="gra-library",
        kind="line",
        layer="Dwgs.User",
        points=(Point(0, 0), Point(1000000, 0)),
        width=100000,
    )
    text = Text(
        id="txt-library",
        text="Ω",
        position=Point(0, 1000000),
        layer="F.SilkS",
        size=Size(1000000, 1000000),
        thickness=100000,
    )
    first = dataclasses.replace(
        first, lib_ref=link, graphics=(graphic,), texts=(text,), rotation=0, side="top", ext={}
    )
    pads = (
        dataclasses.replace(
            first.pads[0], position=Point(first.pads[0].position.x + 100000, first.pads[0].position.y)
        ),
        *first.pads[1:],
    )
    second = dataclasses.replace(first, id="fp-second", component_id=two.id, pads=pads)
    board = dataclasses.replace(design.board, footprints=(second, first))
    circuit = dataclasses.replace(design.circuit, components=(two, one))
    design = dataclasses.replace(design, board=board, circuit=circuit)
    result = to_altium.write(source_of(design), Options())
    name = design.header.name
    library = read_pcblib(result.files[f"{name}.PcbLib"])
    assert len(library.footprints) == 1
    footprint = library.footprints[0]
    assert footprint.name == "R_0603"
    document = read_pcbdoc(result.files[f"{name}.PcbDoc"])
    assert {dict(c.fields)["SOURCEFOOTPRINTLIBRARY"] for c in document.components} == {f"{name}.PcbLib"}
    assert all(dict(c.fields)["PATTERN"] == "R_0603" for c in document.components)
    assert footprint.pads[0].x == document.pads[len(second.pads)].x - document.components[1].x
    assert any(p.prefix.layer == 65 for p in footprint.primitives)
    assert "Ω" in footprint.wide_strings.values()
    row = result.report.row("footprint")
    assert row is not None and row.changed == 1 and row.lost == 0
    assert row.reasons[0].reason == "differs from the library footprint"
    assert row.reasons[0].ids == (second.id,)
    assert f"{name}.PcbLib".encode() in result.files[f"{name}.PrjPcb"]


def test_derived_library_disambiguates_storage_keys() -> None:
    from fenolite.backends.altium import pcblib
    from fenolite.model.library import FootprintDef

    names = ("Header_" + "x" * 30 + "_THT", "Header_" + "x" * 30 + "_SMD")
    footprints = tuple(pcblib.LibFootprint(FootprintDef(id=f"fp-{i}", name=n)) for i, n in enumerate(names))
    with pytest.raises(ValueError, match="one storage name"):
        pcblib.write_pcblib(footprints)
    data = pcblib.write_pcblib(footprints, disambiguate_storages=True)
    assert {f.name for f in read_pcblib(data).footprints} == set(names)
    assert data == pcblib.write_pcblib(footprints, disambiguate_storages=True)


def test_duplicate_designators_use_the_actual_source_footprint() -> None:
    from fenolite.backends.altium import lower

    design = two_layer()
    assert design.board is not None
    first = design.board.footprints[0]
    original = next(c for c in design.circuit.components if c.id == first.component_id)
    two = dataclasses.replace(original, id="cmp-second")
    second = dataclasses.replace(
        first,
        id="fp-second",
        component_id=two.id,
        pads=tuple(
            dataclasses.replace(p, position=Point(p.position.x + 100000, p.position.y)) for p in first.pads
        ),
    )
    design = dataclasses.replace(
        design,
        circuit=dataclasses.replace(design.circuit, components=(original, two)),
        board=dataclasses.replace(design.board, footprints=(first, second)),
    )
    inputs = lower.from_design(design, issues=[])
    actual_first = sorted(inputs.pcb.components, key=lambda c: (c.ref, c.unique_id))[0]
    linked, library = lower.derived_library(design, inputs)
    assert library[0].defn.id == actual_first.footprint.defn.id
    assert linked.changed["footprint"]["differs from the library footprint"] == (
        next(f.id for f in design.board.footprints if f.id != actual_first.footprint.defn.id),
    )


def test_bottom_unnumbered_pad_keeps_its_absolute_layer() -> None:
    from fenolite.backends.altium import lower, pcbdoc
    from fenolite.geometry.transform import Transform

    design = two_layer()
    assert design.board is not None
    original = design.board.footprints[0]
    pad = dataclasses.replace(
        original.pads[0], id="pad-free-bottom", number="", kind="smd", layers=("B.Cu",), net_id=None
    )
    footprint = dataclasses.replace(original, side="bottom", rotation=90000000, pads=(*original.pads, pad))
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=(footprint,)))
    inputs = lower.from_design(design, issues=[])
    assert inputs.pcb is not None
    free = next(p for p in inputs.pcb.free_pads if p.pad.id == pad.id)
    assert free.pad.layers == ("B.Cu",)
    assert free.pad.position == Transform.placement(footprint.position, footprint.rotation).apply(
        pad.position
    )
    document = read_pcbdoc(pcbdoc.write_pcbdoc(inputs.pcb))
    actual = next(p for p in document.pads if not p.name)
    assert actual.prefix.layer == 32


def test_detached_pad_roundtrip_checks_its_geometry(tmp_path) -> None:
    from fenolite.backends.altium import lower, rta3
    from fenolite.backends.altium.backend import AltiumBackend
    from fenolite.checks.rta3 import compare

    design = two_layer()
    path = tmp_path / "free.PcbDoc"
    baseline = lower.write_design(design, allow_lossy=True)
    path.write_bytes(baseline.files[f"{design.header.name}.PcbDoc"])
    design = AltiumBackend().read(path).design
    assert design.board is not None
    original = design.board.footprints[0]
    pad = dataclasses.replace(original.pads[0], id="pad-free", number="", net_id=None)
    fp = dataclasses.replace(original, pads=(*original.pads, pad))
    design = dataclasses.replace(
        design, board=dataclasses.replace(design.board, footprints=(fp, *design.board.footprints[1:]))
    )
    written = lower.write_design(design, allow_lossy=True)
    path = tmp_path / "free.PcbDoc"
    path.write_bytes(written.files[f"{design.header.name}.PcbDoc"])
    second = AltiumBackend().read(path).design
    assert rta3.rt_a3(design, written, second, compare=compare, from_board=True).equal
    assert second.board is not None
    free = next(f for f in second.board.footprints if "board_only" in f.attributes)
    moved = dataclasses.replace(free, position=Point(free.position.x + 100000, free.position.y))
    second = dataclasses.replace(
        second,
        board=dataclasses.replace(
            second.board, footprints=tuple(moved if f.id == free.id else f for f in second.board.footprints)
        ),
    )
    assert not rta3.rt_a3(design, written, second, compare=compare, from_board=True).equal
