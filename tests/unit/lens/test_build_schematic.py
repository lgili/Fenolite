# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A build with a schematic: its symbol libraries, the board that follows the sheet, and the stand-in for
KiCad's update (capability design-dsl, "Schematic in a build", "Symbols of a built project" and "Board
follows the schematic"; capability layout-lens, "Boards updated from the schematic keep their layout";
change c0061)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from _buildhelp import blink, build, resolver
from _layout_edit import EDIT_UUIDS, edit_blink, update_from_schematic
from _preserve_help import rebuild
from _schbuild import (
    SLASH_NET,
    blink_slash,
    blink_unmarked,
    built_nested,
    built_stacked,
    built_units,
    global_build,
    sheet_of,
)

from fenolite.backends.kicad import schgen
from fenolite.backends.kicad.libs import read_lib_table
from fenolite.backends.kicad.pcb import kicad_uuid, read_board
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.backends.kicad.sym import read_symbol_library, write_symbol_library
from fenolite.dsl import Net, Symbol, connect, mm, placements, to_model
from fenolite.lens.build import (
    BUILD_ISSUE_CODES,
    RECORD_FILE,
    BuildOutput,
    build_design,
    lower_for_schematic,
)
from fenolite.model import canonical

UNCONNECTED = "unconnected-("


def text(output: BuildOutput, name: str = "blink.kicad_pcb") -> str:
    return output.files[name].decode("utf-8")


def footprint(output: BuildOutput, ref: str, name: str = "blink.kicad_pcb") -> Node:
    for item in parse(text(output, name)).nodes("footprint"):
        fields = {p.atoms()[0].value: p.atoms()[1].value for p in item.nodes("property")}
        if fields.get("Reference") == ref:
            return item
    raise AssertionError(ref)


def pad_net(item: Node, number: str) -> list[str]:
    (pad,) = [p for p in item.nodes("pad") if p.atoms()[0].value == number]
    net = pad.find("net")
    return [a.value for a in net.atoms()] if net is not None else []


def rows(output: BuildOutput) -> list[tuple[str, str]]:
    table = read_lib_table(text(output, "sym-lib-table"), file="sym-lib-table")
    return [(row.nickname, row.uri) for row in table.rows]


# -- symbols of a built project


def test_libraries_of_the_blink() -> None:
    output = build(blink(), 9)
    mini = read_symbol_library(text(output, "lib/Mini.kicad_sym"), library="Mini")
    assert [s.name for s in mini] == ["Mini_LED", "Mini_QFP32_IC", "Mini_R"]
    (flag,) = read_symbol_library(text(output, "lib/fenolite.kicad_sym"), library="fenolite")
    assert flag.name == "PWR_FLAG"
    assert rows(output) == [
        ("Mini", "${KIPRJMOD}/lib/Mini.kicad_sym"),
        ("fenolite", "${KIPRJMOD}/lib/fenolite.kicad_sym"),
    ]
    assert "(version" not in text(output, "sym-lib-table")
    assert "(version 7)" in text(build(blink(), 10), "sym-lib-table")
    summary = output.summary["schematic"]
    assert summary == {
        "file": "blink.kicad_sch",
        "paper": "A4",
        "sheets": 1,
        "files": [],
        "symbols": 5,
        "labels": 7,
        "no_connects": 29,
        "wires": 2,
        "satellites": 2,
        "power_flags": 2,
        "libraries": ["lib/Mini.kicad_sym", "lib/fenolite.kicad_sym"],
        "unconnected_pads": 29,
    }


def test_the_sheet_embeds_what_the_libraries_hold() -> None:
    output = build(blink())
    sheet = sheet_of(output)
    embedded = {f"{d.library}:{d.name}": d for d in sheet.lib_symbols}
    assert sorted(embedded) == ["Mini:Mini_LED", "Mini:Mini_QFP32_IC", "Mini:Mini_R", "fenolite:PWR_FLAG"]
    for nickname in ("Mini", "fenolite"):
        for symbol in read_symbol_library(text(output, f"lib/{nickname}.kicad_sym"), library=nickname):
            assert embedded[symbol.lib_id].pins == symbol.pins


