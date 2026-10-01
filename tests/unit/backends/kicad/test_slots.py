# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slot split and order-preserving rebuild (capability kicad-slots)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from strategies import nested_nodes

from fenolite.backends.kicad import Atom, Node, parse, tree_equal
from fenolite.backends.kicad.slots import opaque_child, rebuild, split
from fenolite.model.base import Modeled, Opaque

PAD = parse('(pad "1" smd rect (at 1 2) (frobnicate 3) (size 1 1))')
PAD_FIELDS = {"at": "position", "size": "size"}
PAD_POSITIONAL = ("number", "type", "shape")


class Original:
    """A source that returns the original children of each modelled field."""

    def __init__(self, node: Node, fields: dict[str, str], positional: Sequence[str] = ()) -> None:
        self.by_field: dict[str, list[Node | Atom]] = {}
        leading = 0
        seen_list = False
        for child in node.children:
            if isinstance(child, Node):
                seen_list = True
                if child.head.text in fields:
                    self.by_field.setdefault(fields[child.head.text], []).append(child)
            elif not seen_list and leading < len(positional):
                self.by_field.setdefault(positional[leading], []).append(child)
                leading += 1

    def items(self, field: str) -> Sequence[Node | Atom]:
        return self.by_field.get(field, [])

    def fields(self) -> Iterable[str]:
        return [f for f, items in self.by_field.items() if items]


class Fixed:
    def __init__(self, **items: list[Node | Atom]) -> None:
        self.by_field = items

    def items(self, field: str) -> Sequence[Node | Atom]:
        return self.by_field.get(field, [])

    def fields(self) -> Iterable[str]:
        return [f for f, items in self.by_field.items() if items]


def test_pad_with_an_unknown_child() -> None:
    slots = split(PAD, PAD_FIELDS, positional=PAD_POSITIONAL, min_version="20260206")
    assert slots == (
        Modeled("number"),
        Modeled("type"),
        Modeled("shape"),
        Modeled("position"),
        Opaque("(frobnicate 3)", "20260206"),
        Modeled("size"),
    )
    assert tree_equal(rebuild(PAD.head, slots, Original(PAD, PAD_FIELDS, PAD_POSITIONAL)), PAD)


def test_opaque_atom_after_the_positional_atoms() -> None:
    node = parse('(pad "1" smd rect locked (at 1 2))')
    slots = split(node, {"at": "position"}, positional=PAD_POSITIONAL)
    assert slots[3] == Opaque("locked", None)
    assert tree_equal(rebuild(node.head, slots, Original(node, {"at": "position"}, PAD_POSITIONAL)), node)


def test_opaque_atom_after_a_child_list() -> None:
    node = parse('(fp_text reference "R1" (at 0 0) hide (effects))')
    slots = split(node, {"at": "position"})
    assert slots == (
        Opaque("reference"),
        Opaque('"R1"'),
        Modeled("position"),
        Opaque("hide"),
        Opaque("(effects)"),
    )
    assert tree_equal(rebuild(node.head, slots, Original(node, {"at": "position"})), node)


def test_repeated_heads_produce_one_slot_each() -> None:
    node = parse('(footprint "x" (property "A" "1") (layer "F.Cu") (property "B" "2") (property "C" "3"))')
    slots = split(node, {"property": "properties"})
    assert [i for i, s in enumerate(slots) if s == Modeled("properties")] == [1, 3, 4]


def test_conservative_version() -> None:
    node = parse("(pad (frobnicate 1) (x 2) locked)")
    assert {s.min_version for s in split(node, {}, min_version="20241229") if isinstance(s, Opaque)} == {
        "20241229"
    }


def test_per_child_version() -> None:
    node = parse("(pad (padstack (mode front_inner_back)) (frobnicate 1))")
    calls: list[Node | Atom] = []

    def version(child: Node | Atom) -> str | None:
        calls.append(child)
        return "20240929" if isinstance(child, Node) and child.name == "padstack" else "20241229"

    slots = split(node, {}, min_version=version)
    assert slots == (
        Opaque("(padstack (mode front_inner_back))", "20240929"),
        Opaque("(frobnicate 1)", "20241229"),
    )
    assert len(calls) == 2


PROPS = parse('(fp (property "A") (x 1) (property "B"))')
A, X, B = PROPS.children
C = parse('(property "C")')


def test_deleted_item_leaves_neighbours_in_place() -> None:
    slots = split(PROPS, {"property": "properties"})
    rebuilt = rebuild(PROPS.head, slots, Fixed(properties=[A]))
    assert rebuilt.children == (A, X)


def test_added_item_follows_its_field() -> None:
    slots = split(PROPS, {"property": "properties"})
    rebuilt = rebuild(PROPS.head, slots, Fixed(properties=[A, B, C]))
    assert rebuilt.children == (A, X, B, C)


def test_new_field_in_canonical_position() -> None:
    node = parse("(pad 1 (at 1 2) (size 3 3))")
    slots = split(node, {"at": "position", "size": "size"}, positional=("number",))
    at, size = node.nodes()
    rotation = parse("(rotation 90)")
    source = Fixed(number=[node.atoms()[0]], position=[at], size=[size], rotation=[rotation])
    rebuilt = rebuild(node.head, slots, source, canonical=("position", "rotation", "size"))
    assert [c.name if isinstance(c, Node) else c.text for c in rebuilt.children] == [
        "1",
        "at",
        "rotation",
        "size",
    ]


def test_new_field_without_preceding_slot_goes_after_the_atoms() -> None:
    node = parse("(pad 1 locked (size 3 3))")
    slots = split(node, {"size": "size"}, positional=("number",))
    first = parse("(first 0)")
    source = Fixed(number=[node.atoms()[0]], size=[node.nodes()[0]], first=[first])
    rebuilt = rebuild(node.head, slots, source, canonical=("first", "size"))
    assert [c.text if isinstance(c, Atom) else c.name for c in rebuilt.children] == [
        "1",
        "locked",
        "first",
        "size",
    ]


def test_field_without_canonical_position() -> None:
    slots = split(PAD, PAD_FIELDS, positional=PAD_POSITIONAL)
    with pytest.raises(ValueError, match="colour"):
        rebuild(PAD.head, slots, Fixed(colour=[parse("(colour red)")]))


def test_opaque_child_decodes_fragments() -> None:
    assert opaque_child(Opaque("locked")) == Atom.symbol("locked")
    assert tree_equal(opaque_child(Opaque("(a (b 1))")), parse("(a (b 1))"))  # type: ignore[arg-type]


@settings(max_examples=200)
@given(nested_nodes, st.randoms(use_true_random=False))
def test_split_rebuild_identity(node: Node, rnd: object) -> None:
    import random

    assert isinstance(rnd, random.Random)
    heads = sorted({c.head.text for c in node.children if isinstance(c, Node)})
    chosen = [h for h in heads if rnd.random() < 0.5]
    fields = {h: f"f_{h}" for h in chosen}
    leading = 0
    for c in node.children:
        if isinstance(c, Node):
            break
        leading += 1
    positional = tuple(f"p{i}" for i in range(rnd.randint(0, leading)))
    slots = split(node, fields, positional=positional, min_version="20260206")
    assert tree_equal(rebuild(node.head, slots, Original(node, fields, positional)), node)
