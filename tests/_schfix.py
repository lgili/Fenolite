# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored schematic fixtures and edits of their trees, for the schematic reader tests (c0060)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse, parse_fragment

SCHEMATICS = Path(__file__).resolve().parent / "data" / "kicad" / "schematic"
FIXTURES: tuple[str, ...] = (
    "flat.kicad_sch",
    "flat_v9.kicad_sch",
    "units.kicad_sch",
    "units_v9.kicad_sch",
    "hier/top.kicad_sch",
    "hier/child.kicad_sch",
    "hier_v9/top.kicad_sch",
    "hier_v9/child.kicad_sch",
    "multi/top.kicad_sch",
    "multi/cell.kicad_sch",
    "bus.kicad_sch",
)
Children = list[Node | Atom]


def text_of(name: str) -> str:
    return (SCHEMATICS / name).read_text(encoding="utf-8")


def tree_of(name: str) -> Node:
    return parse(text_of(name))


def fragment(text: str) -> Node:
    found = parse_fragment(text)
    assert isinstance(found, Node)
    return found


def reference(symbol: Node) -> str:
    """The text of the ``Reference`` property of a symbol node (``""`` without one)."""
    for prop in symbol.nodes("property"):
        atoms = prop.atoms()
        if len(atoms) >= 2 and atoms[0].value == "Reference":
            return atoms[1].value
    return ""


def edit_root(root: Node, change: Callable[[Children], None]) -> Node:
    children = list(root.children)
    change(children)
    return root.with_children(children)


def edit_symbol(root: Node, ref: str, change: Callable[[Children], None]) -> Node:
    """``root`` with the children of the symbol whose reference is ``ref`` changed in place."""
    done = False
    children: Children = []
    for child in root.children:
        if isinstance(child, Node) and child.name == "symbol" and reference(child) == ref and not done:
            child = edit_root(child, change)
            done = True
        children.append(child)
    assert done, f"no symbol {ref}"
    return root.with_children(children)


def set_child(children: Children, new: Node) -> None:
    """Replace the first child with the head of ``new``."""
    index = next(i for i, c in enumerate(children) if isinstance(c, Node) and c.name == new.name)
    children[index] = new


def with_version(root: Node, version: int) -> Node:
    return edit_root(root, lambda kids: set_child(kids, fragment(f"(version {version})")))


def heads(nodes: Sequence[Node | Atom]) -> list[str]:
    return [n.name if isinstance(n, Node) else n.text for n in nodes]


def text(root: Node) -> str:
    return dumps(root)