def test_build_record_and_evidence() -> None:
    output = build(blink())
    record = json.loads(output.files[RECORD_FILE])["files"]
    for path in ("blink.kicad_sch", "sym-lib-table", "lib/Mini.kicad_sym", "lib/fenolite.kicad_sym"):
        assert record[path] == hashlib.sha256(output.files[path]).hexdigest()
    assert set(schgen.EVIDENCE.hypotheses) <= set(output.evidence.hypotheses)
    assert not set(schgen.EVIDENCE.hypotheses) & set(build(blink(), schematic="skip").evidence.hypotheses)


def test_project_policy(tmp_path: Path) -> None:
    output = global_build(tmp_path, vendor="project")
    assert "lib/Mini.kicad_sym" not in output.files and "lib/fenolite.kicad_sym" in output.files
    assert rows(output) == [("fenolite", "${KIPRJMOD}/lib/fenolite.kicad_sym")]
    assert len([d for d in sheet_of(output).lib_symbols if d.library == "Mini"]) == 3
    symbols = [i for i in output.issues if i.code == "build.global-library" and "symbol" in i.message]
    assert sorted(i.where for i in symbols) == ["Mini:Mini_LED", "Mini:Mini_QFP32_IC", "Mini:Mini_R"]
    assert all(i.severity == "info" for i in symbols)
    full = global_build(tmp_path / "all")
    assert "lib/Mini.kicad_sym" in full.files and not [
        i for i in full.issues if i.code == "build.global-library"
    ]


def test_a_changed_symbol_library_is_reported() -> None:
    first = build(blink())
    record = dict(json.loads(first.files[RECORD_FILE])["files"])
    assert "build.library-changed" not in [i.code for i in build(blink(), record=record).issues]
    record["lib/Mini.kicad_sym"] = "0" * 64
    found = [i for i in build(blink(), record=record).issues if i.code == "build.library-changed"]
    assert [(i.severity, i.where) for i in found] == [("warning", "lib/Mini.kicad_sym")]


def authored_build(**kwargs: object) -> tuple[BuildOutput, Symbol, Symbol]:
    design = blink()
    used = Symbol("Local", "Res", reference="R", value="Res", footprint="Mini:Mini_R_0603")
    used.pin("1", "A", etype="passive", at=(mm(-2.54), mm(0)), length=mm(1.27))
    used.pin("2", "B", etype="passive", at=(mm(2.54), mm(0)), length=mm(1.27), rotation=180)
    spare = Symbol("Local", "Spare", reference="J", value="Spare")
    spare.pin("1", "P", etype="passive", at=(mm(0), mm(0)), length=mm(2.54))
    design.add(used, spare)
    design.parts["R1"].lib_id = "Local:Res"
    output = build_design(
        to_model(design),
        placements(design),
        name=design.name,
        copper=2,
        resolver=resolver(10),
        authored_symbols={s.lib_id: s.definition for s in (used, spare)},
        **kwargs,  # type: ignore[arg-type]
    )
    return output, used, spare


def test_an_authored_library_has_the_same_bytes_with_and_without_a_schematic() -> None:
    written, used, spare = authored_build()
    skipped, _, _ = authored_build(schematic="skip")
    assert written.files["lib/Local.kicad_sym"] == skipped.files["lib/Local.kicad_sym"]
    assert text(written, "lib/Local.kicad_sym") == write_symbol_library(
        [used.definition, spare.definition], target=10
    )
    assert [n for n, _ in rows(written)] == ["Local", "Mini", "fenolite"]
    assert [n for n, _ in rows(skipped)] == ["Local"] and "blink.kicad_sch" not in skipped.files
    assert written.summary["libraries"]["Local:Res"] == "authored"  # type: ignore[index]
    assert {s.lib_ref for s in sheet_of(written).symbols} >= {"Local:Res"}


def test_authoring_in_the_reserved_library_is_refused() -> None:
    design = blink()
    mine = Symbol("fenolite", "Mine", reference="J")
    mine.pin("1", "P", etype="passive", at=(mm(0), mm(0)), length=mm(2.54))
    output = build_design(
        to_model(design),
        placements(design),
        name=design.name,
        copper=2,
        resolver=resolver(10),
        authored_symbols={mine.lib_id: mine.definition},
    )
    assert output.files == {} and "build.reserved-library" in [i.code for i in output.issues]
    assert BUILD_ISSUE_CODES["build.reserved-library"] == "error"


# -- the option


