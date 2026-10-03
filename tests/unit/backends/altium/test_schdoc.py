# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The records of the sample's schematic (capability altium-schematic-writer: "ASCII schematic form",
"Sheet record", "Generic component bodies", "Designator, comment and links", "Connectivity on the sheet"
and "Deterministic sheet layout"; change c0032)."""

from __future__ import annotations

import dataclasses
from collections import Counter
from functools import cache

import pytest
from _altium import (
    HIER_PARTIAL,
    SAMPLE_PATHS,
    check_plan,
    component_index,
    example_files,
    example_model,
    example_plan,
    hier_model,
    model_of,
    owned_by,
    records,
    sample_model,
    upright_symbol,
)

from fenolite.backends.altium.hierarchy import plan_sheets
from fenolite.backends.altium.layout import PartSpec, PinNet, layout_sheet
from fenolite.backends.altium.project import part_specs, plan_sheet, write_project
from fenolite.backends.altium.schdoc import additional_records, schdoc_records, write_schdoc
from fenolite.dsl import Design, Module, Net, Part, connect
from fenolite.model import Design as ModelDesign
from fenolite.model import PinRef

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


# --- No ERC directives (change c0036) ---------------------------------------------------------------

NO_ERC_KEYS = [
    "RECORD", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "COLOR", "ISACTIVE", "SUPPRESSALL", "SYMBOL",
]  # fmt: skip


def _marked(model: ModelDesign, *marks: tuple[str, str]) -> ModelDesign:
    refs = tuple(PinRef(model.by_ref[ref].id if ref in model.by_ref else ref, pin) for ref, pin in marks)
    return dataclasses.replace(model, circuit=dataclasses.replace(model.circuit, no_connects=refs))


def test_no_erc_record_keys_and_order() -> None:
    nets = {"3": PinNet("A", "label")}
    part = PartSpec(
        "X1", "X1", "X", "b.SchLib", "X", None, "AAAAAAAA", upright_symbol(), nets,
        no_connects=frozenset({"1", "2"}),
    )  # fmt: skip
    found = schdoc_records(layout_sheet([part]))
    last = found[-2:]
    assert [[key for key, _ in record] for record in last] == [NO_ERC_KEYS, NO_ERC_KEYS]
    as_dicts = [dict(r) for r in found]
    for record in as_dicts[-2:]:
        assert record["RECORD"] == "22" and record["OWNERPARTID"] == "-1" and record["COLOR"] == "255"
        assert record["ISACTIVE"] == "T" and record["SUPPRESSALL"] == "T"
        assert record["SYMBOL"] == "Thin Cross"
    assert [r["RECORD"] for r in as_dicts].count("22") == 2
    pins = {r["DESIGNATOR"]: _hot_end(r) for r in as_dicts if r["RECORD"] == "2"}
    places = [(int(r["LOCATION.X"]), int(r["LOCATION.Y"])) for r in as_dicts[-2:]]
    assert places == [pins["1"], pins["2"]]
    starts = {(int(w["X1"]), int(w["Y1"])) for w in as_dicts if w["RECORD"] == "27"}
    assert starts == {pins["3"]}, "a marked pin gets no wire"


def test_no_erc_directives_follow_every_stub_label_and_port() -> None:
    model = generic_pins_with_spare()
    found = records(write_project(model, name="lone", form="ascii")["lone.SchDoc"])
    kinds = [r["RECORD"] for r in found]
    first = kinds.index("22")
    assert kinds[first:] == ["22"] and not {"27", "25", "17"} & set(kinds[first:])
    assert max(i for i, k in enumerate(kinds) if k in ("27", "25", "17")) == first - 1
    header = write_project(model, name="lone", form="ascii")["lone.SchDoc"].split(b"\r\n", 1)[0]
    assert header.endswith(f"|WEIGHT={len(found)}".encode()), "WEIGHT counts the directive"


def generic_pins_with_spare() -> ModelDesign:
    """Two resistors of one lib id; ``R2`` uses pin 1 only, and its pin 2 is marked."""
    design = Design("lone")
    r1 = Part("R1", "L.SchLib:RES", "L.PcbLib:R0603", "1k")
    r2 = Part("R2", "L.SchLib:RES", "L.PcbLib:R0603", "1k")
    design.add(r1, r2)
    a, b = Net("A"), Net("B")
    connect(a, r1[1], r2[1])
    connect(b, r1[2])
    return _marked(model_of(design), ("R2", "2"))


def test_no_connect_free_design_has_no_no_erc_record() -> None:
    assert all(r["RECORD"] != "22" for r in sample_records())
    assert plan_sheet(sample_model()).no_connects == ()


@pytest.mark.parametrize(
    ("mark", "match"),
    [
        (("U2", "1"), r"U2 pin 1 .*net"),
        (("U2", "9"), r"U2 holds no pin '9'"),
        (("cmp_nope", "1"), r"unknown component cmp_nope"),
    ],
)
def test_no_connect_mark_refused_by_the_writer(mark: tuple[str, str], match: str) -> None:
    model = _marked(sample_model(), mark)
    with pytest.raises(ValueError, match=match):
        part_specs(model)
    with pytest.raises(ValueError, match=match):
        write_project(model, name="altium_sample")


# --- sheet symbols, sheet entries and ports (change c0037) -------------------------------------------

HIERARCHY_RECORDS = ("15", "16", "18", "32", "33")


def _dicts(plan: object) -> list[dict[str, str]]:
    return [dict(record) for record in schdoc_records(plan)]  # type: ignore[arg-type]


def hier_sheets(form: str = "ascii") -> dict[str, list[dict[str, str]]]:
    """File name → the ``FileHeader`` records of each sheet of the hierarchy sample's ``modules`` build."""
    project = plan_sheets(hier_model(), name="altium_hier", sheets="modules", form=form)  # type: ignore[arg-type]
    return {sheet.file: _dicts(sheet.plan) for sheet in project.sheets}


