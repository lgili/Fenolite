# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The later operations of an edit session on the kit board: flip, clone, add_component, remap_layer,
set_rule and the deletion of a polygon (change c0241, task 3.3)."""

from __future__ import annotations

from pathlib import Path

from fenolite.backends.altium import edit
from fenolite.backends.altium.edit import integrity
from fenolite.backends.altium.edit.session import unique_id_entries
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.pcbprims import PadRecord, RegionRecord, TrackRecord
from tests.unit.backends.altium.edit.conftest import OPEN, mm

PROBE = edit.Track((mm(10), mm(5)), (mm(20), mm(5)), "GND")
MULTI_LAYER, MECHANICAL_13, MECHANICAL_15 = 74, 69, 71


def _commit(session: edit.Session | edit.SchematicSession, out: Path) -> PcbDocument:
    receipt = session.commit(out, backup=False)
    assert receipt.written, receipt.issues
    data = out.read_bytes()
    assert integrity.check_pcbdoc(data) == ()
    return read_pcbdoc(data)


def _session(board: Path) -> edit.Session:
    session = edit.open(board, gates=OPEN)
    assert isinstance(session, edit.Session)
    return session


def test_flip_mirrors_the_pads_and_swaps_the_layers(board: Path, tmp_path: Path) -> None:
    before = read_pcbdoc(board.read_bytes())
    session = _session(board).flip(edit.Component("D1")).declare_connectivity("MID", "GND")
    doc = _commit(session, tmp_path / "flip.PcbDoc")
    [d1] = [c for c in doc.components if c.source_designator == "D1"]
    index = doc.components.index(d1)
    assert d1.layer == "BOTTOM"
    old = {p.name: p.x for p in before.pads if isinstance(p, PadRecord) and p.prefix.component == index}
    new = {p.name: p.x for p in doc.pads if isinstance(p, PadRecord) and p.prefix.component == index}
    assert new["1"] == old["1"] and new["2"] - new["1"] == -(old["2"] - old["1"])
    assert {p.prefix.layer for p in doc.pads if isinstance(p, PadRecord) and p.prefix.component == index} == {
        MULTI_LAYER
    }
    stated = _session(board).flip(edit.Component("D1"), old_side="BOTTOM").commit(tmp_path / "never.PcbDoc")
    assert [i.code for i in stated.issues] == ["altium.edit.assertion"]


def test_clone_copies_a_track_with_new_geometry(board: Path, tmp_path: Path) -> None:
    before = len(read_pcbdoc(board.read_bytes()).tracks)
    session = _session(board).clone(PROBE, start=(mm(10), mm(8)), end=(mm(20), mm(8)))
    doc = _commit(session, tmp_path / "clone.PcbDoc")
    assert len(doc.tracks) == before + 1


def test_clone_onto_a_layer_without_a_template_refuses(board: Path, tmp_path: Path) -> None:
    receipt = _session(board).clone(PROBE, layer="Mechanical 1").commit(tmp_path / "never.PcbDoc")
    [issue] = receipt.issues
    assert issue.code == "altium.edit.no-template" and "Mechanical 1" in issue.message


def test_clone_refuses_a_change_it_cannot_make(board: Path, tmp_path: Path) -> None:
    receipt = _session(board).clone(PROBE, diameter=mm(1)).commit(tmp_path / "never.PcbDoc")
    assert [i.code for i in receipt.issues] == ["altium.edit.assertion"]


def test_add_component_copies_its_records_with_new_ids(board: Path, tmp_path: Path) -> None:
    before = board.read_bytes()
    session = _session(board).add_component(board, "R1", designator="R9", at=(mm(32), mm(22)))
    doc = _commit(session, tmp_path / "add.PcbDoc")
    assert sorted(c.source_designator for c in doc.components) == ["D1", "R1", "R2", "R9"]
    [r9] = [c for c in doc.components if c.source_designator == "R9"]
    [r1] = [c for c in doc.components if c.source_designator == "R1"]
    assert r9.unique_id != r1.unique_id
    entries = unique_id_entries((tmp_path / "add.PcbDoc").read_bytes())
    ids = [e["UNIQUEID"] for e in entries]
    assert len(ids) == len(set(ids)) == len(unique_id_entries(before)) + 2
    index = doc.components.index(r9)
    assert len([p for p in doc.pads if isinstance(p, PadRecord) and p.prefix.component == index]) == 2


def test_add_component_of_a_designator_that_is_taken_refuses(board: Path, tmp_path: Path) -> None:
    receipt = _session(board).add_component(board, "R1", designator="R2").commit(tmp_path / "never.PcbDoc")
    assert [i.code for i in receipt.issues] == ["altium.edit.assertion"]


def test_remap_layer_moves_the_records_and_their_v7_layer(board: Path, tmp_path: Path) -> None:
    doc = _commit(_session(board).remap_layer("Mechanical 13", "Mechanical 15"), tmp_path / "remap.PcbDoc")
    layers = {t.prefix.layer for t in doc.tracks if isinstance(t, TrackRecord)}
    assert MECHANICAL_13 not in layers and MECHANICAL_15 in layers
    [region] = [r for r in doc.regions if isinstance(r, RegionRecord)]
    assert region.prefix.layer == MECHANICAL_15 and region.properties.get("V7_LAYER") == "MECHANICAL15"


def test_remap_layer_refuses_copper(board: Path, tmp_path: Path) -> None:
    receipt = _session(board).remap_layer("Top Layer", "Bottom Layer").commit(tmp_path / "never.PcbDoc")
    assert [i.code for i in receipt.issues] == ["altium.edit.assertion"]


def test_set_rule_states_the_old_value(board: Path, tmp_path: Path) -> None:
    doc = _commit(
        _session(board).set_rule("Clearance", "GAP", "9.8425mil", old="7.874mil"), tmp_path / "rule.PcbDoc"
    )
    assert [dict(r.fields).get("GAP") for r in doc.rules if r.name == "Clearance"] == ["9.8425mil"]
    wrong = _session(board).set_rule("Clearance", "GAP", "9.8425mil", old="10mil")
    assert [i.code for i in wrong.commit(tmp_path / "never.PcbDoc").issues] == ["altium.edit.assertion"]


def test_delete_a_polygon_compacts_the_pour_indices(board: Path, tmp_path: Path) -> None:
    doc = _commit(_session(board).delete(edit.Polygon("GND")), tmp_path / "poly.PcbDoc")
    assert [(p.name, p.pour_index) for p in doc.polygons] == [("VIN", 0)]
