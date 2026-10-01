# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Round-trip properties of the S-expression layer (capability kicad-sexpr)."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given, settings
from strategies import atoms, kicad_strings, nested_nodes, sexpr_trees

from fenolite.backends.kicad import Atom, Node, dumps, parse, parse_fragment, tree_equal


@settings(max_examples=300)
@given(sexpr_trees())
def test_dumps_is_idempotent_and_round_trips(tree: Node) -> None:
    text = dumps(tree)
    again = parse(text)
    assert tree_equal(again, tree)
    assert dumps(again) == text


@settings(max_examples=300)
@given(sexpr_trees())
def test_compact_round_trip_drops_comments(tree: Node) -> None:
    assert tree_equal(parse(dumps(tree, style="compact")), replace(tree, comments=()))


@settings(max_examples=300)
@given(nested_nodes)
def test_fragment_codec_for_nodes(node: Node) -> None:
    assert tree_equal(parse_fragment(dumps(node, style="compact")), node)  # type: ignore[arg-type]


@given(atoms)
def test_fragment_codec_for_atoms(atom: Atom) -> None:
    assert parse_fragment(dumps(atom, style="compact")) == atom


@settings(max_examples=500)
@given(kicad_strings(max_size=40))
def test_string_encode_decode_identity(value: str) -> None:
    atom = Atom.string(value)
    assert atom.value == value
    assert not any(ord(c) < 0x20 and c != "\t" for c in atom.text)
    assert Atom(atom.text, atom.kind) == atom