def test_sheet_symbol_blocks_follow_the_sheet_record() -> None:
    top = hier_sheets()["altium_hier.SchDoc"]
    kinds = [r["RECORD"] for r in top]
    first_component = kinds.index("1")
    assert kinds[:first_component] == ["31", "15", *["16"] * 5, "32", "33", "15", *["16"] * 6, "32", "33"]
    assert not set(kinds[first_component:]) & set(HIERARCHY_RECORDS)
    flash, mcu = (r for r in top if r["RECORD"] == "15")
    assert list(flash) == [
        "RECORD", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "XSIZE", "YSIZE", "COLOR", "AREACOLOR",
        "ISSOLID", "UNIQUEID", "SYMBOLTYPE",
    ]  # fmt: skip
    assert (flash["OWNERPARTID"], flash["COLOR"], flash["AREACOLOR"]) == ("-1", "128", "8454016")
    assert (flash["ISSOLID"], flash["SYMBOLTYPE"], flash["XSIZE"]) == ("T", "Normal", "190")
    assert flash["YSIZE"] == "60" and mcu["YSIZE"] == "70", "(slots + 1) x 100 mil"
    names = [(r["RECORD"], r["TEXT"], int(r["OWNERINDEX"])) for r in top if r["RECORD"] in ("32", "33")]
    assert names == [
        ("32", "flash", 1),
        ("33", "altium_hier_flash.SchDoc", 1),
        ("32", "mcu", 9),
        ("33", "altium_hier_mcu.SchDoc", 9),
    ]
    name, file_name = (r for r in top if r["RECORD"] in ("32", "33") and r["OWNERINDEX"] == "1")
    assert list(name) == [
        "RECORD", "OWNERINDEX", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "COLOR", "FONTID", "TEXT",
    ]  # fmt: skip
    assert (file_name["LOCATION.X"], file_name["LOCATION.Y"]) == (flash["LOCATION.X"], flash["LOCATION.Y"])
    assert (name["LOCATION.X"], int(name["LOCATION.Y"])) == (
        flash["LOCATION.X"],
        int(flash["LOCATION.Y"]) + 10,
    )
    assert not any("INDEXINSHEET" in r for r in top)


