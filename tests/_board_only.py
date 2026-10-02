# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A footprint added "in KiCad" by token edit: ``Mini_R_0603`` without ``fenolite.path`` (change c0019)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from _layout_edit import add_items, net_ref

from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse

ROOT = Path(__file__).resolve().parents[1]


def add_h1(ref: str = "H1") -> Callable[[str], str]:
    def change(text: str) -> str:
        lib = (ROOT / "tests" / "data" / "libs" / "Mini_v9.pretty" / "Mini_R_0603.kicad_mod").read_text()
        node = parse(lib)
        kids = []
        for kid in node.children:
            if isinstance(kid, Node) and kid.name in ("version", "generator", "generator_version"):
                continue
            if isinstance(kid, Node) and kid.name == "property" and kid.atoms()[0].value == "Reference":
                kid = kid.with_children([*kid.children[:1], Atom.string(ref), *kid.children[2:]])  # type: ignore[list-item]
            if isinstance(kid, Node) and kid.name == "pad" and kid.atoms()[0].value == "1":
                kid = kid.with_children([*kid.children, parse(net_ref(text, "GND", pad=True))])
            kids.append(kid)
        kids.insert(1, parse('(uuid "00000000-0000-4000-8000-0000000000a1")'))
        kids.insert(2, parse("(at 140 125)"))
        footprint = node.with_children([Atom.string("Mini:Mini_R_0603"), *kids[1:]])  # type: ignore[list-item]
        return add_items(text, dumps(footprint, style="compact"))

    return change


__all__ = ["add_h1"]
