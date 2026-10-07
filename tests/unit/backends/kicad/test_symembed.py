# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Embedded symbols of a generated sheet and their project libraries (capability kicad-schematic,
"Embedded symbols of a generated sheet"; change c0061)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import BLINK_DIR, LIBS, resolver

from fenolite.backends.kicad import symembed
from fenolite.backends.kicad.sexpr import Node, dumps, parse, tree_equal
from fenolite.backends.kicad.sym import read_symbol_library, resolve_extends
from fenolite.backends.kicad.symembed import EmbeddedSymbol, embed_symbol, power_flag, variant_name
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind, LossyWriteError
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.library import SymbolDef, SymbolPin

PROJECT = LIBS / "project"
"""A project folder whose table names the 10.0 mini library, which holds a derived symbol."""


def embedded(
    lib_id: str,
    target: int = 10,
    *,
    project: Path = BLINK_DIR,
    pin_numbers: tuple[tuple[str, str], ...] | None = None,
    allow_lossy: bool = False,
    issues: list[Issue] | None = None,
) -> EmbeddedSymbol:
    chain = resolver(target, project).symbol_chain(lib_id)
    return embed_symbol(
        resolve_extends(chain)[0],
        parents=chain[1:],
        target=target,
        pin_numbers=pin_numbers,
        allow_lossy=allow_lossy,
        issues=issues,
    )


def subs(node: Node) -> list[str]:
    return [child.atoms()[0].value for child in node.nodes("symbol")]


def pins(node: Node) -> dict[str, str]:
    """Pin name → number of every pin of the embedded node."""
    return {
        pin.find("name").atoms()[0].value: pin.find("number").atoms()[0].value  # type: ignore[union-attr]
        for sub in node.nodes("symbol")
        for pin in sub.nodes("pin")
    }


def test_derived_symbol_is_flattened() -> None:
    found = embedded("Mini:Mini_LED_Red", project=PROJECT, allow_lossy=False)
    assert found.lib_id == "Mini:Mini_LED_Red" and found.node.atoms()[0].value == "Mini:Mini_LED_Red"
    assert subs(found.node) and all(name.startswith("Mini_LED_Red_") for name in subs(found.node))
    assert found.node.find("extends") is None
    values = {p.atoms()[0].value: p.atoms()[1].value for p in found.node.nodes("property")}
    assert values["Value"] == "Mini_LED_Red" and values["Footprint"] == "Mini:Mini_LED_THT_3mm"
    assert found.definition.name == "Mini_LED_Red" and len(found.definition.pins) == 2


def test_pin_pad_variant() -> None:
    mapping = (("1", "2"), ("2", "1"))
    plain = embedded("Mini:Mini_LED")
    variant = embedded("Mini:Mini_LED", pin_numbers=mapping)
    assert plain.lib_id == "Mini:Mini_LED"
    assert variant.name == variant_name("Mini_LED", mapping)
    assert variant.lib_id.startswith("Mini:Mini_LED_") and len(variant.name) == len("Mini_LED_") + 8
    assert int(variant.name[-8:], 16) >= 0
    assert pins(plain.node)["K"] == "1" and pins(variant.node)["K"] == "2"
    assert all(name.startswith(variant.name + "_") for name in subs(variant.node))
    assert variant_name("Mini_LED", (("2", "1"), ("1", "2"))) == variant.name  # the order does not count


def test_hidden_power_input_is_shown() -> None:
    issues: list[Issue] = []
    found = embedded("Mini:Mini_GND", 9, issues=issues)
    (pin,) = [p for sub in found.node.nodes("symbol") for p in sub.nodes("pin")]
    assert pin.atoms()[0].value == "power_in" and pin.find("hide") is None
    assert [(i.code, i.severity) for i in issues] == [("kicad.sch.power-pin-shown", "info")]
    assert not found.definition.pins[0].hidden


