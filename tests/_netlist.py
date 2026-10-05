# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The components of a KiCad netlist (``sch export netlist --format kicadsexpr``), for tests.

Only ``components`` is read: one ``(ref, value, footprint)`` per ``comp``. Nothing of a netlist is stored;
the product netlist reader belongs to another change.
"""

from __future__ import annotations

from fenolite.backends.kicad.sexpr import Node, parse


def _text(node: Node, name: str) -> str:
    child = node.find(name)
    atoms = child.atoms() if child is not None else ()
    return atoms[0].value if atoms else ""


def components(text: str) -> set[tuple[str, str, str]]:
    """``(ref, value, footprint)`` of every ``comp`` of the netlist ``text``."""
    root = parse(text)
    if root.name != "export":
        raise ValueError(f"not a KiCad netlist: the root is {root.name!r}")
    listed = root.find("components")
    if listed is None:
        return set()
    return {(_text(c, "ref"), _text(c, "value"), _text(c, "footprint")) for c in listed.nodes("comp")}
