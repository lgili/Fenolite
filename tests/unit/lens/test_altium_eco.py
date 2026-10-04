# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Classes of the change order in an Altium build (capability altium-build, "Classes in an Altium build";
change c0048).

The board example with module sheets and the flat routed sample are built and read back with the test
readers: the schematic declares the net classes of the PCB document, the project file holds the class
generation keys, and the PCB document holds the component classes of the module sheets. What Altium
Designer then proposes in "Design » Update PCB Document" is settled only by the maintainer's report of
Part E of ``docs/evidence/altium-pcb.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _altium import HIER_BOARD_DIR, blink, blink_resolver, hier_board
from _altium_copper import routed_build
from _altium_pcb_read import read_pcbdoc
from _altium_read import net_classes_from_sheet, nets_from_sheet, read_sheet

from fenolite.dsl import placements, to_model
from fenolite.lens.altium import build_altium
from fenolite.lens.build import BuildOutput

SHEET_KEYS = b"ClassGenCCAutoEnabled=1\r\nClassGenCCAutoRoomEnabled=0\r\nClassGenNCAutoScope=None\r\n"
CLASS_SECTION = (
    b"\r\n[PrjClassGen]\r\nCompClassManualEnabled=0\r\nCompClassManualRoomEnabled=0\r\n"
    b"NetClassAutoBusEnabled=1\r\nNetClassAutoCompEnabled=0\r\nNetClassAutoNamedHarnessEnabled=0\r\n"
    b"NetClassManualEnabled=1\r\nNetClassSeparateForBusSections=0\r\n"
)


def build_board(folder: Path, **kwargs: object) -> BuildOutput:
    design = hier_board()
    return build_altium(
        to_model(design),
        name=design.name,
        placed=tuple(placements(design)),
        placements=placements(design),
        resolver=blink_resolver(folder, HIER_BOARD_DIR),
        **kwargs,  # type: ignore[arg-type]
    )


def schematic_classes(files: dict[str, bytes]) -> dict[str, set[str]]:
    """Class name → its nets, from the directives of every sheet of a build."""
    found: dict[str, set[str]] = {}
    for name, data in files.items():
        if name.endswith(".SchDoc"):
            for net, group in net_classes_from_sheet(read_sheet(data)[0]).items():
                found.setdefault(group, set()).add(net)
    return found


def board_classes(document: bytes, kind: str) -> dict[str, set[str]]:
    return {c.name: set(c.members) for c in read_pcbdoc(document).classes if c.kind == kind}


@pytest.mark.parametrize("form", ["binary", "ascii"])
def test_board_example_with_module_sheets(tmp_path: Path, form: str) -> None:
    """Scenario "Board example"."""
    output = build_board(tmp_path, sheets="modules", form=form)
    assert not [i for i in output.issues if i.severity == "error"]
    files = output.files
    assert schematic_classes(files) == {"PWR": {"GND", "VIN"}}
    project = files["altium_hier_board.PrjPcb"]
    assert project.endswith(CLASS_SECTION) and project.count(SHEET_KEYS) == 3
    assert project.count(b"ClassGenCCAutoRoomEnabled=0") == 3 and b"RoomEnabled=1" not in project
    document = files["altium_hier_board.PcbDoc"]
    assert [c.name for c in read_pcbdoc(document).classes] == ["PWR", "driver", "led"]
    assert board_classes(document, "0") == schematic_classes(files)
    assert board_classes(document, "1") == {"driver": {"R1", "U1"}, "led": {"D1"}}


def test_component_classes_hold_the_parts_of_their_sheets(tmp_path: Path) -> None:
    """Each component class of the board holds exactly the parts that its module's sheet draws."""
    files = build_board(tmp_path, sheets="modules").files
    on_sheet: dict[str, set[str]] = {}
    for name, data in files.items():
        if name.startswith("altium_hier_board_") and name.endswith(".SchDoc"):
            module = name.removeprefix("altium_hier_board_").removesuffix(".SchDoc")
            records = read_sheet(data)[0]
            on_sheet[module] = {r["TEXT"] for r in records if r["RECORD"] == "34"}
    assert board_classes(files["altium_hier_board.PcbDoc"], "1") == on_sheet


def test_directives_do_not_change_the_nets(tmp_path: Path) -> None:
    """A directive names no net and joins none: each sheet gives the same nets with and without them."""
    files = build_board(tmp_path, sheets="modules").files
    for name, data in files.items():
        if not name.endswith(".SchDoc"):
            continue
        records = read_sheet(data)[0]
        directives = {i for i, r in enumerate(records) if r["RECORD"] == "43"}
        plain = [
            r
            for i, r in enumerate(records)
            if i not in directives and not (r["RECORD"] == "41" and r.get("NAME") == "ClassName")
        ]
        assert len(plain) == len(records) - 2 * len(directives)
        if any(r["RECORD"] == "2" for r in records):
            assert nets_from_sheet(records) == nets_from_sheet(plain)


