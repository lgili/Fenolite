# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The later operations of an edit session on the kit board: flip, clone, add_component, remap_layer,
set_rule and the deletion of a polygon (change c0241, task 3.3)."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from fenolite.backends.altium import edit
from fenolite.backends.altium import pcbrecords as pcbrec
from fenolite.backends.altium.edit import integrity, ops
from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.edit.session import unique_id_entries
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.libboard import long_id
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


# c0389 task 4.2 (S-1588, case J23): a saved long track, arc or fill holds a long layer id after its short
# form, and Altium shows the primitive on that layer; the records below are authored in the saved long forms.
def _long_form(raw: bytes, length: int, layer: int) -> bytes:
    """``raw``, a short track or arc, as the saved long form of ``length`` bytes on ``layer``: five zero
    bytes, the 32-bit long layer id, then for the longer form the restrictions byte and three zero bytes."""
    kind, subs = rec.split(raw)
    body = subs[0] + bytes(5) + struct.pack("<I", long_id(layer))
    subs[0] = body + bytes(length - len(body))
    return rec.join(kind, subs)


def _fill(length: int, layer: int) -> bytes:
    """A fill (type 6) of ``length`` bytes on ``layer``, with its long layer id at 42 when it is that long."""
    body = bytearray(length)
    body[0] = layer
    if length >= 46:
        struct.pack_into("<I", body, 42, long_id(layer))
    return rec.join(6, [bytes(body)])


TRACK_36 = pcbrec.track_record(MECHANICAL_13, (0, 0), (1000, 0), 100)
ARC_47 = pcbrec.arc_record(MECHANICAL_13, pcbrec.ArcGeometry(0, 0, 500, 0.0, 90.0), 100)
LONG_FORMS = [
    (_long_form(TRACK_36, 45, MECHANICAL_13), 41),
    (_long_form(TRACK_36, 49, MECHANICAL_13), 41),
    (_long_form(ARC_47, 56, MECHANICAL_13), 52),
    (_long_form(ARC_47, 60, MECHANICAL_13), 52),
    (_fill(50, MECHANICAL_13), 42),
]


@pytest.mark.parametrize(("raw", "offset"), LONG_FORMS)
def test_relayer_moves_the_long_layer_id_of_a_long_form(raw: bytes, offset: int) -> None:
    moved = ops.relayer(raw, MECHANICAL_15)
    assert rec.prefix_of(moved)[0] == MECHANICAL_15
    assert rec.unpack(moved, offset, "<I") == (long_id(MECHANICAL_15),) == (0x0102000F,)
    before, after = rec.split(raw)[1][0], rec.split(moved)[1][0]
    changed = [i for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b]
    assert set(changed) <= {0, *range(offset, offset + 4)}


@pytest.mark.parametrize("raw", [TRACK_36, ARC_47])
def test_relayer_of_a_short_form_changes_the_layer_byte_alone(raw: bytes) -> None:
    moved = ops.relayer(raw, MECHANICAL_15)
    assert len(moved) == len(raw) and moved[6:] == raw[6:] and rec.prefix_of(moved)[0] == MECHANICAL_15


def test_relayer_refuses_a_form_without_a_recorded_long_layer_id() -> None:
    """No row records the bytes of a 46-byte fill: a remap refuses it, a flip keeps its other bytes."""
    raw = _fill(46, MECHANICAL_13)
    with pytest.raises(rec.RecordError):
        ops.relayer(raw, MECHANICAL_15)
    kept = ops.relayer(raw, MECHANICAL_15, strict=False)
    assert rec.prefix_of(kept)[0] == MECHANICAL_15 and kept[6:] == raw[6:]


def test_on_layer_reads_the_long_layer_id_of_a_long_form() -> None:
    """S-1654: a saved long track on Mechanical 20 holds the layer byte of Mechanical 16 (72); it is not on
    Mechanical 16, and a short track with that byte is."""
    deep = rec.patch(_long_form(TRACK_36, 49, MECHANICAL_13), 41, "<I", 0x01020014)
    deep = rec.set_prefix(deep, layer=72)
    assert not ops.on_layer(deep, 72)
    assert ops.on_layer(rec.set_prefix(TRACK_36, layer=72), 72)
    assert ops.on_layer(_long_form(TRACK_36, 45, MECHANICAL_13), MECHANICAL_13)