def test_library_equals_the_embedded_copy() -> None:
    names = ("Mini_LED", "Mini_QFP32_IC", "Mini_R")
    for target in (9, 10):
        found = [embedded(f"Mini:{name}", target) for name in names]
        text = symembed.write_symbol_library(list(reversed(found)), target=target)
        root = parse(text)
        assert root.find("version").atoms()[0].value == str(FORMAT_VERSIONS[FileKind.SYMBOL_LIB][target])  # type: ignore[union-attr]
        assert root.find("generator").atoms()[0].value == "fenolite"  # type: ignore[union-attr]
        written = root.nodes("symbol")
        assert [s.atoms()[0].value for s in written] == list(names)
        for item, copy in zip(written, found, strict=True):
            renamed = parse(dumps(item).replace(f'"{copy.name}"', f'"{copy.lib_id}"', 1))
            assert tree_equal(renamed, copy.node)
        back = {s.name: s for s in read_symbol_library(text, library="Mini")}
        for copy in found:
            assert back[copy.name].pins == copy.definition.pins
        assert text.endswith(")\n") and text == symembed.write_symbol_library(found, target=target)


@pytest.mark.parametrize("target", [9, 10])
def test_the_flag_is_authored(target: int) -> None:
    flag = power_flag(target)
    assert flag.lib_id == "fenolite:PWR_FLAG" and flag.nickname == symembed.FLAG_LIBRARY
    text = symembed.write_symbol_library([flag], target=target)
    (back,) = read_symbol_library(text, library="fenolite")
    assert back.power == "global" and back.reference == "#FLG"
    assert not back.in_bom and not back.on_board
    (pin,) = back.pins
    assert (pin.etype, pin.number, pin.position, pin.length) == ("power_out", "1", Point(0, 0), 0)
    assert "authored for Fenolite" in back.description
    assert "kicad" not in back.description.lower()


def test_a_token_too_new_for_the_target_is_refused_or_dropped() -> None:
    with pytest.raises(LossyWriteError) as error:
        embedded("Mini:Mini_R", 9, project=PROJECT)
    assert error.value.droppable and "in_pos_files" in str([i.message for i in error.value.issues])
    issues: list[Issue] = []
    found = embedded("Mini:Mini_R", 9, project=PROJECT, allow_lossy=True, issues=issues)
    assert "in_pos_files" not in dumps(found.node) and "duplicate_pin_numbers" not in dumps(found.node)
    assert issues and {i.code for i in issues} == {"kicad.sch.dropped-too-new"}
    assert all(i.severity == "warning" for i in issues)
    assert embedded("Mini:Mini_R", 10, project=PROJECT).node.find("in_pos_files") is not None


def test_a_tilde_of_an_older_library_stays_empty() -> None:
    """The 9.0 library writes an empty pin name as ``~``; a 10.0 sheet reads ``~`` as a tilde."""
    nine = embedded("Mini:Mini_GND", 9)
    ten = embedded("Mini:Mini_GND", 10)
    assert pins(nine.node) == {"~": "1"} and pins(ten.node) == {"": "1"}
    assert nine.definition.pins[0].name == ten.definition.pins[0].name == ""
    assert ten.definition.properties["Datasheet"] == ""


def test_an_authored_symbol_takes_the_node_of_the_symbol_writer() -> None:
    pin = SymbolPin("1", "A", "passive", Point(-2_540_000, 0), length=1_270_000)
    other = SymbolPin("2", "B", "passive", Point(2_540_000, 0), rotation=180_000_000, length=1_270_000)
    own = SymbolDef(
        id=derived_id("sym", "dsl", "Local:Two"),
        name="Two",
        library="Local",
        properties={"Reference": "J", "Value": "Two"},
        pins=(pin, other),
    )
    from fenolite.backends.kicad.sym import write_symbol_library

    for target in (9, 10):
        found = embed_symbol(own, target=target)
        assert found.authored is own and found.lib_id == "Local:Two"
        assert symembed.write_symbol_library([found], target=target) == write_symbol_library(
            [own], target=target
        )
        mapped = embed_symbol(own, target=target, pin_numbers=(("1", "9"),))
        assert mapped.authored is None and pins(mapped.node) == {"A": "9", "B": "2"}
        mixed = symembed.write_symbol_library([found, mapped], target=target)
        assert [s.atoms()[0].value for s in parse(mixed).nodes("symbol")] == ["Two", mapped.name]