def test_skipping_the_schematic() -> None:
    output = build(blink(), schematic="skip")
    assert not [p for p in output.files if p.endswith((".kicad_sch", ".kicad_sym")) or p == "sym-lib-table"]
    assert output.summary["schematic"] is None and output.schematic is None
    assert UNCONNECTED not in text(output) and "(path " not in text(output)
    written = build(blink())
    assert set(written.files) - set(output.files) == {
        "blink.kicad_sch",
        "sym-lib-table",
        "lib/Mini.kicad_sym",
        "lib/fenolite.kicad_sym",
    }
    for path in ("blink.kicad_pro", "blink.kicad_dru", "fp-lib-table"):
        assert written.files[path] == output.files[path]


def test_unknown_mode() -> None:
    with pytest.raises(ValueError, match="write, skip"):
        build(blink(), schematic="maybe")


def test_two_builds_are_identical() -> None:
    assert build(blink()).files == build(blink()).files
    assert built_units(9).files == built_units(9).files


def test_a_generator_error_writes_nothing() -> None:
    from fenolite.backends.kicad.schlayout import SymbolPlacement

    short = {
        "R1": SymbolPlacement(25_400_000, 25_400_000),
        "D1": SymbolPlacement(25_400_000, 29_210_000 + 3_810_000, 270),
    }
    output = build(blink(), symbol_placements=short)
    assert output.files == {} and "build.symbol-short" in [i.code for i in output.issues]


# -- the board follows the schematic


def test_pads_of_unconnected_pins() -> None:
    output = build(blink(), 10)
    u1 = footprint(output, "U1")
    assert pad_net(u1, "2") == ["unconnected-(U1-PA1-Pad2)"]
    assert pad_net(u1, "16") == ["unconnected-(U1-Pad16)"]
    assert pad_net(u1, "9") == ["VIN"]
    symbol = next(s for s in sheet_of(output).symbols if s.ref == "U1")
    assert u1.find("path").atoms()[0].value == f"/{symbol.native_ids['kicad']}"  # type: ignore[union-attr]
    assert u1.find("sheetname") is None and u1.find("sheetfile") is None


def test_numbered_form_for_target_9() -> None:
    output = build(blink(), 9)
    board = text(output)
    table = re.findall(r'^\t\(net (\d+) "(unconnected-\(U1-[^"]*)"\)$', board, flags=re.M)
    assert len(table) == 29
    for number, name in table:
        assert len(re.findall(rf'\(net {number} "{re.escape(name)}"\)', board)) == 2  # the row and one pad


def test_the_stored_model_stays_clean() -> None:
    output = build(blink())
    circuit = json.loads(output.files[".fenolite/circuit.json"])
    board = json.loads(output.files[".fenolite/board.json"])
    assert not [n["name"] for n in circuit["nets"] if n["name"].startswith(UNCONNECTED)]
    assert UNCONNECTED not in output.files[".fenolite/board.json"].decode("utf-8")
    assert board is not None
    for design in (output.design, output.layout):
        assert design is not None and design.board is not None
        assert not [n for n in design.circuit.nets if n.name.startswith(UNCONNECTED)]
        ids = {c.id: c.ref for c in design.circuit.components}
        (u1,) = [f for f in design.board.footprints if ids[f.component_id or ""] == "U1"]
        assert next(p for p in u1.pads if p.number == "2").net_id is None
        assert not [i for i in design.validate() if UNCONNECTED in i.message]
    assert all(not c.path for c in output.design.circuit.components)
    assert {n: t for n, t in canonical.dump_texts(output.layout).items()} == {  # type: ignore[arg-type]
        n.split("/", 1)[1]: output.files[n].decode("utf-8")
        for n in output.files
        if n.startswith(".fenolite/") and n != RECORD_FILE
    }


def test_the_written_board_reads_back_with_the_names() -> None:
    output = build(blink(), 10)
    design = read_board(text(output))
    named = [n for n in design.circuit.nets if n.name.startswith(UNCONNECTED)]
    assert len(named) == 29 and all(len(n.members) == 1 for n in named)
    assert {c.ref: bool(c.path) for c in design.circuit.components} == {"D1": True, "R1": True, "U1": True}


