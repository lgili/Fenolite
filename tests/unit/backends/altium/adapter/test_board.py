# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A PCB document as a design: nets, net classes, footprints and the synthesised circuit (capability
altium-import, "Nets and net classes of a board", "Footprint instances and pads" and "Circuit synthesised
from a board"; change c0043)."""

from __future__ import annotations

import dataclasses
import hashlib
import tempfile
from pathlib import Path

import _altium_records as rec
from _altium import blink, blink_resolver
from _altium_copper import routed_model

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.dsl import placements, to_model
from fenolite.geometry.transform import Transform
from fenolite.lens.build import build_design
from fenolite.model.design import Design

DATA = Path(__file__).resolve().parents[5] / "tests" / "data" / "altium"
MIL = rec.MIL


def read(path: Path, issues: list[Issue] | None = None) -> Design:
    data = path.read_bytes()
    return import_board(
        read_pcbdoc(data), file=path.name, sha256=hashlib.sha256(data).hexdigest(), issues=issues
    )


def kicad_blink(tmp_path: Path) -> Design:
    """The board that the KiCad build of the blink script writes, read by KicadBackend."""
    design = blink()
    with tempfile.TemporaryDirectory() as folder:
        built = build_design(
            to_model(design), placements(design), name="blink", copper=design.copper,  # type: ignore[arg-type]
            resolver=blink_resolver(Path(folder)),
        )  # fmt: skip
    board = tmp_path / "blink.kicad_pcb"
    board.write_bytes(built.files["blink.kicad_pcb"])
    return KicadBackend().read(board).design


def nets_of(design: Design) -> dict[str, set[tuple[str, str]]]:
    refs = {c.id: c.ref for c in design.circuit.components}
    return {n.name: {(refs[m.component_id], m.pin) for m in n.members} for n in design.circuit.nets}


# --- nets and classes -----------------------------------------------------------------------------------


def test_nets_are_kept_as_written_and_duplicates_are_one_net() -> None:
    issues: list[Issue] = []
    document = rec.document(nets=["GND", "+3V3", "GND"], tracks=[rec.track((0, 0), (9, 0), net=2)])
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    assert [net.name for net in design.circuit.nets] == ["GND", "+3V3"]
    assert design.board is not None and design.board.tracks[0].net_id == design.nets_by_name["GND"].id
    found = [i for i in issues if i.code == "altium.import.duplicate-net"]
    assert len(found) == 1 and found[0].where == "GND"


def test_classes_of_the_routed_sample() -> None:
    design = read(DATA / "routed" / "routed.PcbDoc")
    (power,) = [c for c in design.circuit.netclasses if c.name == "PWR"]
    assert (power.clearance, power.track_width, power.via_diameter, power.via_drill) == (None,) * 4
    assert design.nets_by_name["GND"].netclass_id == power.id
    assert design.nets_by_name["VIN"].netclass_id == power.id
    assert power.native_ids == {"altium": "class:PWR"}