def test_unknown_target() -> None:
    with pytest.raises(ValueError, match="unsupported target"):
        power_flag(8)


@pytest.mark.parametrize("target", [9, 10])
def test_stacked_pins_of_a_pin_with_several_pads(target: int) -> None:
    """Capability kicad-schematic, "Pins with several pads on a generated sheet", scenario "Thermal pad
    stacked" (change c0123)."""
    mapping = (("1", "1"), ("1", "T1"), ("1", "T2"))
    found = embedded("Mini:Mini_LED", target, pin_numbers=mapping)
    plain = embedded("Mini:Mini_LED", target)
    nodes = [pin for sub in found.node.nodes("symbol") for pin in sub.nodes("pin")]
    listed = [
        (
            pin.find("name").atoms()[0].value,  # type: ignore[union-attr]
            pin.find("number").atoms()[0].value,  # type: ignore[union-attr]
            pin.atoms()[0].value,
            pin.atoms()[1].value,
            pin.find("hide") is not None,
        )
        for pin in nodes
    ]
    assert listed == [
        ("K", "1", "passive", "line", False),
        ("K", "T1", symembed.STACKED_TYPE, "line", symembed.STACKED_HIDDEN),
        ("K", "T2", symembed.STACKED_TYPE, "line", symembed.STACKED_HIDDEN),
        ("A", "2", "passive", "line", False),
    ]
    # a stacked pin lies where its pin lies, with its length, directly after it
    first, second = nodes[0], nodes[1]
    assert dumps(first.find("at")) == dumps(second.find("at"))  # type: ignore[arg-type]
    assert dumps(first.find("length")) == dumps(second.find("length"))  # type: ignore[arg-type]
    assert second.find("alternate") is None
    # the other pin is as the library holds it
    other = [pin for sub in plain.node.nodes("symbol") for pin in sub.nodes("pin")][1]
    assert dumps(nodes[3]) == dumps(other)
    # the project library holds the same pins as the sheet
    text = symembed.write_symbol_library([found], target=target)
    (read,) = read_symbol_library(text, library="Mini")
    assert [(p.name, p.number, p.etype, p.hidden) for p in read.pins] == [
        (name, number, etype, hidden) for name, number, etype, _style, hidden in listed
    ]
    assert [(p.name, p.number) for p in found.definition.pins] == [(n, m) for n, m, *_ in listed]


def test_variant_name_of_one_pad_per_pin_is_unchanged() -> None:
    """Scenario "Variant name of one pad per pin is unchanged"."""
    assert variant_name("Mini_LED", (("2", "1"), ("1", "2"))) == "Mini_LED_b0bb1b70"
    assert variant_name("Mini_LED", (("1", "2"), ("2", "1"))) == "Mini_LED_b0bb1b70"
    # the pads of one pin count in their order: the first is the one the symbol shows
    one, other = (("1", "1"), ("1", "T1")), (("1", "T1"), ("1", "1"))
    assert variant_name("Mini_LED", one) != variant_name("Mini_LED", other)
    assert symembed.variant_pairs((("2", "9"), ("1", "T"), ("1", "1"))) == (
        ("1", "T"),
        ("1", "1"),
        ("2", "9"),
    )
    assert embedded("Mini:Mini_LED", pin_numbers=other).name == variant_name("Mini_LED", other)
    shown = {
        pin.find("number").atoms()[0].value  # type: ignore[union-attr]
        for sub in embedded("Mini:Mini_LED", pin_numbers=other).node.nodes("symbol")
        for pin in sub.nodes("pin")
        if pin.find("hide") is None
    }
    assert shown == {"T1", "2"}
