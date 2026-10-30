# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``teardrops`` child of a pad and of a via (change c0277): ``Teardrop`` settings written for created
pads and vias, and read back by the board-to-code import, which interprets the child the reader keeps in
its slot (the reader itself does not project it).

Facts and Fenolite choices: ``docs/formats/kicad/board.md``, "Teardrop settings". The children and their
order are those of the pads and vias of the demo boards of 9.0.9 and 10.0.6 (S-0058); a ratio is a
fraction of the pad or via size, written as a decimal and held as parts per million.
"""

from __future__ import annotations

from collections.abc import Sequence

from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node
from fenolite.core.evidence import Evidence, Level
from fenolite.model.board import Teardrop

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-TEARDROP",))
"""The children and their order are corpus facts (S-0058); a created child stays ``INFERRED`` until
``H-K-TEARDROP`` loads, fills and re-saves one on both majors."""
HEAD = "teardrops"
CHILDREN: tuple[tuple[str, str, str], ...] = (
    ("best_length_ratio", "length_ratio", "ratio"),
    ("max_length", "max_length", "length"),
    ("best_width_ratio", "width_ratio", "ratio"),
    ("max_width", "max_width", "length"),
    ("curved_edges", "curved", "flag"),
    ("filter_ratio", "filter_ratio", "ratio"),
    ("enabled", "enabled", "flag"),
    ("allow_two_segments", "two_segments", "flag"),
    ("prefer_zone_connections", "prefer_zones", "flag"),
)
"""Each child of ``teardrops``: its head, the ``Teardrop`` field and the kind of its value, in the order
KiCad 9.0 and 10.0 write them (``board.md``, "Teardrop settings")."""


def _child(head: str, value: Atom) -> Node:
    return Node(Atom.symbol(head), (value,))


def _atom(kind: str, value: object) -> Atom:
    if kind == "flag":
        return Atom.symbol("yes" if value else "no")
    # a length in nanometres and a ratio in parts per million are both written with six decimals at most
    return Atom.from_nm(value)  # type: ignore[arg-type]


def emit(teardrop: Teardrop) -> Node:
    """The ``teardrops`` node of ``teardrop``: a child per field that is not ``None``, ``enabled`` always."""
    children: list[Node | Atom] = []
    for head, field, kind in CHILDREN:
        value = getattr(teardrop, field)
        if value is not None:
            children.append(_child(head, _atom(kind, value)))
    return Node(Atom.symbol(HEAD), tuple(children))


def _value(child: Node, kind: str) -> object:
    atoms = child.atoms()
    if child.nodes() or len(atoms) != 1:
        raise ValueError(f"({child.name} …) holds {len(atoms)} atoms")
    atom = atoms[0]
    if kind == "flag":
        if atom.kind != AtomKind.SYMBOL or atom.value not in ("yes", "no"):
            raise ValueError(f"({child.name} {atom.text}) is not yes or no")
        return atom.value == "yes"
    value = atom.to_nm()
    if value < 0:
        raise ValueError(f"({child.name} {atom.text}) is negative")
    return value


def project(node: Node) -> Teardrop | None:
    """The ``Teardrop`` of a ``teardrops`` node; ``None`` when it holds an unknown child, a child twice or a
    value the model cannot hold (the import then reports the item as unexpressed)."""
    if node.name != HEAD or node.atoms():
        return None
    known: dict[str, tuple[str, str]] = {head: (field, kind) for head, field, kind in CHILDREN}
    values: dict[str, object] = {}
    for child in node.nodes():
        found = known.get(child.name)
        if found is None or found[0] in values:
            return None
        try:
            values[found[0]] = _value(child, found[1])
        except ValueError:
            return None
    values.setdefault("enabled", True)
    try:
        return Teardrop(**values)  # type: ignore[arg-type]
    except TypeError:  # pragma: no cover - the keys are the fields of Teardrop
        return None


def find(children: Sequence[Node | Atom]) -> Node | None:
    """The ``teardrops`` node among ``children``, or ``None``."""
    return next((c for c in children if isinstance(c, Node) and c.name == HEAD), None)


__all__ = ["CHILDREN", "HEAD", "emit", "find", "project"]