def test_flat_board_example_has_the_class_of_its_sheet(tmp_path: Path) -> None:
    """A flat build: one component class, named after the single sheet, with every component."""
    output = build_board(tmp_path)
    project = output.files["altium_hier_board.PrjPcb"]
    assert project.count(SHEET_KEYS) == 1 and project.endswith(CLASS_SECTION)
    document = output.files["altium_hier_board.PcbDoc"]
    assert [c.name for c in read_pcbdoc(document).classes] == ["PWR", "altium_hier_board"]
    assert board_classes(document, "1") == {"altium_hier_board": {"D1", "R1", "U1"}}
    assert schematic_classes(output.files) == {"PWR": {"GND", "VIN"}}


def test_flat_routed_sample(tmp_path: Path) -> None:
    """Scenario "Flat routed sample": what the report of Part E asked for (a class named ``routed``)."""
    files = routed_build(tmp_path).files
    main = read_sheet(files["routed.SchDoc"])[0]
    assert sum(1 for r in main if r["RECORD"] == "43") == 2
    assert net_classes_from_sheet(main) == {"GND": "PWR", "VIN": "PWR"}
    project = files["routed.PrjPcb"]
    assert project.count(SHEET_KEYS) == 1 and project.endswith(CLASS_SECTION)
    assert b"DocumentPath=routed.SchDoc\r\n" + SHEET_KEYS in project
    classes = read_pcbdoc(files["routed.PcbDoc"]).classes
    assert [(c.name, c.kind, c.members) for c in classes] == [
        ("PWR", "0", ["GND", "VIN"]),
        ("routed", "1", ["D1", "R1", "U1"]),
    ]
    refs = {r["TEXT"] for r in main if r["RECORD"] == "34"}
    assert set(classes[1].members) == refs


def test_class_of_the_top_sheet_names_its_parts(tmp_path: Path) -> None:
    """A part outside every module is in the class named after the top sheet, beside the module classes."""
    from _altium import blink

    design = blink(
        "design.add(u1, r1, d1)",
        'from fenolite.dsl import Module\n\nm = Module("stage")\nm.add(r1, d1)\ndesign.add(u1, m)',
    )
    output = build_altium(
        to_model(design),
        name=design.name,
        placed=tuple(placements(design)),
        placements=placements(design),
        resolver=blink_resolver(tmp_path),
        sheets="modules",
    )
    assert not [i for i in output.issues if i.severity == "error"]
    assert board_classes(output.files["blink.PcbDoc"], "1") == {"blink": {"U1"}, "stage": {"D1", "R1"}}
    assert output.files["blink.PrjPcb"].count(SHEET_KEYS) == 2


def test_net_class_name_the_schematic_cannot_hold() -> None:
    """Scenario "Net class name the schematic cannot hold": no board, so no PCB document is planned."""
    from fenolite.dsl import Design, Net, Part, connect

    design = Design("classy")
    r1 = Part("R1", "Parts.SchLib:RES", footprint="Parts.PcbLib:R0603")
    first, second = Net("A"), Net("B")
    connect(first, r1[1])
    connect(second, r1[2])
    design.add(r1)
    design.rules.netclass("=PWR", nets=(first,))
    output = build_altium(to_model(design), name=design.name)
    errors = [i for i in output.issues if i.severity == "error"]
    assert output.files == {}
    assert [i.code for i in errors] == ["altium.text-unwritable"]
    assert "net class name '=PWR'" in errors[0].message and errors[0].where == "=PWR"


def test_design_without_a_class_holds_no_class_record(tmp_path: Path) -> None:
    """Scenario "Design without a class keeps its bytes", on the built files."""
    from _altium import sample

    design = sample()
    files = build_altium(to_model(design), name=design.name).files
    assert (
        b"PrjClassGen" not in files["altium_sample.PrjPcb"]
        and b"ClassGen" not in files["altium_sample.PrjPcb"]
    )
    main = read_sheet(files["altium_sample.SchDoc"])[0]
    assert not [r for r in main if r["RECORD"] == "43"]


def test_rule_values_are_reported_without_the_document(tmp_path: Path) -> None:
    """Without a PCB document the schematic still declares the class; only its rule values stay behind."""
    design = blink("design.board(mm(50), mm(30))\n", "")
    output = build_altium(
        to_model(design), name=design.name, resolver=blink_resolver(tmp_path), placed=(), placements={}
    )
    rules = [i for i in output.issues if i.code == "altium.not-lowered" and i.where == "rules"]
    assert len(rules) == 1 and "rule values of the net classes PWR" in rules[0].message
    assert "the schematic declares their nets" in rules[0].message
    assert schematic_classes(output.files) == {"PWR": {"GND", "VIN"}}
    assert output.files["blink.PrjPcb"].endswith(CLASS_SECTION)
