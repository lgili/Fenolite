# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The records of the sample's schematic (capability altium-schematic-writer: "ASCII schematic form",
"Sheet record", "Generic component bodies", "Designator, comment and links", "Connectivity on the sheet"
and "Deterministic sheet layout"; change c0032)."""

from __future__ import annotations

from collections import Counter
from functools import cache

from _altium import (
    SAMPLE_PATHS,
    check_plan,
    component_index,
    example_files,
    example_plan,
    model_of,
    owned_by,
    records,
    sample_model,
    upright_symbol,
)

from fenolite.backends.altium.layout import PartSpec, PinNet, layout_sheet
from fenolite.backends.altium.project import plan_sheet, write_project
from fenolite.backends.altium.schdoc import schdoc_records
from fenolite.dsl import Design, Net, Part, connect

SHEET_LINE = (
    "|RECORD=31|FONTIDCOUNT=1|SIZE1=10|FONTNAME1=Times New Roman|SYSTEMFONT=1|BORDERON=T|SNAPGRIDON=T"
    "|SNAPGRIDSIZE=10|VISIBLEGRIDON=T|VISIBLEGRIDSIZE=10|HOTSPOTGRIDON=T|HOTSPOTGRIDSIZE=4|DISPLAY_UNIT=4"
    "|AREACOLOR=16317695|SHEETSTYLE=0"
)
COORDINATES = ("LOCATION.X", "LOCATION.Y", "CORNER.X", "CORNER.Y", "X1", "Y1", "X2", "Y2")


@cache
def sample_bytes() -> bytes:
    return write_project(sample_model(), name="altium_sample", form="ascii")["altium_sample.SchDoc"]


def sample_records() -> list[dict[str, str]]:
    return records(sample_bytes())


# --- requirement "ASCII schematic form" --------------------------------------------------------------


def test_header_and_first_record_of_the_sample() -> None:
    lines = sample_bytes().split(b"\r\n")
    assert lines[-1] == b"" and len(lines) - 1 == 123
    assert lines[0] == b"|HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0|WEIGHT=122"
    assert lines[1].startswith(b"|RECORD=31|")


def test_line_ends_and_bytes() -> None:
    data = sample_bytes()
    assert data.endswith(b"\r\n") and data.count(b"\r\n") == 123
    body = data.replace(b"\r\n", b"")
    assert all(0x20 <= b <= 0x7E for b in body)
    assert not any(line.endswith(b"|>") for line in data.split(b"\r\n"))


def test_owners_precede_children_and_no_frac() -> None:
    found = sample_records()
    for index, record in enumerate(found):
        if "OWNERINDEX" in record:
            assert 0 <= int(record["OWNERINDEX"]) < index
        assert not any(key.endswith("_FRAC") for key in record)
    assert found[0]["RECORD"] == "31" and "OWNERINDEX" not in found[0]


# --- requirement "Sheet record" -------------------------------------------------------------------------


def test_sheet_record_of_the_sample() -> None:
    assert sample_bytes().split(b"\r\n")[1].decode("ascii") == SHEET_LINE


# --- requirement "Generic component bodies" -----------------------------------------------------------


def test_four_pin_part_of_the_sample() -> None:
    found = sample_records()
    u2 = component_index(found, "U2")
    children = owned_by(found, u2)
    (rect,) = [r for _, r in children if r["RECORD"] == "14"]
    left, right = int(rect["LOCATION.X"]), int(rect["CORNER.X"])
    assert (right - left, int(rect["CORNER.Y"]) - int(rect["LOCATION.Y"])) == (60, 30)
    pins = {r["DESIGNATOR"]: r for _, r in children if r["RECORD"] == "2"}
    assert sorted(pins) == ["1", "2", "3", "4"]
    for designator, edge, conglomerate in (
        ("1", left, "18"),
        ("2", left, "18"),
        ("3", right, "16"),
        ("4", right, "16"),
    ):
        pin = pins[designator]
        assert int(pin["LOCATION.X"]) == edge and pin["PINCONGLOMERATE"] == conglomerate
        assert pin["PINLENGTH"] == "20" and pin["ELECTRICAL"] == "4" and pin["OWNERINDEX"] == str(u2)
        assert pin["NAME"] == designator and pin["OWNERPARTID"] == "1"
    assert int(pins["1"]["LOCATION.Y"]) > int(pins["2"]["LOCATION.Y"]), "pin 1 above pin 2"


def test_a_part_without_connected_pins() -> None:
    design = Design("lone")
    x1 = Part("X1", "L.SchLib:SYM", "L.PcbLib:FP", "1k")
    r1 = Part("R1", "L.SchLib:RES", "L.PcbLib:R0603", "1k")
    design.add(x1, r1)
    connect(Net("A"), r1[1])
    connect(Net("B"), r1[2])
    found = records(write_project(model_of(design), name="lone", form="ascii")["lone.SchDoc"])
    x1_index = component_index(found, "X1")
    assert found[x1_index]["RECORD"] == "1"
    kinds = [r["RECORD"] for _, r in owned_by(found, x1_index)]
    assert kinds == ["14", "34", "41", "44"]
    (rect,) = [r for _, r in owned_by(found, x1_index) if r["RECORD"] == "14"]
    assert int(rect["CORNER.X"]) - int(rect["LOCATION.X"]) == 60
    assert int(rect["CORNER.Y"]) - int(rect["LOCATION.Y"]) == 20


# --- requirement "Designator, comment and links" -------------------------------------------------------


def test_links_of_the_sample_j1() -> None:
    found = sample_records()
    j1 = component_index(found, "J1")
    component = found[j1]
    assert component["LIBREFERENCE"] == "HDR2" and component["DESIGNITEMID"] == "HDR2"
    assert component["SOURCELIBRARYNAME"] == "FenoliteSample.SchLib"
    (listing,) = [i for i, r in owned_by(found, j1) if r["RECORD"] == "44"]
    (model,) = [r for _, r in owned_by(found, listing) if r["RECORD"] == "45"]
    assert model == {
        "RECORD": "45",
        "OWNERINDEX": str(listing),
        "MODELNAME": "HDR1X2",
        "MODELTYPE": "PCBLIB",
        "DATAFILECOUNT": "1",
        "MODELDATAFILEENTITY0": "HDR1X2",
        "MODELDATAFILEKIND0": "PCBLIB",
        "MODELDATAFILE0": "FenoliteSample.PcbLib",
        "ISCURRENT": "T",
    }
    comment = next(r for _, r in owned_by(found, j1) if r["RECORD"] == "41")
    assert comment["NAME"] == "Comment" and comment["TEXT"] == "HDR2", "J1 has no value"


def test_designators_and_comments_of_the_sample() -> None:
    found = sample_records()
    texts = {(r["RECORD"], r["TEXT"]) for r in found if r["RECORD"] in ("34", "41")}
    refs = {"J1", "R2", "U2", "R1", "D1", "U1", "C1", "C2"}
    assert {t for k, t in texts if k == "34"} == refs
    assert {t for k, t in texts if k == "41"} == {"HDR2", "10k", "DRV4", "330", "red", "5V", "10uF"}


def test_ownership_chain() -> None:
    found = sample_records()
    kinds = Counter(r["RECORD"] for r in found)
    assert kinds["44"] == kinds["45"] == kinds["46"] == kinds["48"] == 8 and kinds["47"] == 0
    for index, record in enumerate(found):
        owner = int(record.get("OWNERINDEX", "-1"))
        if record["RECORD"] == "44":
            assert found[owner]["RECORD"] == "1"
        elif record["RECORD"] == "45":
            assert owner == index - 1 and found[owner]["RECORD"] == "44"
        elif record["RECORD"] in ("46", "48"):
            assert found[owner]["RECORD"] == "45" and owner in (index - 1, index - 2)


def test_empty_value_and_no_footprint() -> None:
    design = Design("bare")
    x1, r1 = Part("X1", "L.SchLib:SYM"), Part("R1", "L.SchLib:RES", "L.PcbLib:R0603", "1k")
    design.add(x1, r1)
    connect(Net("A"), x1[1], r1[1])
    connect(Net("B"), x1[2], r1[2])
    found = records(write_project(model_of(design), name="bare", form="ascii")["bare.SchDoc"])
    x1_index = component_index(found, "X1")
    children = owned_by(found, x1_index)
    assert [r["TEXT"] for _, r in children if r["RECORD"] == "41"] == ["SYM"]
    assert not [r for _, r in children if r["RECORD"] == "44"]


# --- requirement "Connectivity on the sheet" -------------------------------------------------------------


def test_ports_and_labels_of_the_sample() -> None:
    found = sample_records()
    kinds = Counter(r["RECORD"] for r in found)
    assert kinds["27"] == 19 and kinds["17"] == 13 and kinds["25"] == 6 and kinds["29"] == 0
    ports = Counter((r["TEXT"], r["STYLE"]) for r in found if r["RECORD"] == "17")
    assert ports == {("GND", "4"): 6, ("VIN", "2"): 3, ("+5V", "2"): 4}
    labels = Counter(r["TEXT"] for r in found if r["RECORD"] == "25")
    assert labels == {"EN": 2, "LED_DRV": 2, "LED_A": 2}
    for record in found:
        if record["RECORD"] == "17":
            assert record["SHOWNETNAME"] == "T" and record["ORIENTATION"] in ("0", "2")
        if record["RECORD"] == "27":
            assert record["LOCATIONCOUNT"] == "2" and record["Y1"] == record["Y2"]


def _hot_end(pin: dict[str, str]) -> tuple[int, int]:
    x, y, length = int(pin["LOCATION.X"]), int(pin["LOCATION.Y"]), int(pin["PINLENGTH"])
    direction = int(pin["PINCONGLOMERATE"]) & 3
    return {0: (x + length, y), 1: (x, y + length), 2: (x - length, y), 3: (x, y - length)}[direction]


def _on_wire(point: tuple[int, int], wire: dict[str, str]) -> bool:
    (x1, y1), (x2, y2) = (int(wire["X1"]), int(wire["Y1"])), (int(wire["X2"]), int(wire["Y2"]))
    x, y = point
    return y == y1 == y2 and min(x1, x2) <= x <= max(x1, x2)


def test_label_on_its_stub() -> None:
    found = sample_records()
    u2 = component_index(found, "U2")
    pin3 = next(r for _, r in owned_by(found, u2) if r["RECORD"] == "2" and r["DESIGNATOR"] == "3")
    hot = _hot_end(pin3)
    wires = [r for r in found if r["RECORD"] == "27"]
    (stub,) = [w for w in wires if (int(w["X1"]), int(w["Y1"])) == hot]
    labels = [
        r
        for r in found
        if r["RECORD"] == "25" and _on_wire((int(r["LOCATION.X"]), int(r["LOCATION.Y"])), stub)
    ]
    (label,) = labels
    where = (int(label["LOCATION.X"]), int(label["LOCATION.Y"]))
    assert label["TEXT"] == "LED_DRV" and where == (hot[0] + 10, hot[1])
    assert [w for w in wires if _on_wire(where, w)] == [stub]
    pin_ends = {_hot_end(r) for r in found if r["RECORD"] == "2"}
    assert where not in pin_ends


def test_every_stub_starts_at_a_pin_end() -> None:
    found = sample_records()
    pin_ends = [_hot_end(r) for r in found if r["RECORD"] == "2"]
    starts = [(int(w["X1"]), int(w["Y1"])) for w in found if w["RECORD"] == "27"]
    assert sorted(starts) == sorted(pin_ends) and len(set(starts)) == 19


# --- requirement "Deterministic sheet layout" -----------------------------------------------------------


def test_sample_on_a4() -> None:
    plan = plan_sheet(sample_model())
    assert plan.size.name == "A4"
    assert tuple(p.spec.key for p in plan.parts) == SAMPLE_PATHS
    positions = [(p.cell[1], p.cell[0]) for p in plan.parts]
    assert positions == sorted(positions), "left to right, then top to bottom"
    check_plan(plan)
    for record in sample_records():
        for key in COORDINATES:
            if key in record:
                value = int(record[key])
                limit = 1150 - 50 if key.endswith("X") or key[0] == "X" else 760 - 50
                assert 50 <= value <= limit, (key, value)


# --- library-symbol bodies (change c0034) -----------------------------------------------------------


def test_vertical_labels_ports_and_edge_codes() -> None:
    nets = {"1": PinNet("A", "label"), "2": PinNet("GND", "port", "ground"), "3": PinNet("B", "label")}
    part = PartSpec("X1", "X1", "X", "b.SchLib", "X", None, "AAAAAAAA", upright_symbol(), nets)
    found = [dict(r) for r in schdoc_records(layout_sheet([part]))]
    labels = [r for r in found if r["RECORD"] == "25"]
    assert [r.get("ORIENTATION") for r in labels] == ["1", None]
    (port,) = [r for r in found if r["RECORD"] == "17"]
    assert port["ORIENTATION"] == "3"
    pins = {r["DESIGNATOR"]: r for r in found if r["RECORD"] == "2"}
    assert pins["3"]["SYMBOL_INNEREDGE"] == "3" and "SYMBOL_OUTEREDGE" not in pins["3"]
    assert "SYMBOL_INNEREDGE" not in pins["1"] and pins["1"]["PINCONGLOMERATE"] == str(1 | 0x08 | 0x10)
    assert pins["1"]["PINLENGTH"] == "5" and pins["3"]["ELECTRICAL"] == "0"


# --- multi-part symbols (change c0034) --------------------------------------------------------------


def test_dual_unit_placed_twice() -> None:
    found = records(example_files("ascii")["altium_kicad.SchDoc"])
    parts = [(i, r) for i, r in enumerate(found) if r["RECORD"] == "1" and r["LIBREFERENCE"] == "DUAL_OPAMP"]
    assert [r["CURRENTPARTID"] for _, r in parts] == ["1", "2"]
    assert all(r["PARTCOUNT"] == "3" for _, r in parts)
    assert len({r["UNIQUEID"] for _, r in parts}) == 2
    for index, _ in parts:
        children = [r for _, r in owned_by(found, index)]
        assert [r["TEXT"] for r in children if r["RECORD"] == "34"] == ["U1"]
        pins = [r for r in children if r["RECORD"] == "2"]
        assert sorted(r["DESIGNATOR"] for r in pins) == ["1", "2", "3", "4", "5", "6", "7", "8"]
        assert {r["DESIGNATOR"]: r["OWNERPARTID"] for r in pins}["8"] == "0"
        assert [r["OWNERPARTID"] for r in children if r["RECORD"] == "14"] == ["1", "2"]
        (listing,) = [i for i, r in owned_by(found, index) if r["RECORD"] == "44"]
        assert [r["MODELNAME"] for _, r in owned_by(found, listing)] == ["SOIC8"]


def test_part_zero_stubs_on_part_one_only() -> None:
    plan = example_plan()
    stubs = [s for s in plan.stubs if s.key == "U1"]
    designators = [s.designator for s in stubs]
    assert sorted(designators) == ["1", "2", "3", "4", "5", "6", "7", "8"]
    assert designators.count("8") == 1 and designators.count("4") == 1
    first, second = (p for p in plan.parts if p.spec.key == "U1")
    assert (first.part, second.part) == (1, 2)
    index = plan.parts.index(first)
    assert plan.parts[index + 1] is second, "the parts of one symbol take consecutive cells"
    check_plan(plan, grid=10)
    on_first = {s.designator for s in stubs if first.cell[0] <= s.start[0] <= first.cell[2]}
    assert {"4", "8", "1", "2", "3"} <= on_first
