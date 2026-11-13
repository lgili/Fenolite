# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Parts, annotation, wires, net labels and power ports added to a binary Altium sheet (change c0499, design
D1 to D3), on the Part J kit project, authored for Fenolite."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from fenolite.backends.altium import edit
from fenolite.backends.altium.adapter.connectivity import local_nets
from fenolite.backends.altium.adapter.parts import part_groups
from fenolite.backends.altium.edit.records import keys_of
from fenolite.backends.altium.edit.schematic import UNIT_NM, load
from fenolite.backends.altium.read.sch import read_schematic

OPEN = dict.fromkeys(("add_part", "annotate", "create"), True)
MIL = UNIT_NM // 10


@pytest.fixture
def sheet(board: Path) -> Path:
    return board.with_suffix(".SchDoc")


def _session(
    path: Path, *, gates: dict[str, bool] | None = None, project: Path | None = None
) -> edit.SchematicSession:
    session = edit.open(path, gates=OPEN if gates is None else gates, project=project)
    assert isinstance(session, edit.SchematicSession)
    return session


def _records(path: Path) -> list[dict[str, str]]:
    return [keys_of(p.rstrip(b"\0")) if k == 0 else {} for k, p in load(path.read_bytes()).frames]


def _part_records(records: list[dict[str, str]], ref: str) -> tuple[int, list[int]]:
    [root] = [int(r["OWNERINDEX"]) for r in records if r.get("RECORD") == "34" and r.get("TEXT") == ref]
    owned = {root}
    for n, r in enumerate(records):
        if r.get("OWNERINDEX", "").isdigit() and int(r["OWNERINDEX"]) in owned:
            owned.add(n)
    return root, sorted(owned)


def test_add_part_copies_a_part_and_places_it(sheet: Path, tmp_path: Path) -> None:
    """Scenario "A part copied and placed"."""
    out = tmp_path / "add.SchDoc"
    session = _session(sheet).add_part(sheet, "R1", new_designator="R9", at=(500 * MIL, 0))
    receipt = session.declare_connectivity().commit(out, backup=False)
    assert receipt.written, receipt.issues
    document = read_schematic(out.read_bytes())
    groups = {g.ref: g for g in part_groups(document)}
    assert "R9" in groups and "R1" in groups
    r1 = sorted(
        (p.designator, p.location[0].value + 50 * 100_000, p.location[1].value) for p in groups["R1"].pins
    )
    r9 = sorted((p.designator, p.location[0].value, p.location[1].value) for p in groups["R9"].pins)
    assert r1 == r9
    records = _records(out)
    root, owned = _part_records(records, "R9")
    assert records[root]["RECORD"] == "1" and len(owned) == len(_part_records(records, "R1")[1])
    assert all(records[n]["OWNERINDEX"] in {str(i) for i in owned} for n in owned if n != root)
    ids = [r["UNIQUEID"] for r in records if "UNIQUEID" in r]
    assert len(ids) == len(set(ids))
    assert load(out.read_bytes()).header.rstrip(b"\0").endswith(f"WEIGHT={len(records)}".encode())


def test_add_part_of_a_designator_held_twice_refuses(sheet: Path, tmp_path: Path) -> None:
    """Scenario "A designator held twice"."""
    out = tmp_path / "never.SchDoc"
    receipt = _session(sheet).add_part(sheet, "R1", new_designator="R2").declare_connectivity().commit(out)
    assert [i.code for i in receipt.issues] == ["altium.edit.assertion"] and "R2" in receipt.issues[0].message
    assert not out.exists()


def test_annotate_a_copied_part(sheet: Path, tmp_path: Path) -> None:
    """Scenario "A copied part annotated"."""
    out = tmp_path / "annotated.SchDoc"
    session = (
        _session(sheet).add_part(sheet, "R1", at=(500 * MIL, 0)).annotate(edit.Part("R?"), "R9", old="R?")
    )
    assert session.declare_connectivity().commit(out, backup=False).written
    refs = {g.ref for g in part_groups(read_schematic(out.read_bytes()))}
    assert "R9" in refs and "R?" not in refs


def test_annotate_alone_keeps_the_net_signature_without_a_declaration(sheet: Path, tmp_path: Path) -> None:
    out = tmp_path / "renamed.SchDoc"
    receipt = _session(sheet).annotate(edit.Part("R2"), "R7", old="R2").commit(out, backup=False)
    assert receipt.written, receipt.issues
    refs = {g.ref for g in part_groups(read_schematic(out.read_bytes()))}
    assert "R7" in refs and "R2" not in refs
    taken = _session(sheet).annotate(edit.Part("R2"), "R1", old="R2").commit(tmp_path / "never.SchDoc")
    assert [i.code for i in taken.issues] == ["altium.edit.assertion"]
    wrong = _session(sheet).annotate(edit.Part("R2"), "R7", old="R3").commit(tmp_path / "never.SchDoc")
    assert [i.code for i in wrong.issues] == ["altium.edit.assertion"]


def test_annotate_a_designator_of_another_sheet_of_the_project(sheet: Path, tmp_path: Path) -> None:
    """Scenario "A designator held on another sheet of the project": an authored two-sheet project."""
    second = sheet.with_name("second.SchDoc")
    shutil.copy(sheet, second)
    renamed = _session(second).annotate(edit.Part("R1"), "R5", old="R1").commit(second, backup=False)
    assert renamed.written, renamed.issues
    project = sheet.with_suffix(".PrjPcb")
    text = project.read_text(encoding="utf-8")
    project.write_text(
        text.rstrip("\r\n") + "\r\n\r\n[Document9]\r\nDocumentPath=second.SchDoc\r\n", encoding="utf-8"
    )
    out = tmp_path / "never.SchDoc"
    receipt = _session(sheet, project=project).annotate(edit.Part("R2"), "R5", old="R2").commit(out)
    assert [i.code for i in receipt.issues] == ["altium.edit.assertion"]
    assert "second.SchDoc" in receipt.issues[0].message and not out.exists()
    free = _session(sheet, project=project).annotate(edit.Part("R2"), "R8", old="R2")
    assert free.commit(tmp_path / "free.SchDoc", backup=False).written