FLASH_NETS = ("FLASH_WP", "SPI_CS", "SPI_MISO", "SPI_MOSI", "SPI_SCK")
MCU_NETS = ("FLASH_WP", "RESET_N", "SPI_CS", "SPI_MISO", "SPI_MOSI", "SPI_SCK")


def test_sheet_entry_keys_and_order() -> None:
    top = hier_sheets()["altium_hier.SchDoc"]
    entries = [r for r in top if r["RECORD"] == "16"]
    assert [(r["OWNERINDEX"], r["NAME"], r["DISTANCEFROMTOP"]) for r in entries] == [
        *(("1", name, str(k)) for k, name in enumerate(FLASH_NETS, 1)),
        *(("9", name, str(k)) for k, name in enumerate(MCU_NETS, 1)),
    ]
    keys = [
        "RECORD", "OWNERINDEX", "OWNERPARTID", "SIDE", "DISTANCEFROMTOP", "COLOR", "AREACOLOR", "TEXTCOLOR",
        "TEXTFONTID", "TEXTSTYLE", "NAME", "ARROWKIND",
    ]  # fmt: skip
    assert all(list(r) == keys for r in entries)
    first = entries[0]
    assert (first["SIDE"], first["COLOR"], first["AREACOLOR"], first["TEXTCOLOR"]) == (
        "1",
        "128",
        "8454143",
        "128",
    )
    assert (first["TEXTFONTID"], first["TEXTSTYLE"], first["ARROWKIND"]) == ("1", "Full", "Block & Triangle")
    assert not any("IOTYPE" in r or "UNIQUEID" in r for r in entries)


def test_sheet_entry_on_the_edge() -> None:
    """Scenario "Entry on the edge": the stub of ``RESET_N`` on the symbol ``mcu`` starts on the right edge,
    ``DISTANCEFROMTOP`` x 100 mil below the top-left corner, and its label lies on the stub."""
    top = hier_sheets()["altium_hier.SchDoc"]
    symbol = top[9]
    assert symbol["RECORD"] == "15" and top[16]["TEXT"] == "mcu"
    (entry,) = (r for r in top if r["RECORD"] == "16" and r["OWNERINDEX"] == "9" and r["NAME"] == "RESET_N")
    x = int(symbol["LOCATION.X"]) + int(symbol["XSIZE"])
    y = int(symbol["LOCATION.Y"]) - 10 * int(entry["DISTANCEFROMTOP"])
    wires = [r for r in top if r["RECORD"] == "27" and (int(r["X1"]), int(r["Y1"])) == (x, y)]
    assert len(wires) == 1
    (wire,) = wires
    label = top[top.index(wire) + 1]
    assert label["RECORD"] == "25" and label["TEXT"] == "RESET_N"
    assert int(wire["Y2"]) == y == int(label["LOCATION.Y"]) and int(wire["X2"]) > x
    assert x < int(label["LOCATION.X"]) < int(wire["X2"])


def test_sheet_entry_stubs_follow_the_last_component_and_precede_the_pin_stubs() -> None:
    top = hier_sheets()["altium_hier.SchDoc"]
    kinds = [r["RECORD"] for r in top]
    first_wire = kinds.index("27")
    assert not {"1", "2", "14", "34", "41", "44", "45", "46", "48"} & set(kinds[first_wire:])
    tail = [(r["RECORD"], r.get("TEXT", "")) for r in top[first_wire:] if r["RECORD"] != "27"]
    assert [text for _, text in tail] == [*FLASH_NETS, *MCU_NETS, "VDD", "GND", "RESET_N"]
    assert [kind for kind, _ in tail] == [*["25"] * 11, "17", "17", "25"]


