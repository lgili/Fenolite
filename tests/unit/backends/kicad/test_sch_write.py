# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Writing a created schematic sheet for a target (capability kicad-schematic, "Schematic writing per
target"; change c0061)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _buildhelp import LIBS, resolver
from _schfix import SCHEMATICS

from fenolite.backends.kicad import sch
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.backends.kicad.sym import read_symbol_library, resolve_extends
from fenolite.backends.kicad.symembed import embed_symbol
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.presentation import TitleBlock
from fenolite.model.schematic import (
    NetLabel,
    NoConnectFlag,
    SchematicSheet,
    SheetPage,
    SymbolInstance,
    SymbolUse,
)

MM = 1_000_000


def created(target: int = 10) -> SchematicSheet:
    """One instance of ``Mini:Mini_R``, one global label on its first pin and one flag on its second."""
    chain = resolver(target).symbol_chain("Mini:Mini_R")
    definition = embed_symbol(resolve_extends(chain)[0], parents=chain[1:], target=target).definition
    origin = Point(50_800_000, 50_800_000)
    root = SchematicSheet(id=derived_id("sch", "fenolite", "one"), name="one")
    symbol = SymbolInstance(
        id=derived_id("sci", "fenolite", "one:R1#1"),
        lib_ref="Mini:Mini_R",
        position=origin,
        ref="R1",
        value="330",
        footprint="Mini:Mini_R_0603",
        properties={
            "Value": "330",
            "Reference": "R1",
            "Footprint": "Mini:Mini_R_0603",
            "Datasheet": "",
            "Description": "",
            "fenolite.path": "R1",
            "MPN": "X-1",
        },
        uses=(SymbolUse("one", f"/{kicad_uuid(root)}", "R1", 1),),
    )
    label = NetLabel(
        id=derived_id("lbl", "fenolite", "one:label:R1:1"),
        kind="global",
        name="mod{slash}A",
        position=Point(origin.x, origin.y - 3_810_000),
        rotation=90_000_000,
        shape="passive",
    )
    flag = NoConnectFlag(
        id=derived_id("ncf", "fenolite", "one:nc:R1:2"), position=Point(origin.x, origin.y + 3_810_000)
    )
    return dataclasses.replace(
        root,
        title_block=TitleBlock(title="One", revision="A"),
        lib_symbols=(definition,),
        symbols=(symbol,),
        labels=(label,),
        no_connects=(flag,),
        pages=(SheetPage("/", "1"),),
    )


def first(node: Node, head: str) -> str:
    found = node.find(head)
    assert found is not None, head
    return found.atoms()[0].value


def properties(item: Node) -> dict[str, Node]:
    return {p.atoms()[0].value: p for p in item.nodes("property")}


def test_header_for_target_9() -> None:
    result = sch.write_schematic(created(9), target=9)
    root = parse(result.text)
    assert (first(root, "version"), first(root, "generator"), first(root, "generator_version")) == (
        "20250114",
        "fenolite",
        "9.0",
    )
    (symbol,) = root.nodes("symbol")
    assert symbol.find("body_style") is None and symbol.find("in_pos_files") is None
    last = root.nodes()[-1]
    assert (last.name, [a.value for a in last.atoms()]) == ("embedded_fonts", ["no"])
    hidden = properties(symbol)["Footprint"]
    assert hidden.find("hide") is None and hidden.find("effects").find("hide") is not None  # type: ignore[union-attr]
    assert hidden.find("show_name") is None
    (label,) = root.nodes("global_label")
    assert not label.nodes("property")
    assert result.issues == () and result.text.endswith(")\n")


def test_target_10_form() -> None:
    root = parse(sch.write_schematic(created(10), target=10).text)
    assert first(root, "version") == "20260306" and first(root, "generator_version") == "10.0"
    (symbol,) = root.nodes("symbol")
    assert first(symbol, "body_style") == "1" and first(symbol, "in_pos_files") == "yes"
    for prop in properties(symbol).values():
        assert first(prop, "show_name") == "no" and first(prop, "do_not_autoplace") == "no"
    hidden = properties(symbol)["Footprint"]
    assert first(hidden, "hide") == "yes" and hidden.find("effects").find("hide") is None  # type: ignore[union-attr]
    assert properties(symbol)["Reference"].find("hide") is None
    (label,) = root.nodes("global_label")
    assert list(properties(label)) == ["Intersheetrefs"]
    assert root.find("embedded_fonts") is None