def test_super_class_and_other_kinds_are_skipped() -> None:
    issues: list[Issue] = []
    classes = [rec.net_class("All Nets", [], superclass=True), rec.net_class("Parts", ["R1"], kind=1)]
    design = import_board(rec.document(classes=classes), file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    assert design.circuit.netclasses == ()
    (unmapped,) = [i for i in issues if i.code == "altium.import.unmapped"]
    assert "classes 2" in unmapped.message


def test_classes_first_by_name_and_unknown_members() -> None:
    issues: list[Issue] = []
    classes = [rec.net_class("Z", ["A", "nope"]), rec.net_class("B", ["A"])]
    design = import_board(rec.document(nets=["A"], classes=classes), file="a", sha256=rec.SHA, issues=issues)
    net = design.nets_by_name["A"]
    by_name = {c.name: c.id for c in design.circuit.netclasses}
    assert net.netclass_id == by_name["B"] and net.ext["altium"].payload == (("classes", "Z"),)
    codes = [i.code for i in issues]
    assert codes.count("altium.import.unknown-member") == 1 and codes.count("altium.import.multi-class") == 1


# --- footprints -----------------------------------------------------------------------------------------


def test_footprints_of_the_blink_sample(tmp_path: Path) -> None:
    mine, theirs = read(DATA / "blink" / "blink.PcbDoc"), kicad_blink(tmp_path)
    assert mine.board is not None and theirs.board is not None
    kicad = {theirs.by_id[fp.component_id].ref: fp for fp in theirs.board.footprints}  # type: ignore[attr-defined]
    altium = {mine.by_id[fp.component_id].ref: fp for fp in mine.board.footprints}  # type: ignore[attr-defined]
    assert sorted(altium) == sorted(kicad) == ["D1", "R1", "U1"]
    shifts = set()
    net_name = {n.id: n.name for n in mine.circuit.nets}
    their_net = {n.id: n.name for n in theirs.circuit.nets}
    for ref, fp in altium.items():
        other = kicad[ref]
        assert (fp.side, fp.rotation) == (other.side, other.rotation), ref
        assert fp.lib_ref.split(":")[-1] == other.lib_ref.split(":")[-1], ref
        shifts.add((fp.position.x - other.position.x, fp.position.y - other.position.y))
        theirs_by_number = {pad.number: pad for pad in other.pads}
        assert len(fp.pads) == len(other.pads)
        for pad in fp.pads:
            want = theirs_by_number[pad.number]
            assert (pad.shape, pad.kind) == (want.shape, want.kind), (ref, pad.number)
            assert net_name.get(pad.net_id or "") == their_net.get(want.net_id or ""), (ref, pad.number)
            assert abs(pad.position.x - want.position.x) <= 2, (ref, pad.number)
            assert abs(pad.position.y - want.position.y) <= 2, (ref, pad.number)
    xs, ys = [s[0] for s in shifts], [s[1] for s in shifts]
    assert max(xs) - min(xs) <= 2 and max(ys) - min(ys) <= 2


def test_footprints_on_the_bottom_keep_mirrored_pads() -> None:
    data = (DATA / "blink" / "blink.PcbDoc").read_bytes()
    document = read_pcbdoc(data)
    design = read(DATA / "blink" / "blink.PcbDoc")
    assert design.board is not None
    (d1,) = [fp for fp in design.board.footprints if design.by_id[fp.component_id].ref == "D1"]  # type: ignore[attr-defined]
    assert d1.side == "bottom" and len(d1.pads) == 2
    records = {p.name: p for p in document.primitives_of(0) if hasattr(p, "name")}
    index = next(i for i, c in enumerate(document.components) if c.source_designator == "D1")
    records = {p.name: p for p in document.pads if p.prefix.component == index}  # type: ignore[union-attr]
    for pad in d1.pads:
        got = Transform.placement(d1.position, d1.rotation).apply(pad.position)
        record = records[pad.number]
        want = Point(round(record.x * 127 / 50), -round(record.y * 127 / 50))  # type: ignore[union-attr]
        assert abs(got.x - want.x) <= 1 and abs(got.y - want.y) <= 1


def test_footprints_rotation_side_lock_and_library_reference() -> None:
    parts = [
        rec.component("R1", rotation=90.0, layer="BOTTOM", extra={"LOCKED": "TRUE"}),
        rec.component("R2", rotation=33.3, extra={"SOURCEFOOTPRINTLIBRARY": ""}),
    ]
    pads = [
        rec.pad("1", (2000 * MIL, 1600 * MIL), component=0),
        rec.pad("1", (2100 * MIL, 1500 * MIL), component=1),
    ]
    design = import_board(rec.document(components=parts, pads=pads), file="a.PcbDoc", sha256=rec.SHA)
    assert design.board is not None
    first, second = design.board.footprints
    assert (first.rotation, first.side, first.locked, first.lib_ref) == (
        90_000_000,
        "bottom",
        True,
        "Parts:R_0603",
    )
    assert (second.rotation, second.side, second.locked, second.lib_ref) == (
        33_300_000,
        "top",
        False,
        "R_0603",
    )
    assert first.position == Point(50_800_000, -38_100_000)
    # 100 mil above the origin in Altium's frame, on a footprint turned by 90 degrees.
    assert first.pads[0].position == Point(2_540_000, 0) and first.pads[0].rotation == 270_000_000
    back = Transform.placement(first.position, first.rotation).apply(first.pads[0].position)
    assert back == Point(50_800_000, -40_640_000)
    assert first.attributes == ("smd",) and first.native_ids == {"altium": "fp:UIDR1"}


def test_footprints_attributes_follow_the_pads() -> None:
    parts = [rec.component("J1"), rec.component("R1"), rec.component("H1")]
    pads = [
        rec.pad("1", hole=30 * MIL, layer=74, component=0),
        rec.pad("2", component=0),
        rec.pad("1", component=1),
    ]
    design = import_board(rec.document(components=parts, pads=pads), file="a.PcbDoc", sha256=rec.SHA)
    assert design.board is not None
    assert [fp.attributes for fp in design.board.footprints] == [("through_hole",), ("smd",), ()]


def test_footprints_free_pad_is_a_footprint_of_its_own() -> None:
    pads = [rec.pad("", (500 * MIL, 400 * MIL), hole=120 * MIL, layer=74, plated=False)]
    design = import_board(rec.document(pads=pads), file="a.PcbDoc", sha256=rec.SHA)
    assert design.board is not None
    (footprint,) = design.board.footprints
    assert footprint.attributes == ("board_only",) and footprint.lib_ref == ""
    assert footprint.position == Point(12_700_000, -10_160_000)
    assert [pad.position for pad in footprint.pads] == [Point(0, 0)]
    assert footprint.pads[0].kind == "np_thru_hole"
    assert design.by_id[footprint.component_id].ref == ""  # type: ignore[attr-defined]
    assert [i for i in design.validate() if i.severity == "error"] == []


def test_footprints_component_index_that_names_no_record_is_free() -> None:
    document = rec.document(pads=[rec.pad("1", component=7)], tracks=[rec.track((0, 0), (9, 0), component=7)])
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA)
    assert design.board is not None
    assert design.board.footprints[0].attributes == ("board_only",) and len(design.board.tracks) == 1