def test_annotate_on_a_repeated_sheet_refuses(tmp_path: Path) -> None:
    """Requirement "Annotation": a part of a repeated sheet takes its designator from the channel, so the
    annotation refuses; the two-channel project of ``_altium_channels``, authored for Fenolite."""
    import _altium_channels as two

    for name, data in two.files().items():
        (tmp_path / name).write_bytes(data)
    child = tmp_path / two.CHILD
    out = tmp_path / "never.SchDoc"
    session = _session(child, project=tmp_path / two.PROJECT)
    receipt = session.annotate(edit.Part("R1"), "R5", old="R1").commit(out)
    assert [i.code for i in receipt.issues] == ["altium.edit.assertion"], receipt.issues
    assert "repeated sheet" in receipt.issues[0].message and not out.exists()
    top = _session(tmp_path / two.TOP, project=tmp_path / two.PROJECT)
    assert top.annotate(edit.Part("U1"), "U5", old="U1").commit(tmp_path / "top.SchDoc", backup=False).written


def _net_of(path: Path, ref: str, pin: str) -> tuple[str, ...]:
    document = read_schematic(path.read_bytes())
    groups = part_groups(document)
    for net in local_nets(document, groups):
        if (ref, pin) in {(groups[p.group].ref, p.designator) for p in net.pins}:
            return tuple(sorted(i.text for i in net.idents))
    return ()


def test_power_port_wires_a_copied_part_to_its_net(sheet: Path, tmp_path: Path) -> None:
    """Scenario "A part wired to a power net": R9's pin 1 ends 5 units above its origin, (290, 645)."""
    out = tmp_path / "wired.SchDoc"
    end, left = (2900 * MIL, 6450 * MIL), (2700 * MIL, 6450 * MIL)
    session = (
        _session(sheet)
        .add_part(sheet, "R1", new_designator="R9", at=(500 * MIL, 0))
        .add_power_port("GND", (6000 * MIL, 4000 * MIL), style="4")
        .add_wire([end, left])
        .add_power_port("GND", left)
    )
    assert session.declare_connectivity().commit(out, backup=False).written
    assert "GND" in _net_of(out, "R9", "1")
    ports = [r for r in _records(out) if r.get("RECORD") == "17"]
    assert [p["STYLE"] for p in ports] == ["4", "4"] and ports[1]["LOCATION.X"] == "270"


def test_net_label_on_a_wire_middle_gets_a_junction(sheet: Path, tmp_path: Path) -> None:
    """Scenario "A net label on a wire's middle": wire A runs up from R9's pin 1, wire B starts on A's middle
    and holds the label, so R9's pin 1 lies on ``SENSE`` only through the joint."""
    out = tmp_path / "junction.SchDoc"
    before = sum(1 for r in _records(sheet) if r.get("RECORD") == "29")
    pin, top, middle = (2900 * MIL, 6450 * MIL), (2900 * MIL, 7450 * MIL), (2900 * MIL, 7000 * MIL)
    session = (
        _session(sheet)
        .add_part(sheet, "R1", new_designator="R9", at=(500 * MIL, 0))
        .add_wire([pin, top])
        .add_wire([middle, (3500 * MIL, 7000 * MIL)])
        .add_net_label("SENSE", (3300 * MIL, 7000 * MIL))
    )
    assert session.declare_connectivity().commit(out, backup=False).written
    junctions = [r for r in _records(out) if r.get("RECORD") == "29"]
    assert len(junctions) == before + 1
    assert (junctions[-1]["LOCATION.X"], junctions[-1]["LOCATION.Y"]) == ("290", "700")
    assert _net_of(out, "R9", "1") == ("SENSE",)


def test_undeclared_wire_refuses(sheet: Path, tmp_path: Path) -> None:
    """Scenario "An undeclared wire": a wire from R1's pin 2 (``MID``) to R2's pin 1 (``VIN``)."""
    out = tmp_path / "never.SchDoc"
    points = [
        (2400 * MIL, 6150 * MIL),
        (2700 * MIL, 6150 * MIL),
        (2700 * MIL, 6450 * MIL),
        (3000 * MIL, 6450 * MIL),
    ]
    receipt = _session(sheet).add_wire(points).commit(out)
    assert [i.code for i in receipt.issues] == ["altium.edit.connectivity"] and not out.exists()


def test_gates_of_the_additions_are_off(sheet: Path, tmp_path: Path) -> None:
    """Scenario "The gates are off"."""
    assert not any(edit.SCHEMATIC_GATES.values()) and not edit.GATES["link"]
    out = tmp_path / "never.SchDoc"
    for build in (
        lambda s: s.add_part(sheet, "R1", new_designator="R9"),
        lambda s: s.annotate(edit.Part("R2"), "R7", old="R2"),
        lambda s: s.add_wire([(0, 0), (UNIT_NM, 0)]),
        lambda s: s.add_net_label("X", (0, 0)),
        lambda s: s.add_power_port("GND", (0, 0)),
    ):
        receipt = build(_session(sheet, gates={})).commit(out)
        assert [i.code for i in receipt.issues] == ["altium.edit.gate"], receipt.issues
        assert "H-A-EDIT-SCH-ADD" in receipt.issues[0].message and not out.exists()
