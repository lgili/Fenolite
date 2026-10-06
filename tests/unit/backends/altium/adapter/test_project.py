# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The sheets and the PCB document of one project as one design (capability altium-import, "Project
import"; change c0043)."""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import _altium_records as rec
import pytest

from fenolite.backends.altium.adapter import BoardInput, NetOptions, ProjectInput, SheetInput, import_project
from fenolite.backends.altium.adapter.project import RulesInput
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.sch import read_schematic
from fenolite.core.errors import FormatError, Issue
from fenolite.model.design import Design

BLINK = Path(__file__).resolve().parents[5] / "tests" / "data" / "altium" / "blink"


def blink(edit: object = None, issues: list[Issue] | None = None) -> Design:
    sheet = (BLINK / "blink.SchDoc").read_bytes()
    board = (BLINK / "blink.PcbDoc").read_bytes()
    document = read_pcbdoc(board)
    if edit is not None:
        document = edit(document)  # type: ignore[operator]
    project = ProjectInput(
        name="blink",
        sheets=(SheetInput("blink.SchDoc", hashlib.sha256(sheet).hexdigest(), read_schematic(sheet)),),
        board=BoardInput("blink.PcbDoc", hashlib.sha256(board).hexdigest(), document),
        file="blink.PrjPcb",
    )
    return import_project(project, issues=issues)


def codes(issues: list[Issue]) -> list[str]:
    return [i.code.removeprefix("altium.import.") for i in issues]


def test_blink_project_links_by_path() -> None:
    issues: list[Issue] = []
    design = blink(issues=issues)
    assert design.header.name == "blink" and design.header.native_ids == {"altium": "altium_prjpcb"}
    assert sorted(c.ref for c in design.circuit.components) == ["D1", "R1", "U1"]
    assert design.board is not None and design.rules is not None
    ids = {c.id for c in design.circuit.components}
    assert all(fp.component_id in ids for fp in design.board.footprints)
    assert "linked-by-designator" not in codes(issues) and "pcb-only-component" not in codes(issues)
    assert "pcb-only-net" not in codes(issues)
    nets = {n.id for n in design.circuit.nets}
    assert all(pad.net_id is None or pad.net_id in nets for fp in design.board.footprints for pad in fp.pads)
    assert [i for i in design.validate() if i.severity == "error"] == []
    r1 = design.by_ref["R1"]
    assert r1.provenance is not None and r1.provenance.file == "blink.SchDoc"
    assert r1.pins[0].etype != "unspecified" or r1.pins[0].name != ""
    (footprint,) = [fp for fp in design.board.footprints if fp.component_id == r1.id]
    assert footprint.provenance is not None and footprint.provenance.file == "blink.PcbDoc"
    assert len({e.provenance.file_sha256 for e in design.entities() if e.provenance}) >= 2


def without_links(document: PcbDocument) -> PcbDocument:
    parts = tuple(dataclasses.replace(c, source_unique_id="") for c in document.components)
    return dataclasses.replace(document, components=parts)


def test_link_by_designator() -> None:
    issues: list[Issue] = []
    plain, design = blink(), blink(without_links, issues)
    assert design.board is not None and plain.board is not None
    assert [fp.component_id for fp in design.board.footprints] == [
        fp.component_id for fp in plain.board.footprints
    ]
    (found,) = [i for i in issues if i.code == "altium.import.linked-by-designator"]
    assert found.message.startswith("3 component(s)") and found.severity == "info"
    assert len(design.circuit.components) == 3


def with_mounting_hole(document: PcbDocument) -> PcbDocument:
    hole = rec.component("MH1", unique_id="HOLEUID1", source_unique_id="\\NOSUCHID")
    index = len(document.components)
    pads = (rec.pad("1", (2000 * rec.MIL, 1500 * rec.MIL), hole=120 * rec.MIL, layer=74, component=index),)
    return dataclasses.replace(
        document, components=(*document.components, hole), pads=(*document.pads, *pads)
    )


def test_component_only_on_the_board() -> None:
    issues: list[Issue] = []
    design = blink(with_mounting_hole, issues)
    hole = design.by_ref["MH1"]
    assert [pin.number for pin in hole.pins] == ["1"] and len(design.circuit.components) == 4
    (found,) = [i for i in issues if i.code == "altium.import.pcb-only-component"]
    assert found.where == "MH1" and found.severity == "warning"
    assert [i for i in design.validate() if i.severity == "error"] == []


def with_other_net(document: PcbDocument) -> PcbDocument:
    nets = (*document.nets, rec.net("SHIELD"))
    first = dataclasses.replace(
        document.pads[0], prefix=dataclasses.replace(document.pads[0].prefix, net=len(nets) - 1)
    )  # type: ignore[union-attr]
    return dataclasses.replace(document, nets=nets, pads=(first, *document.pads[1:]))