def test_footprints_graphics_are_counted_not_modelled() -> None:
    issues: list[Issue] = []
    document = rec.document(
        components=[rec.component("R1")],
        tracks=[rec.track((0, 0), (9, 0), layer=33, component=0)],
        arcs=[rec.arc((0, 0), 100, 0.0, 90.0, layer=33, component=0)],
        texts=[rec.text("R1", designator=True, component=0), rec.text("10k", comment=True, component=0)],
        fills=[rec.fill((0, 0), (9, 9), component=0)],
        regions=[rec.region([(0, 0), (9, 0), (9, 9)], layer=33, component=0)],
    )
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    board = design.board
    assert board is not None
    assert (board.tracks, board.arcs, board.texts) == ((), (), ())
    assert [g for g in board.graphics if g.layer != "Edge.Cuts"] == []
    (unmapped,) = [i for i in issues if i.code == "altium.import.unmapped"]
    assert "footprint-graphics 6" in unmapped.message


# --- the synthesised circuit ----------------------------------------------------------------------------


def test_circuit_board_only_import_of_the_blink_sample() -> None:
    design = read(DATA / "blink" / "blink.PcbDoc")
    assert design.board is not None and design.header.name == "blink"
    assert sorted(design.by_ref) == ["D1", "R1", "U1"]
    for footprint in design.board.footprints:
        component = design.by_id[footprint.component_id]
        numbers = [pin.number for pin in component.pins]  # type: ignore[attr-defined]
        assert numbers == list(dict.fromkeys(pad.number for pad in footprint.pads if pad.number))
        assert {pin.etype for pin in component.pins} == {"unspecified"}  # type: ignore[attr-defined]
        assert {pin.name for pin in component.pins} == {""}  # type: ignore[attr-defined]
        assert component.path == component.ref and component.lib_footprint_ref == footprint.lib_ref  # type: ignore[attr-defined]
    model = to_model(blink())
    assert nets_of(design) == nets_of(model)
    assert [i for i in design.validate() if i.severity == "error"] == []


def test_circuit_nets_of_the_routed_sample_equal_the_model() -> None:
    assert nets_of(read(DATA / "routed" / "routed.PcbDoc")) == nets_of(routed_model())


def test_circuit_reference_value_and_symbol_reference() -> None:
    extra = {"SOURCECOMPONENTLIBRARY": "Lib\\Parts.SchLib", "SOURCELIBREFERENCE": "RES"}
    parts = [rec.component("R1", extra=extra), rec.component("", unique_id="AAAA")]
    document = rec.document(
        components=parts,
        nets=["A"],
        pads=[rec.pad("1", component=0, net=0), rec.pad("1", component=0, net=0), rec.pad("2", component=1)],
        texts=[
            rec.text("10k", comment=True, component=0),
            rec.text("X9", designator=True, component=1),
        ],
    )
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA)
    first, second = design.circuit.components
    assert (first.ref, first.value, first.lib_symbol_ref) == ("R1", "10k", "Parts:RES")
    assert first.lib_footprint_ref == "Parts:R_0603" and [p.number for p in first.pins] == ["1"]
    assert (second.ref, second.value, second.lib_symbol_ref) == ("X9", "", "")
    assert first.native_ids == {"altium": "cmp:fp:UIDR1"} and second.native_ids == {"altium": "cmp:fp:AAAA"}
    assert len(design.nets_by_name["A"].members) == 1
    linked = dataclasses.replace(parts[0], source_unique_id="\\SHEETUID\\PARTUID")
    design = import_board(rec.document(components=[linked]), file="a.PcbDoc", sha256=rec.SHA)
    assert design.circuit.components[0].native_ids == {"altium": "cmp:\\SHEETUID\\PARTUID"}