@pytest.mark.parametrize("target", [9, 10])
def test_root_order_and_symbol_children(target: int) -> None:
    root = parse(sch.write_schematic(created(target), target=target).text)
    heads = [child.name for child in root.nodes()]
    body = [h for h in heads if h not in ("version", "generator", "generator_version", "embedded_fonts")]
    assert body == [
        "uuid", "paper", "title_block", "lib_symbols", "no_connect", "global_label", "symbol",
        "sheet_instances",
    ]  # fmt: skip
    (symbol,) = root.nodes("symbol")
    assert list(properties(symbol)) == [
        "Reference", "Value", "Footprint", "Datasheet", "Description", "MPN", "fenolite.path",
    ]  # fmt: skip
    assert [first(pin, "uuid") != "" and pin.atoms()[0].value for pin in symbol.nodes("pin")] == ["1", "2"]
    project = symbol.find("instances").find("project")  # type: ignore[union-attr]
    path = project.find("path")  # type: ignore[union-attr]
    assert project.atoms()[0].value == "one" and path.atoms()[0].value == f"/{first(root, 'uuid')}"  # type: ignore[union-attr]
    assert (first(path, "reference"), first(path, "unit")) == ("R1", "1")  # type: ignore[arg-type]
    for head in ("lib_id", "at", "unit", "exclude_from_sim", "in_bom", "on_board", "dnp", "uuid"):
        assert symbol.find(head) is not None, head


@pytest.mark.parametrize("target", [9, 10])
def test_read_back_equal(target: int) -> None:
    sheet = created(target)
    text = sch.write_schematic(sheet, target=target).text
    back = sch.read_schematic(text, file="one.kicad_sch")
    (symbol,), (wanted,) = back.symbols, sheet.symbols
    assert (symbol.position, symbol.ref, symbol.value, symbol.footprint, symbol.lib_ref) == (
        wanted.position,
        "R1",
        "330",
        "Mini:Mini_R_0603",
        "Mini:Mini_R",
    )
    assert symbol.properties == wanted.properties and symbol.uses == wanted.uses
    assert symbol.native_ids["kicad"] == kicad_uuid(wanted)
    (label,), (flag,) = back.labels, back.no_connects
    assert (label.kind, label.name, label.position, label.rotation, label.shape) == (
        "global",
        "mod{slash}A",
        sheet.labels[0].position,
        90_000_000,
        "passive",
    )
    assert flag.position == sheet.no_connects[0].position
    assert back.title_block == sheet.title_block and back.pages == sheet.pages
    assert sch.roundtrip_schematic(text).passed
    assert text == sch.write_schematic(sheet, target=target).text


def too_new() -> SchematicSheet:
    """The created sheet with its embedded symbol read from the 10.0 mini library."""
    sheet = created(10)
    definitions = {d.name: d for d in read_symbol_library(LIBS / "Mini.kicad_sym", library="Mini")}
    return dataclasses.replace(sheet, lib_symbols=(definitions["Mini_R"],))


def test_too_new_symbol_for_target_9() -> None:
    sheet = too_new()
    assert "in_pos_files" in sch.write_schematic(sheet, target=10).text
    with pytest.raises(LossyWriteError) as error:
        sch.write_schematic(sheet, target=9)
    assert error.value.droppable and "in_pos_files" in " ".join(i.message for i in error.value.issues)
    result = sch.write_schematic(sheet, target=9, allow_lossy=True)
    assert "in_pos_files" not in result.text and "duplicate_pin_numbers_are_jumpers" not in result.text
    assert {(i.code, i.severity) for i in result.issues} == {("kicad.sch.dropped-too-new", "warning")}
    assert sch.read_schematic(result.text).symbols[0].ref == "R1"


def test_read_sheet_refused() -> None:
    sheet = sch.read_schematic(SCHEMATICS / "flat.kicad_sch")
    with pytest.raises(ValueError, match="rebuild_schematic"):
        sch.write_schematic(sheet)


def test_unknown_target_and_missing_slots() -> None:
    with pytest.raises(ValueError, match="unsupported target"):
        sch.write_schematic(created(), target=8)
    bare = dataclasses.replace(created().lib_symbols[0], ext={})
    with pytest.raises(ValueError, match="embed_symbol"):
        sch.write_schematic(dataclasses.replace(created(), lib_symbols=(bare,)))


def test_mirror_rotation_and_dnp_are_written(tmp_path: Path) -> None:
    sheet = created(10)
    turned = dataclasses.replace(sheet.symbols[0], rotation=90_000_000, mirror="y", dnp=True, in_bom=False)
    text = sch.write_schematic(dataclasses.replace(sheet, symbols=(turned,)), target=10).text
    (symbol,) = sch.read_schematic(text).symbols
    assert (symbol.rotation, symbol.mirror, symbol.dnp, symbol.in_bom) == (90_000_000, "y", True, False)
