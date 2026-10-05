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
