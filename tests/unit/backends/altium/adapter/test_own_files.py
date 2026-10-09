# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Own files import to the model they were written from (capability altium-import, "Own files import to
the model they were written from"; change c0043): each example is built for the Altium target under
tmp_path, in the ASCII and in the binary schematic form, and its project is read by AltiumBackend.
Evidence of level INFERRED: Fenolite's writers read by Fenolite's readers and adapter."""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from pathlib import Path

import pytest
from _altium import (
    EXAMPLE_NETS,
    HIER_NETS,
    NO_CONNECT_MARKS,
    NO_CONNECT_NETS,
    SAMPLE_NETS,
    blink,
    blink_resolver,
    blink_tree,
    example,
    example_resolver,
    hier,
    no_connect_example,
    sample,
)
from _altium_copper import routed_build

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.base import ReadResult
from fenolite.dsl import placements, to_model
from fenolite.lens.altium import build_altium
from fenolite.lens.build import BuildOutput
from fenolite.model.design import Design

DATA = Path(__file__).resolve().parents[5] / "tests" / "data" / "altium"
FORMS = ("ascii", "binary")


def nets_of(design: Design) -> dict[str, set[tuple[str, str]]]:
    refs = {c.id: c.ref for c in design.circuit.components}
    return {n.name: {(refs[m.component_id], m.pin) for m in n.members} for n in design.circuit.nets}


def marks_of(design: Design) -> set[tuple[str, str]]:
    refs = {c.id: c.ref for c in design.circuit.components}
    return {(refs[m.component_id], m.pin) for m in design.circuit.no_connects}


def read_built(folder: Path, files: Mapping[str, bytes]) -> ReadResult:
    """Write the project files of a build under folder and read its project file."""
    folder.mkdir(parents=True, exist_ok=True)
    projects = [name for name in files if name.endswith(".PrjPcb")]
    assert len(projects) == 1
    for name, data in files.items():
        if not name.startswith(".fenolite/"):
            (folder / name).write_bytes(data)
    return AltiumBackend().read(folder / projects[0])


def check(result: ReadResult, built: BuildOutput, *, board: bool = False) -> Design:
    """The comparisons of the requirement: nets by name, no-connect marks, and each component's reference,
    value and footprint name."""
    design, model = result.design, built.design
    assert nets_of(design) == nets_of(model)
    assert marks_of(design) == marks_of(model)
    mine = {c.ref: c for c in design.circuit.components}
    assert sorted(mine) == sorted(c.ref for c in model.circuit.components)
    assert len(mine) == len(design.circuit.components)
    for want in model.circuit.components:
        got = mine[want.ref]
        assert want.value in ("", got.value), want.ref  # an empty value is written as the symbol's
        if want.lib_footprint_ref:
            assert got.lib_footprint_ref.split(":")[-1] == want.lib_footprint_ref.split(":")[-1], want.ref
    assert (design.board is not None) == board
    assert [i for i in result.issues if i.severity == "error"] == []
    codes = {i.code for i in result.issues}
    assert not codes & {"altium.import.linked-by-designator", "altium.import.pcb-only-component"}
    return design


@pytest.mark.parametrize("form", FORMS)
def test_sample(tmp_path: Path, form: str) -> None:
    design = sample()
    built = build_altium(to_model(design), name=design.name, form=form)  # type: ignore[arg-type]
    read = check(read_built(tmp_path, built.files), built)
    assert nets_of(read) == SAMPLE_NETS and marks_of(read) == set()


@pytest.mark.parametrize("form", FORMS)
def test_kicad_example(tmp_path: Path, form: str) -> None:
    design = example()
    with tempfile.TemporaryDirectory() as folder:
        built = build_altium(
            to_model(design),
            name=design.name,
            form=form,
            resolver=example_resolver(Path(folder)),  # type: ignore[arg-type]
        )
    read = check(read_built(tmp_path, built.files), built)
    assert nets_of(read) == EXAMPLE_NETS
    assert len(read.by_ref["U1"].pins) == len(built.design.by_ref["U1"].pins)


@pytest.mark.parametrize("form", FORMS)
def test_no_connect(tmp_path: Path, form: str) -> None:
    design = no_connect_example()
    with tempfile.TemporaryDirectory() as folder:
        built = build_altium(
            to_model(design),
            name=design.name,
            form=form,
            resolver=example_resolver(Path(folder)),  # type: ignore[arg-type]
        )
    read = check(read_built(tmp_path, built.files), built)
    assert nets_of(read) == NO_CONNECT_NETS and marks_of(read) == NO_CONNECT_MARKS
    members = {(m.component_id, m.pin) for net in read.circuit.nets for m in net.members}
    assert not members & {(m.component_id, m.pin) for m in read.circuit.no_connects}


@pytest.mark.parametrize("form", FORMS)
def test_hier(tmp_path: Path, form: str) -> None:
    design = hier()
    built = build_altium(to_model(design), name=design.name, form=form, sheets="modules")  # type: ignore[arg-type]
    result = read_built(tmp_path, built.files)
    read = check(result, built)
    assert nets_of(read) == HIER_NETS
    (scope,) = [i for i in result.issues if i.code == "altium.import.scope"]
    assert "hierarchical" in scope.message
    assert sorted(m.path for m in read.circuit.modules) == sorted(
        m.path for m in built.design.circuit.modules
    )
    by_path = {m.path: m for m in read.circuit.modules}
    refs = {c.id: c for c in read.circuit.components}
    for module in built.design.circuit.modules:
        owned = [refs[i] for i in by_path[module.path].component_ids]
        assert len(owned) == len(module.component_ids)
        assert all(c.path == f"{module.path}/{c.ref}" for c in owned)
    if form == "ascii":  # the ASCII form writes no harness record (``altium.not-lowered``)
        assert read.circuit.interfaces == ()
        return
    (harness,) = read.circuit.interfaces
    (want,) = [i for i in built.design.circuit.interfaces if i.kind == "harness"]
    names = {n.id: n.name for n in read.circuit.nets}
    model_names = {n.id: n.name for n in built.design.circuit.nets}
    assert (harness.name, harness.kind) == (want.name, "harness")
    assert {k: names[v] for k, v in harness.members.items()} == {
        k: model_names[v] for k, v in want.members.items()
    }
    sheet_of = {c.id: c.path.split("/")[0] for c in read.circuit.components}
    for net in read.circuit.nets:
        if net.name.startswith("SPI_"):
            assert sorted(sheet_of[m.component_id] for m in net.members) == sorted(by_path)


def test_hier_sample_files_of_c0037() -> None:
    result = AltiumBackend().read(DATA / "hier" / "altium_hier.PrjPcb")
    assert nets_of(result.design) == HIER_NETS and len(result.design.circuit.modules) == 2


def test_flat_sample_files() -> None:
    """sample, kicad_example and no_connect: the committed files of the three flat examples."""
    assert nets_of(AltiumBackend().read(DATA / "sample" / "altium_sample.PrjPcb").design) == SAMPLE_NETS
    assert (
        nets_of(AltiumBackend().read(DATA / "kicad_example" / "altium_kicad.PrjPcb").design) == EXAMPLE_NETS
    )
    marked = AltiumBackend().read(DATA / "no_connect" / "altium_no_connect.PrjPcb").design
    assert nets_of(marked) == NO_CONNECT_NETS and marks_of(marked) == NO_CONNECT_MARKS


@pytest.mark.parametrize("form", FORMS)
def test_blink_project(tmp_path: Path, form: str) -> None:
    project = blink_tree(tmp_path / "tree")
    design = blink()
    built = build_altium(
        to_model(design),
        name=design.name,
        form=form,  # type: ignore[arg-type]
        placed=tuple(placements(design)),
        resolver=blink_resolver(tmp_path / "tree", project),
    )
    read = check(read_built(tmp_path / "out", built.files), built, board=True)
    assert read.board is not None and built.design.board is not None
    ids = {c.id: c.ref for c in read.circuit.components}
    placed = {ids[fp.component_id]: fp for fp in read.board.footprints}
    model_refs = {c.id: c.ref for c in built.design.circuit.components}
    for footprint in built.design.board.footprints:
        got = placed[model_refs[footprint.component_id]]
        assert (got.side, got.rotation) == (footprint.side, footprint.rotation)
    nets = {n.id for n in read.circuit.nets}
    assert all(pad.net_id is None or pad.net_id in nets for fp in read.board.footprints for pad in fp.pads)


def test_routed_project(tmp_path: Path) -> None:
    built = routed_build(tmp_path / "tree")
    read = check(read_built(tmp_path / "out", built.files), built, board=True)
    assert read.board is not None and built.design.board is not None
    board, want = read.board, built.design.board
    assert (len(board.tracks), len(board.arcs), len(board.vias)) == (
        len(want.tracks),
        len(want.arcs),
        len(want.vias),
    )
    assert len(board.zones) == sum(len(zone.layers) for zone in want.zones)
    assert len([layer for layer in board.layers if layer.kind == "copper"]) == 4


# --- copper locks (change c0108; capability altium-import, "Copper locks from an Altium board") -----


def _locked_counts(design: Design) -> dict[str, int]:
    assert design.board is not None
    board = design.board
    return {
        "tracks": sum(1 for item in board.tracks if item.locked),
        "arcs": sum(1 for item in board.arcs if item.locked),
        "vias": sum(1 for item in board.vias if item.locked),
    }


def test_locked_copper_survives_the_round_trip(tmp_path: Path) -> None:
    """Scenario "Locks survive the round trip": exactly the track, the arc and the via that were locked
    are locked in the import of the written project."""
    import dataclasses

    from _altium_copper import routed_model

    model = routed_model()
    assert model.board is not None
    board = model.board
    track, arc, via = board.tracks[0], board.arcs[0], board.vias[0]
    locked = dataclasses.replace(
        model,
        board=dataclasses.replace(
            board,
            tracks=(dataclasses.replace(track, locked=True), *board.tracks[1:]),
            arcs=(dataclasses.replace(arc, locked=True), *board.arcs[1:]),
            vias=(dataclasses.replace(via, locked=True), *board.vias[1:]),
        ),
    )
    built = routed_build(tmp_path / "tree", locked)
    read = read_built(tmp_path / "out", built.files).design
    assert read.board is not None
    assert _locked_counts(read) == {"tracks": 1, "arcs": 1, "vias": 1}
    (got_track,) = [item for item in read.board.tracks if item.locked]
    (got_via,) = [item for item in read.board.vias if item.locked]
    (got_arc,) = [item for item in read.board.arcs if item.locked]
    # lengths come back within one file unit (2.54 nm)
    assert got_track.layer == track.layer and abs(got_track.width - track.width) <= 2
    assert abs(got_via.diameter - via.diameter) <= 2 and abs(got_via.drill - via.drill) <= 2
    assert got_arc.layer == arc.layer and abs(got_arc.width - arc.width) <= 2
    # but for the locks, the import is that of the same project written without them
    plain = read_built(tmp_path / "plain", routed_build(tmp_path / "tree2").files).design
    assert plain.board is not None and _locked_counts(plain) == {"tracks": 0, "arcs": 0, "vias": 0}

    def unlocked(items):  # type: ignore[no-untyped-def]
        return tuple(dataclasses.replace(item, locked=False, provenance=None) for item in items)

    assert unlocked(read.board.tracks) == unlocked(plain.board.tracks)
    assert unlocked(read.board.arcs) == unlocked(plain.board.arcs)
    assert unlocked(read.board.vias) == unlocked(plain.board.vias)


def test_locked_is_false_for_a_document_without_locks() -> None:
    """Scenario "A document without locks": the committed routed sample imports with nothing locked."""
    sample = Path(__file__).resolve().parents[4] / "data" / "altium" / "routed"
    read = AltiumBackend().read(sample / "routed.PrjPcb").design
    assert read.board is not None and read.board.tracks and read.board.vias
    assert _locked_counts(read) == {"tracks": 0, "arcs": 0, "vias": 0}