def test_no_sheet_symbol_in_the_flat_mode() -> None:
    """Scenario "No symbol in the flat mode": the sample has two modules and one flat sheet."""
    assert not {r["RECORD"] for r in sample_records()} & set(HIERARCHY_RECORDS)
    flat = plan_sheets(hier_model(), name="altium_hier", sheets="flat", form="binary")
    assert not {r["RECORD"] for r in _dicts(flat.top.plan)} & set(HIERARCHY_RECORDS)


def test_no_sheet_symbol_without_modules() -> None:
    """Scenario "No symbol without modules": the KiCad example has no module, so both modes give one sheet
    with the same bytes."""
    model, symbols = example_model()
    flat = plan_sheets(model, name="altium_kicad", sheets="flat", form="ascii", symbols=symbols)
    split = plan_sheets(model, name="altium_kicad", sheets="modules", form="ascii", symbols=symbols)
    assert len(split.sheets) == 1
    data = write_schdoc(split.top.plan)
    assert data == write_schdoc(flat.top.plan)
    assert not {r["RECORD"] for r in records(data)} & set(HIERARCHY_RECORDS)


def test_port_records_of_the_module_sheets() -> None:
    sheets = hier_sheets()
    port_keys = [
        "RECORD", "OWNERPARTID", "WIDTH", "LOCATION.X", "LOCATION.Y", "COLOR", "FONTID", "AREACOLOR",
        "TEXTCOLOR", "NAME", "UNIQUEID", "HEIGHT",
    ]  # fmt: skip
    for file, names in (("altium_hier_flash.SchDoc", FLASH_NETS), ("altium_hier_mcu.SchDoc", MCU_NETS)):
        found = sheets[file]
        kinds = [r["RECORD"] for r in found]
        assert not {"15", "16", "32", "33"} & set(kinds), "no module sheet holds a sheet symbol"
        first = kinds.index("18")
        assert not {"1", "2", "14", "34", "41"} & set(kinds[first:]), "ports follow the last component record"
        ports = [r for r in found if r["RECORD"] == "18"]
        assert [r["NAME"] for r in ports] == list(names)
        assert kinds[first : first + 3 * len(ports)] == ["18", "27", "25"] * len(ports)
        assert all(kind in ("27", "25", "17") for kind in kinds[first + 3 * len(ports) :])
        for port in ports:
            assert list(port) == port_keys
            colours = (port["COLOR"], port["FONTID"], port["AREACOLOR"], port["TEXTCOLOR"], port["HEIGHT"])
            assert colours == ("128", "1", "8454143", "128", "10")
            assert int(port["WIDTH"]) == max(30, -(-(70 * len(port["NAME"]) + 150) // 100) * 10)
            wire, label = found[found.index(port) + 1], found[found.index(port) + 2]
            right_end = (str(int(port["LOCATION.X"]) + int(port["WIDTH"])), port["LOCATION.Y"])
            assert (wire["X1"], wire["Y1"]) == right_end
            assert label["TEXT"] == port["NAME"] and label["LOCATION.Y"] == wire["Y1"]
            assert int(wire["X1"]) < int(label["LOCATION.X"]) < int(wire["X2"])


def test_port_and_sheet_entry_names_match() -> None:
    """Scenario "Port and entry names match", in both forms."""
    for form in ("ascii", "binary"):
        sheets = hier_sheets(form)
        top = sheets["altium_hier.SchDoc"]
        files = {int(r["OWNERINDEX"]): r["TEXT"] for r in top if r["RECORD"] == "33"}
        assert sorted(files.values()) == ["altium_hier_flash.SchDoc", "altium_hier_mcu.SchDoc"]
        for owner, file in files.items():
            entries = [r["NAME"] for r in top if r["RECORD"] == "16" and int(r["OWNERINDEX"]) == owner]
            ports = [r["NAME"] for r in sheets[file] if r["RECORD"] == "18"]
            assert entries == ports and len(set(ports)) == len(ports) and ports


def test_port_free_module_gets_a_symbol_without_entries() -> None:
    """A module whose nets all stay on its sheet gets no port, and its sheet symbol no entry."""
    design = Design("x")
    lone = Module("lone")
    r1, r2 = Part("R1", "L.SchLib:RES"), Part("R2", "L.SchLib:RES")
    lone.add(r1, r2)
    design.add(lone)
    connect(Net("A"), r1[1], r2[1])
    project = plan_sheets(model_of(design), name="x", sheets="modules", form="ascii")
    top, sheet = (_dicts(s.plan) for s in project.sheets)
    assert [r["RECORD"] for r in top] == ["31", "15", "32", "33"]
    assert "18" not in {r["RECORD"] for r in sheet}


# --- harness records (change c0037, "Harness records") -----------------------------------------------

DBG = '\ndesign.add(Harness("DBG", {"RST": reset_n}))\n'


def hier_plans(**variant: object) -> dict[str, object]:
    """File name → the plan of each sheet of the hierarchy sample's binary ``modules`` build."""
    model = hier_model(**variant)  # type: ignore[arg-type]
    name = "altium_hier_partial" if variant.get("script") else "altium_hier"
    project = plan_sheets(model, name=name, sheets="modules", form="binary")
    return {sheet.file: sheet.plan for sheet in project.sheets}


def _additional(plan: object) -> list[dict[str, str]]:
    return [dict(record) for record in additional_records(plan)]  # type: ignore[arg-type]


def _wires(found: list[dict[str, str]]) -> dict[tuple[int, int], dict[str, str]]:
    """Start point → the label that follows each wire."""
    return {
        (int(r["X1"]), int(r["Y1"])): found[i + 1]
        for i, r in enumerate(found)
        if r["RECORD"] == "27" and found[i + 1]["RECORD"] == "25"
    }


def test_harness_block_of_the_flash_sheet() -> None:
    """Scenario "Block of the flash sheet"."""
    found = _additional(hier_plans()["altium_hier_flash.SchDoc"])
    assert [r["RECORD"] for r in found] == ["215", "216", "216", "216", "216", "217", "218"]
    connector, *entries, kind, line = found
    assert list(connector) == [
        "RECORD", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "XSIZE", "YSIZE", "LINEWIDTH", "COLOR",
        "AREACOLOR", "PRIMARYCONNECTIONPOSITION",
    ]  # fmt: skip
    assert (connector["XSIZE"], connector["YSIZE"], connector["PRIMARYCONNECTIONPOSITION"]) == (
        "50",
        "50",
        "20",
    )
    assert (connector["LINEWIDTH"], connector["COLOR"], connector["AREACOLOR"]) == (
        "1",
        "13213327",
        "16511725",
    )
    assert "HARNESSCONNECTORSIDE" not in connector
    assert [(r["NAME"], r["DISTANCEFROMTOP"]) for r in entries] == [
        ("CS", "1"),
        ("MISO", "2"),
        ("MOSI", "3"),
        ("SCK", "4"),
    ]
    for entry in entries:
        assert list(entry) == [
            "RECORD", "OWNERINDEXADDITIONALLIST", "OWNERPARTID", "SIDE", "DISTANCEFROMTOP", "COLOR",
            "AREACOLOR", "TEXTCOLOR", "TEXTFONTID", "TEXTSTYLE", "NAME",
        ]  # fmt: skip
        assert (entry["OWNERINDEXADDITIONALLIST"], entry["OWNERPARTID"], entry["SIDE"]) == ("T", "-1", "1")
        assert (entry["COLOR"], entry["AREACOLOR"], entry["TEXTCOLOR"]) == ("7354880", "8454143", "7354880")
        assert (entry["TEXTFONTID"], entry["TEXTSTYLE"]) == ("1", "Full")
    assert list(kind) == [
        "RECORD", "OWNERINDEXADDITIONALLIST", "OWNERPARTID", "LOCATION.X", "LOCATION.Y", "COLOR", "FONTID",
        "TEXT",
    ]  # fmt: skip
    assert (kind["TEXT"], kind["COLOR"], kind["FONTID"]) == ("SPI", "8388608", "1")
    assert (kind["LOCATION.X"], kind["LOCATION.Y"]) == (connector["LOCATION.X"], connector["LOCATION.Y"])
    assert list(line) == [
        "RECORD", "OWNERPARTID", "LINEWIDTH", "COLOR", "LOCATIONCOUNT", "X1", "Y1", "X2", "Y2",
    ]  # fmt: skip
    assert (line["LINEWIDTH"], line["COLOR"], line["LOCATIONCOUNT"]) == ("2", "15187117", "2")
    assert not any("UNIQUEID" in r or "INDEXINSHEET" in r for r in found)


def test_harness_line_joins_port_and_connector() -> None:
    """Scenario "Line joins port and connector"."""
    plan = hier_plans()["altium_hier_flash.SchDoc"]
    (port,) = (r for r in _dicts(plan) if r["RECORD"] == "18" and r["NAME"] == "SPI")
    assert port["HARNESSTYPE"] == "SPI" and list(port)[-3:] == ["HARNESSTYPE", "UNIQUEID", "HEIGHT"]
    connector, *_, line = _additional(plan)
    start = (int(port["LOCATION.X"]) + int(port["WIDTH"]), int(port["LOCATION.Y"]))
    assert (int(line["X1"]), int(line["Y1"])) == start
    end = (
        int(connector["LOCATION.X"]),
        int(connector["LOCATION.Y"]) - int(connector["PRIMARYCONNECTIONPOSITION"]),
    )
    assert (int(line["X2"]), int(line["Y2"])) == end
    assert end == (start[0] + 20, start[1]), "200 mil apart on one horizontal line"


def test_harness_entry_stubs_carry_net_names() -> None:
    """Scenario "Entry stubs carry net names"."""
    plan = hier_plans()["altium_hier_flash.SchDoc"]
    connector = _additional(plan)[0]
    edge = int(connector["LOCATION.X"]) + int(connector["XSIZE"])
    top = int(connector["LOCATION.Y"])
    wires = _wires(_dicts(plan))
    on_edge = {point: label["TEXT"] for point, label in wires.items() if point[0] == edge}
    assert on_edge == {
        (edge, top - 10): "SPI_CS",
        (edge, top - 20): "SPI_MISO",
        (edge, top - 30): "SPI_MOSI",
        (edge, top - 40): "SPI_SCK",
    }


def test_harness_sheet_entries_and_ports_carry_the_type() -> None:
    """Scenarios "Symbols of the hierarchy sample" and "Ports of the hierarchy sample" (record counts)."""
    plans = hier_plans()
    top = _dicts(plans["altium_hier.SchDoc"])
    kinds = Counter(r["RECORD"] for r in top)
    assert (kinds["15"], kinds["16"], kinds["32"], kinds["33"]) == (2, 5, 2, 2)
    assert (kinds["27"], kinds["25"], kinds["17"], kinds["18"]) == (14, 12, 2, 0)
    entries = [r for r in top if r["RECORD"] == "16"]
    assert [r.get("HARNESSTYPE") for r in entries] == [None, "SPI", None, None, "SPI"]
    assert [r["NAME"] for r in entries] == ["FLASH_WP", "SPI", "FLASH_WP", "RESET_N", "SPI"]
    assert [r["DISTANCEFROMTOP"] for r in entries] == ["1", "4", "1", "2", "5"]
    harness = entries[1]
    assert list(harness)[-3:] == ["NAME", "HARNESSTYPE", "ARROWKIND"] and "IOTYPE" not in harness
    assert [r["TEXT"] for r in top if r["RECORD"] == "32"] == ["flash", "mcu"]
    assert [r["TEXT"] for r in top if r["RECORD"] == "33"] == [
        "altium_hier_flash.SchDoc",
        "altium_hier_mcu.SchDoc",
    ]
    for file, ports, wires, labels, power in (
        ("altium_hier_mcu.SchDoc", [("FLASH_WP", None), ("RESET_N", None), ("SPI", "SPI")], 16, 12, 4),
        ("altium_hier_flash.SchDoc", [("FLASH_WP", None), ("SPI", "SPI")], 17, 12, 5),
    ):
        found = _dicts(plans[file])
        kinds = Counter(r["RECORD"] for r in found)
        assert [(r["NAME"], r.get("HARNESSTYPE")) for r in found if r["RECORD"] == "18"] == ports
        assert (kinds["27"], kinds["25"], kinds["17"]) == (wires, labels, power), file


def test_harness_entry_of_a_net_that_does_not_cross() -> None:
    """Scenario "Entry of a net that does not cross" (``partial.py``): every block holds five entries, and
    no wire starts at the connection point of a ``HOLD`` entry."""
    plans = hier_plans(script=HIER_PARTIAL)
    blocks = 0
    for plan in plans.values():
        found = _additional(plan)
        starts = set(_wires(_dicts(plan)))
        connectors = [r for r in found if r["RECORD"] == "215"]
        blocks += len(connectors)
        for connector in connectors:
            index = found.index(connector)
            entries = found[index + 1 : index + 6]
            assert [r["NAME"] for r in entries] == ["CS", "HOLD", "MISO", "MOSI", "SCK"]
            assert found[index + 6]["RECORD"] == "217" and connector["YSIZE"] == "60"
            edge = int(connector["LOCATION.X"]) + int(connector["XSIZE"])
            points = {
                r["NAME"]: (edge, int(connector["LOCATION.Y"]) - 10 * int(r["DISTANCEFROMTOP"]))
                for r in entries
            }
            assert points["HOLD"] not in starts
            assert all(points[name] in starts for name in ("CS", "MISO", "MOSI", "SCK"))
    assert blocks == 4
    labels = [r["TEXT"] for plan in plans.values() for r in _dicts(plan) if r["RECORD"] == "25"]
    assert labels.count("FLASH_HOLD_N") == 2, "only the two pins on the flash sheet"


def test_harness_second_connector_names_its_index() -> None:
    """Scenario "Second connector names its index": a second harness ``DBG`` crosses ``mcu``."""
    found = _additional(hier_plans(append=DBG)["altium_hier.SchDoc"])
    connectors = [i for i, r in enumerate(found) if r["RECORD"] == "215"]
    assert connectors == [0, 7, 11]
    assert [found[i + 1]["NAME"] for i in connectors] == ["CS", "RST", "CS"]
    for position, index in enumerate(connectors):
        end = connectors[position + 1] if position + 1 < len(connectors) else len(found)
        children = [r for r in found[index:end] if r["RECORD"] in ("216", "217")]
        assert children and found[end - 1]["RECORD"] == "218"
        if index == 0:
            assert all("OWNERINDEX" not in r for r in children)
        else:
            assert all(r["OWNERINDEX"] == str(index) for r in children)
            assert all(list(r)[:3] == ["RECORD", "OWNERINDEX", "OWNERINDEXADDITIONALLIST"] for r in children)
    assert all("OWNERINDEX" not in r for r in found if r["RECORD"] in ("215", "218"))
    assert [r["TEXT"] for r in found if r["RECORD"] == "217"] == ["SPI", "DBG", "SPI"]


def test_ascii_writer_refuses_a_harness_block() -> None:
    """Scenario "ASCII writer refuses a block"."""
    plan = hier_plans()["altium_hier_flash.SchDoc"]
    with pytest.raises(ValueError, match="SPI"):
        write_schdoc(plan)  # type: ignore[arg-type]


def test_no_harness_block_in_the_flat_mode_or_the_ascii_form() -> None:
    model = hier_model()
    flat = plan_sheets(model, name="altium_hier", sheets="flat", form="binary")
    assert additional_records(flat.top.plan) == [] and additional_records(plan_sheet(sample_model())) == []
    for sheet in plan_sheets(model, name="altium_hier", sheets="modules", form="ascii").sheets:
        assert additional_records(sheet.plan) == []
        assert write_schdoc(sheet.plan).startswith(b"|HEADER=")