def test_slash_net() -> None:
    design = blink_slash()
    output = build(design, 10)
    board = text(output)
    assert '(net "mod{slash}LED_A")' in board and f'"{SLASH_NET}"' not in board
    assert '(global_label "mod{slash}LED_A"' in text(output, "blink.kicad_sch")
    circuit = json.loads(output.files[".fenolite/circuit.json"])
    assert SLASH_NET in [n["name"] for n in circuit["nets"]]
    assert "{slash}" not in output.files[".fenolite/circuit.json"].decode("utf-8")
    nine = build(design, 9)
    assert len(re.findall(r'^\t\(net \d+ "mod\{slash\}LED_A"\)$', text(nine), flags=re.M)) == 1
    assert build(design, 10).files == output.files
    assert [n.name for n in read_board(board).circuit.nets if "LED_A" in n.name] == [SLASH_NET]


def test_the_units_design() -> None:
    output = built_units()
    u2 = footprint(output, "U2", "units.kicad_pcb")
    assert pad_net(u2, "1") == ["unconnected-(U2-Pad1)"] and pad_net(u2, "7") == ["GND"]
    assert pad_net(u2, "9") == []  # a pad without a pin stays on no net
    first = next(s for s in sheet_of(output).symbols if s.ref == "U2" and s.unit == 1)
    assert u2.find("path").atoms()[0].value == f"/{first.native_ids['kicad']}"  # type: ignore[union-attr]
    d1 = footprint(output, "D1", "units.kicad_pcb")
    assert pad_net(d1, "2") == ["GND"] and pad_net(d1, "1") == ["mod{slash}LED_A"]


def test_lowering_is_pure_and_idempotent() -> None:
    output = build(blink())
    assert output.schematic is not None
    once = lower_for_schematic(output.design, output.schematic)
    assert lower_for_schematic(once, output.schematic) == once
    assert once != output.design and output.design == build(blink()).design
    added = [n for n in once.circuit.nets if n.name.startswith(UNCONNECTED)]
    assert len(added) == 29 and all(n.netclass_id is None and n.members == () for n in added)
    assert [n for n in once.circuit.nets if not n.name.startswith(UNCONNECTED)] == list(
        output.design.circuit.nets
    )
    assert all(c.path.startswith("/") for c in once.circuit.components)


def test_a_pin_connected_later_takes_its_net_back() -> None:
    """A pad that an earlier build named ``unconnected-(…)`` follows the script when its pin gets a net."""
    first = build(blink_unmarked())
    design = blink_unmarked()
    connect(Net("SENSE"), design.parts["U1"][2], design.parts["U1"][3])
    again = rebuild(design, text(first))
    u1 = footprint(again, "U1")
    assert pad_net(u1, "2") == ["SENSE"] and pad_net(u1, "3") == ["SENSE"]
    assert pad_net(u1, "4") == ["unconnected-(U1-PA3-Pad4)"]
    assert "unconnected-(U1-PA1-Pad2)" not in text(again)
    assert not [i for i in again.issues if i.code == "layout.net-removed"]
    same = rebuild(blink_unmarked(), text(first))
    assert same.files["blink.kicad_pcb"] == first.files["blink.kicad_pcb"]
    assert not [i for i in same.issues if i.code.startswith("layout.") and i.severity != "info"]


# -- the stand-in for "Update PCB from Schematic"


def test_stand_in_is_a_no_op_on_paths_and_fields() -> None:
    output = build(blink(), 10)
    board, sheet = text(output), text(output, "blink.kicad_sch")
    updated = update_from_schematic(board, sheet)
    before, after = parse(board).nodes("footprint"), parse(updated).nodes("footprint")
    assert len(before) == len(after) == 3
    for old, new in zip(before, after, strict=True):
        added = [c for c in new.nodes() if c.name in ("sheetname", "sheetfile")]
        assert [(c.name, c.atoms()[0].value) for c in added] == [
            ("sheetname", "/"),
            ("sheetfile", "blink.kicad_sch"),
        ]
        assert [c for c in new.children if c not in added] == list(old.children)
    assert update_from_schematic(updated, sheet) == updated


def test_stand_in_rewrites_what_differs() -> None:
    skipped = text(build(blink(), 10, schematic="skip"))
    sheet = text(build(blink(), 10), "blink.kicad_sch")
    updated = update_from_schematic(skipped.replace('"Value" "330"', '"Value" "999"'), sheet)
    assert '"Value" "330"' in updated and '"Value" "999"' not in updated
    assert updated.count("(path ") == 3 and updated.count('(sheetfile "blink.kicad_sch")') == 3