def _edited(board: Path, edit_state: object) -> Path:
    state = State.of(board.read_bytes(), file=board.name)
    edit_state(state)  # type: ignore[operator]
    board.write_bytes(state.data())
    return board


def test_remap_layer_moves_the_long_layer_id_of_a_saved_track(board: Path, tmp_path: Path) -> None:
    """Case J23 of S-1588: the Mechanical 13 tracks in their saved 49-byte form move to Mechanical 15 with
    their long layer id, so Altium no longer finds them on Mechanical 13."""

    def lengthen(state: State) -> None:
        tracks = state.get("Tracks6")
        for position in [i for i, raw in enumerate(tracks) if rec.prefix_of(raw)[0] == MECHANICAL_13]:
            state.replace("Tracks6", position, _long_form(tracks[position], 49, MECHANICAL_13))

    doc = _commit(_session(_edited(board, lengthen)).remap_layer("Mechanical 13", "Mechanical 15"),
                  tmp_path / "remap.PcbDoc")  # fmt: skip
    moved = [t for t in doc.tracks if isinstance(t, TrackRecord) and len(rec.split(t.raw)[1][0]) == 49]
    assert moved and {t.prefix.layer for t in moved} == {MECHANICAL_15}
    assert {rec.unpack(t.raw, 41, "<I") for t in moved} == {(long_id(MECHANICAL_15),)}


def test_set_rule_states_the_old_value(board: Path, tmp_path: Path) -> None:
    doc = _commit(
        _session(board).set_rule("Clearance", "GAP", "9.8425mil", old="7.874mil"), tmp_path / "rule.PcbDoc"
    )
    assert [dict(r.fields).get("GAP") for r in doc.rules if r.name == "Clearance"] == ["9.8425mil"]
    wrong = _session(board).set_rule("Clearance", "GAP", "9.8425mil", old="10mil")
    assert [i.code for i in wrong.commit(tmp_path / "never.PcbDoc").issues] == ["altium.edit.assertion"]


def test_set_rule_changes_the_gap_and_the_generic_clearance_together(board: Path, tmp_path: Path) -> None:
    """Case J23 of S-1588: Altium shows a Clearance's gap from ``GENERICCLEARANCE``, which a saved rule holds
    equal to ``GAP`` (``pcb-copper.md``), so both keys take the new value, in either spelling."""
    for key in ("GAP", "GENERICCLEARANCE"):
        doc = _commit(_session(board).set_rule("Clearance", key, "9.8425mil", old="7.874mil"),
                      tmp_path / f"{key}.PcbDoc")  # fmt: skip
        (fields,) = [dict(r.fields) for r in doc.rules if r.name == "Clearance"]
        assert fields["GAP"] == fields["GENERICCLEARANCE"] == "9.8425mil"


def test_set_rule_refuses_a_gap_that_differs_from_its_generic_clearance(board: Path, tmp_path: Path) -> None:
    def split_gap(state: State) -> None:
        rules = state.properties("Rules6")
        (position,) = [i for i, r in enumerate(rules) if r.get("NAME") == "Clearance"]
        raw = rec.set_property(rules[position].raw, {"GENERICCLEARANCE": "8mil"}, lead=2)
        state.replace("Rules6", position, raw)

    session = _session(_edited(board, split_gap)).set_rule("Clearance", "GAP", "9.8425mil", old="7.874mil")
    receipt = session.commit(tmp_path / "never.PcbDoc")
    assert [i.code for i in receipt.issues] == ["altium.edit.assertion"]
    assert "GENERICCLEARANCE" in receipt.issues[0].message


def test_delete_a_polygon_compacts_the_pour_indices(board: Path, tmp_path: Path) -> None:
    doc = _commit(_session(board).delete(edit.Polygon("GND")), tmp_path / "poly.PcbDoc")
    assert [(p.name, p.pour_index) for p in doc.polygons] == [("VIN", 0)]