def test_net_only_on_the_board_keeps_the_pad_net() -> None:
    issues: list[Issue] = []
    design = blink(with_other_net, issues)
    shield = design.nets_by_name["SHIELD"]
    assert design.board is not None
    assert any(pad.net_id == shield.id for fp in design.board.footprints for pad in fp.pads)
    (found,) = [i for i in issues if i.code == "altium.import.pcb-only-net"]
    assert found.message.startswith("1 net(s)") and len(shield.members) == 1
    assert [i for i in design.validate() if i.severity == "error"] == []


def test_nets_link_by_name_without_letter_case_and_classes_attach() -> None:
    sheet = rec.Sheet("s.SchDoc")
    sheet.component("R1", [("1", 10, 10), ("2", 30, 10)], uid="RUID0001")
    sheet.label("Vin", 10, 10)
    sheet.label("GND", 30, 10)
    part = rec.component("R1", source_unique_id="\\RUID0001")
    document = rec.document(
        nets=["VIN", "GND"],
        components=[part],
        classes=[rec.net_class("PWR", ["VIN"])],
        pads=[rec.pad("1", component=0, net=0), rec.pad("2", component=0, net=1)],
        tracks=[rec.track((0, 0), (9, 0), net=0)],
    )
    issues: list[Issue] = []
    project = ProjectInput("p", NetOptions(), (sheet.input(),), BoardInput("b.PcbDoc", rec.SHA, document))
    design = import_project(project, issues=issues)
    assert sorted(design.nets_by_name) == ["GND", "Vin"] and "pcb-only-net" not in codes(issues)
    assert design.board is not None
    vin = design.nets_by_name["Vin"]
    assert design.board.tracks[0].net_id == vin.id and design.board.footprints[0].pads[0].net_id == vin.id
    (power,) = design.circuit.netclasses
    assert vin.netclass_id == power.id and design.nets_by_name["GND"].netclass_id is None
    assert [i for i in design.validate() if i.severity == "error"] == []


def test_repeated_sheet_takes_its_references_from_the_board() -> None:
    top = rec.Sheet("top.SchDoc")
    top.symbol("CH1", "ch.SchDoc", (100, 200), uid="SYMBOL01")
    top.symbol("CH2", "ch.SchDoc", (300, 200), uid="SYMBOL02")
    channel = rec.Sheet("ch.SchDoc")
    channel.component("R1", [("1", 10, 10)], uid="RUID0001")
    parts = [
        rec.component("R1_CH1", unique_id="A", source_unique_id="\\SYMBOL01\\RUID0001"),
        rec.component("R1_CH2", unique_id="B", source_unique_id="\\SYMBOL02\\RUID0001"),
    ]
    issues: list[Issue] = []
    project = ProjectInput(
        "p",
        sheets=(top.input(), channel.input()),
        board=BoardInput("b.PcbDoc", rec.SHA, rec.document(components=parts)),
    )
    design = import_project(project, issues=issues)
    assert sorted((c.ref, c.path) for c in design.circuit.components) == [
        ("R1_CH1", "CH1/R1_CH1"),
        ("R1_CH2", "CH2/R1_CH2"),
    ]
    assert "channels" in codes(issues) and "linked-by-designator" not in codes(issues)
    assert "repeated-sheet" not in codes(issues)
    assert [i for i in design.validate() if i.code == "model.duplicate-ref"] == []


def test_project_without_a_board_and_without_sheets() -> None:
    sheet = rec.Sheet("s.SchDoc")
    sheet.component("R1", [("1", 10, 10)])
    only_sheets = import_project(ProjectInput("p", sheets=(sheet.input(),)))
    assert only_sheets.board is None and only_sheets.rules is None and only_sheets.header.name == "p"
    board = BoardInput("b.PcbDoc", rec.SHA, rec.document(components=[rec.component("R1")]))
    only_board = import_project(ProjectInput("p", board=board))
    assert only_board.board is not None and only_board.header.name == "p"
    assert only_board.header.native_ids == {"altium": "altium_pcbdoc"}
    with pytest.raises(FormatError, match="no readable sheet"):
        import_project(ProjectInput("p"))


def test_extra_board_and_rule_files_of_the_caller() -> None:
    issues: list[Issue] = []
    sheet = rec.Sheet("s.SchDoc")
    sheet.component("R1", [("1", 10, 10)])
    record = rec.rule("Width", "W", MINLIMIT="6mil", PREFEREDWIDTH="10mil", MAXLIMIT="20mil")
    board = BoardInput("b.PcbDoc", rec.SHA, rec.document(rules=[record]))
    extra = RulesInput("x.RUL", rec.SHA, (record.fields,))
    project = ProjectInput("p", sheets=(sheet.input(),), board=board, rules=(extra,), extra_boards=1)
    design = import_project(project, issues=issues)
    assert design.rules is not None and [r.name for r in design.rules.rules] == ["W", "W"]
    assert len({r.id for r in design.rules.rules}) == 2
    assert design.rules.rules[1].provenance is not None and design.rules.rules[1].provenance.file == "x.RUL"
    (found,) = [i for i in issues if i.code == "altium.import.extra-board"]
    assert found.severity == "info" and "1 further" in found.message
    assert import_project(ProjectInput("p", sheets=(sheet.input(),), board=board)).rules is not None
