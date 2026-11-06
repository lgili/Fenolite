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


def test_bottom_unnumbered_pad_stays_in_its_component() -> None:
    """A pad without a number is a pad of its component with an empty name (change c0433), on its own
    layer: the bottom-side component swaps it to the top in the definition and the record holds Bottom."""
    from fenolite.backends.altium import lower, pcbdoc

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
    assert not inputs.pcb.free_pads
    (component,) = inputs.pcb.components
    assert [p.id for p in component.footprint.defn.pads] == [*(p.id for p in original.pads), pad.id]
    assert "pad" not in inputs.changed
    document = read_pcbdoc(pcbdoc.write_pcbdoc(inputs.pcb))
    actual = next(p for p in document.pads if not p.name)
    assert actual.prefix.layer == 32
    assert actual.prefix.component is not None


def test_unnumbered_pad_roundtrip_checks_its_geometry(tmp_path) -> None:
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
    assert not [f for f in second.board.footprints if "board_only" in f.attributes]
    owner = next(f for f in second.board.footprints if any(not p.number for p in f.pads))
    assert len(owner.pads) == len(fp.pads)
    pads = tuple(
        dataclasses.replace(p, position=Point(p.position.x + 100000, p.position.y)) if not p.number else p
        for p in owner.pads
    )
    moved = dataclasses.replace(owner, pads=pads)
    second = dataclasses.replace(
        second,
        board=dataclasses.replace(
            second.board, footprints=tuple(moved if f.id == owner.id else f for f in second.board.footprints)
        ),
    )
    assert not rta3.rt_a3(design, written, second, compare=compare, from_board=True).equal


def test_unnumbered_hole_pads_stay_in_their_component(tmp_path) -> None:
    """A pad without a number whose copper is its hole stays a pad of its component (change c0433): RT-A3
    compares it there, round or slotted, and a moved one is a difference (capability
    altium-verification, "Unnumbered pads in RT-A3")."""
    from fenolite.backends.altium import lower, rta3
    from fenolite.backends.altium.backend import AltiumBackend
    from fenolite.checks.rta3 import compare
    from fenolite.model.board import Padstack

    design = two_layer()
    path = tmp_path / "holes.PcbDoc"
    path.write_bytes(lower.write_design(design, allow_lossy=True).files[f"{design.header.name}.PcbDoc"])
    design = AltiumBackend().read(path).design
    assert design.board is not None
    owner = next(fp for fp in design.board.footprints if fp.pads[0].kind == "thru_hole")
    base = owner.pads[0]
    drill = base.drill
    assert drill is not None
    round_hole = dataclasses.replace(
        base, id="pad-hole", number="", net_id=None, kind="np_thru_hole", size=Size(drill, drill),
        position=Point(base.position.x + 3_000_000, base.position.y),
    )  # fmt: skip
    slot = dataclasses.replace(
        base, id="pad-slot", number="", net_id=None, kind="np_thru_hole", shape="oval",
        size=Size(2 * drill, drill), position=Point(base.position.x - 3_000_000, base.position.y),
        padstack=Padstack(id="ps-slot", hole_shape="slot", hole_length=2 * drill),
    )  # fmt: skip
    fp = dataclasses.replace(owner, pads=(*owner.pads, round_hole, slot))
    design = dataclasses.replace(
        design,
        board=dataclasses.replace(
            design.board, footprints=tuple(fp if f.id == owner.id else f for f in design.board.footprints)
        ),
    )
    written = lower.write_design(design, allow_lossy=True)
    path.write_bytes(written.files[f"{design.header.name}.PcbDoc"])
    second = AltiumBackend().read(path).design
    assert second.board is not None
    assert not second.board.holes
    assert not [f for f in second.board.footprints if "board_only" in f.attributes]
    read = next(f for f in second.board.footprints if f.position == fp.position)
    assert sorted((p.drill, p.number) for p in read.pads if not p.number) == [(drill, ""), (drill, "")]
    assert rta3.rt_a3(design, written, second, compare=compare, from_board=True).equal
    pads = tuple(
        dataclasses.replace(p, position=Point(p.position.x + 100_000, p.position.y))
        if not p.number and p.shape == "circle"
        else p
        for p in read.pads
    )
    moved = dataclasses.replace(read, pads=pads)
    second = dataclasses.replace(
        second,
        board=dataclasses.replace(
            second.board, footprints=tuple(moved if f.id == read.id else f for f in second.board.footprints)
        ),
    )
    assert not rta3.rt_a3(design, written, second, compare=compare, from_board=True).equal