@pytest.mark.parametrize("target", [9, 10])
def test_rebuild_after_the_stand_in(target: int) -> None:
    first = build(blink(), target)
    routed = edit_blink(text(first))
    updated = update_from_schematic(routed, text(first, "blink.kicad_sch"))
    again = rebuild(blink(), updated, target)
    assert again.summary["preserved"]["kept"] == ["D1", "R1", "U1"]  # type: ignore[index]
    codes = {i.code for i in again.issues}
    assert not codes & {"layout.orphan", "layout.footprint-replaced", "layout.net-removed"}
    board = text(again)
    for uuid in EDIT_UUIDS:
        assert uuid in board
    assert board.count('(sheetname "/")') == 3 and board.count('(sheetfile "blink.kicad_sch")') == 3
    assert board.count("(path ") == 3 and board.count('"fenolite.path"') == 3
    assert again.files["blink.kicad_sch"] == first.files["blink.kicad_sch"]
    design = read_board(board)
    assert len([n for n in design.circuit.nets if n.name.startswith(UNCONNECTED)]) == 29
    assert rebuild(blink(), board, target).files["blink.kicad_pcb"] == again.files["blink.kicad_pcb"]


# -- a symbol in a child sheet (c0070)


@pytest.mark.parametrize("target", [9, 10])
def test_path_of_a_symbol_in_a_child_sheet(target: int) -> None:
    output = built_nested(target)
    generated = output.schematic
    assert generated is not None
    (power,) = [box for box in generated.sheet.sheets if box.name == "power"]
    (ldo,) = generated.children["sheets/power.kicad_sch"].sheets
    (c1,) = generated.children["sheets/power.ldo.kicad_sch"].symbols
    item = footprint(output, "C1", "nested.kicad_pcb")
    assert item.find("path").atoms()[0].value == (  # type: ignore[union-attr]
        f"/{kicad_uuid(power)}/{kicad_uuid(ldo)}/{kicad_uuid(c1)}"
    )
    u1 = footprint(output, "U1", "nested.kicad_pcb")
    (symbol,) = [s for s in generated.sheet.symbols if s.ref == "U1"]
    assert u1.find("path").atoms()[0].value == f"/{kicad_uuid(symbol)}"  # type: ignore[union-attr]
    lowered = lower_for_schematic(output.design, generated)
    assert lower_for_schematic(lowered, generated) == lowered


def test_stacked_open_pins_share_one_net_on_the_board() -> None:
    """Capability kicad-schematic, "Pins with several pads on a generated sheet", scenario "Open pin with
    three pads" (change c0123): the pads of an open pin are one net, named as KiCad names it."""
    for target in (9, 10):
        output = built_stacked(target)
        assert not [i for i in output.issues if i.severity == "error"]
        board = read_board(output.files["stacked.kicad_pcb"].decode("utf-8"), file="stacked.kicad_pcb")
        names = {net.id: net.name for net in board.circuit.nets}
        refs = {c.id: c.ref for c in board.circuit.components}
        assert board.board is not None
        pads = {
            (refs[fp.component_id], pad.number): names.get(pad.net_id or "", "")
            for fp in board.board.footprints
            for pad in fp.pads
        }
        assert pads[("U1", "5")] == pads[("U1", "15")] == pads[("U1", "9")] == "unconnected-(U1-Pad15)"
        assert pads[("D2", "21")] == pads[("D2", "17")] == "Net-(D2-K-Pad17)"
        assert pads[("U1", "3")] == pads[("U1", "23")] == pads[("R1", "1")] == pads[("R1", "2")] == "OUT"
        assert pads[("U1", "7")] == pads[("U1", "27")] == "GND" and pads[("U1", "24")] == "VCC"
        assert pads[("U1", "1")] == "unconnected-(U1-Pad1)" and pads[("U1", "30")] == ""
        # one net per name: the pads of one pin do not make two nets of one name
        assert len([n for n in board.circuit.nets if n.name == "unconnected-(U1-Pad15)"]) == 1
        # the stored model holds none of these nets, and a second build is the first
        assert output.layout is not None
        assert not [n for n in output.layout.circuit.nets if n.name.startswith(("unconnected-(", "Net-("))]
        assert built_stacked(target).files == output.files
