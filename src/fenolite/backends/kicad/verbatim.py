# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Verbatim items of a script (change c0277, decision 11): KiCad text a build writes as given.

``check`` parses each ``VerbatimItem`` of a board and reports what the build refuses: text that is not one
list (``build.verbatim-invalid``), a head the DSL expresses or the file's header owns (``-head``), a layer
the board does not hold (``-layer``) and a net the design does not hold (``-net``); every item gives one
``build.verbatim-item`` (info). ``node`` gives the list the writer writes: every ``uuid`` child takes
``embed.placement_uuid(<key>, "/verbatim/<n>")``, so two builds agree and two items never share a uuid,
and a net named in it is written in the net form of the target. Atoms elsewhere (the ``members`` of a
``generated`` item, which name tracks by uuid) are written as they are.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Collection, Mapping, Sequence

from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, parse
from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import FENOLITE_NS
from fenolite.model.board import Board, VerbatimItem

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-VERBATIM",))
"""``INFERRED`` until ``H-K-VERBATIM`` loads, checks and re-saves a board with verbatim items on both
majors."""

ISSUE_CODES: Mapping[str, Severity] = {
    "build.verbatim-item": "info",
    "build.verbatim-invalid": "error",
    "build.verbatim-head": "error",
    "build.verbatim-layer": "error",
    "build.verbatim-net": "error",
}
"""The codes of verbatim items (design decision 11)."""
ROOT_REFUSED: frozenset[str] = frozenset(
    {
        "version", "generator", "generator_version", "general", "paper", "layers", "setup", "net",
        "title_block", "footprint", "segment", "arc", "via", "zone", "gr_line", "gr_arc", "gr_circle",
        "gr_rect", "gr_poly", "gr_text", "dimension", "group",
    }
)  # fmt: skip
"""Root heads a board item may not take: the header's, and those a DSL call says."""
FOOTPRINT_REFUSED: frozenset[str] = frozenset({"pad", "property", "at", "layer", "uuid", "attr", "path"})
"""Footprint children a part's item may not take: the instance's own, and its pads and fields."""
RULE_HEADS: frozenset[str] = frozenset({"rule"})
"""The one head an item of the rules file takes."""
_WILDCARD = re.compile(r"^(?:\*|F&B)\.[A-Za-z]+$")
"""A layer wildcard KiCad writes in ``layers`` (``*.Cu``, ``*.Mask``, ``F&B.Cu``)."""


def uuid_of(key: str, locator: str) -> str:
    """``embed.placement_uuid(key, locator)``: the uuid of the node at ``locator`` of the item ``key`` (the
    writer cannot import ``embed``, which imports it)."""
    return str(uuid.uuid5(FENOLITE_NS, f"kicad-place:{key}:{locator}"))


def uuid_nodes(tree: Node) -> list[Node]:
    """Every ``uuid`` node of ``tree``, in document order."""
    return [found for found in _walk(tree) if found.name == "uuid"]


def _issue(code: str, message: str, where: str, hint: str = "") -> Issue:
    return Issue(code, ISSUE_CODES[code], message, where=where, hint=hint)


def parsed(item: VerbatimItem) -> Node | None:
    """The one list ``item.text`` holds; ``None`` when it does not parse or holds something else."""
    try:
        found = parse(item.text)
    except FormatError:
        return None
    return found if found.name else None


def _refused(item: VerbatimItem) -> frozenset[str]:
    if item.target == "footprint":
        return FOOTPRINT_REFUSED
    return frozenset() if item.target == "kicad_dru" else ROOT_REFUSED


def _walk(tree: Node) -> list[Node]:
    found = [tree]
    for child in tree.nodes():
        found += _walk(child)
    return found


def check(board: Board, nets: Collection[str]) -> list[Issue]:
    """The issues of the verbatim items of ``board``, whose layer table names the layers, ``nets`` the net
    names of the design."""
    layers = {layer.name for layer in board.layers}
    issues: list[Issue] = []
    for item in board.verbatim:
        tree = parsed(item)
        where = item.key
        if tree is None:
            message = f"{item.key}: the text is not one KiCad list"
            issues.append(_issue("build.verbatim-invalid", message, where, "write one list: (barcode ...)"))
            continue
        if item.target == "kicad_dru" and tree.name not in RULE_HEADS:
            issues.append(_issue("build.verbatim-head", f"{item.key}: a rules item is a (rule ...), not "
                                 f"({tree.name} ...)", where))  # fmt: skip
            continue
        if tree.name in _refused(item):
            issues.append(
                _issue(
                    "build.verbatim-head",
                    f"{item.key}: ({tree.name} ...) is written by Fenolite itself",
                    where,
                    "use the DSL call that says it, or another head",
                )  # fmt: skip
            )
            continue
        bad = False
        for found in _walk(tree) if item.target != "kicad_dru" else ():
            if found.name in ("layer", "layers"):
                names = [a.value for a in found.atoms() if a.kind in (AtomKind.STRING, AtomKind.SYMBOL)]
                for name in names[:1] if found.name == "layer" else names:
                    if name not in layers and not _WILDCARD.fullmatch(name):
                        issues.append(_issue("build.verbatim-layer", f"{item.key}: layer {name!r} is not a "
                                             "layer of the board", where))  # fmt: skip
                        bad = True
            elif found.name == "net":
                atoms = found.atoms()
                if len(atoms) != 1 or atoms[0].kind != AtomKind.STRING or atoms[0].value not in nets:
                    shown = atoms[0].value if atoms else ""
                    message = f"{item.key}: net {shown!r} is not a net of the design"
                    issues.append(_issue("build.verbatim-net", message, where, 'name a net: (net "GND")'))
                    bad = True
        if not bad:
            issues.append(
                _issue("build.verbatim-item", f"{item.key}: ({tree.name} ...) is written as given", where)
            )
    return issues


def node(
    item: VerbatimItem, uuid_of: Callable[[str, str], str], net_node: Callable[[str], Node | None]
) -> Node:
    """The list of ``item`` the writer writes: each ``uuid`` child takes ``uuid_of(key, "/verbatim/<n>")``,
    n counting them in document order, and each ``(net "name")`` the node ``net_node(name)`` gives (the
    target's form). ``ValueError`` for an item ``check`` refuses."""
    tree = parsed(item)
    if tree is None:
        raise ValueError(f"verbatim item {item.key!r} does not parse")
    count = [0]

    def visit(current: Node) -> Node:
        if current.name == "uuid":
            n = count[0]
            count[0] += 1
            return current.with_children([Atom.string(uuid_of(item.key, f"/verbatim/{n}"))])
        if current.name == "net":
            atoms = current.atoms()
            if len(atoms) == 1 and atoms[0].kind == AtomKind.STRING:
                written = net_node(atoms[0].value)
                if written is not None:
                    return written
        children: list[Node | Atom] = [visit(c) if isinstance(c, Node) else c for c in current.children]
        return current.with_children(children)

    return visit(tree)


def with_rules(text: str, board: Board | None, target: int, *, allow_lossy: bool, issues: list[Issue]) -> str:
    """The rules file ``text`` with the ``kicad_dru`` items of ``board`` appended, one rule each (change
    c0277). A rule whose tokens KiCad ``target`` cannot read is dropped with ``rules.dropped-for-target``
    (warning) under ``allow_lossy`` and raises ``RulesLossError`` otherwise, as a preserved rule does."""
    from fenolite.backends.kicad.dru import DROPPED_CODE, RulesLossError, gate_rule

    found = of_target(board, "kicad_dru") if board is not None else ()
    if not found:
        return text
    lines = [text.rstrip("\n")]
    for item in found:
        rule = item.text.strip()
        droppable, errors, warnings = gate_rule(rule, target)
        issues.extend(warnings)
        if errors or (droppable and not allow_lossy):
            raise RulesLossError([*errors, *droppable], droppable=not errors)
        if droppable:
            message = f"verbatim rule {item.key!r} dropped: {droppable[0].message}"
            issues.append(Issue(DROPPED_CODE, "warning", message, where=item.key))
            continue
        lines.append(rule)
    return "\n".join(lines) + "\n"


def of_target(board: Board, target: str, component_id: str | None = None) -> Sequence[VerbatimItem]:
    """The verbatim items of ``board`` of ``target`` (and of the component, for ``footprint``)."""
    return [
        item
        for item in board.verbatim
        if item.target == target and (component_id is None or item.component_id == component_id)
    ]


__all__ = [
    "FOOTPRINT_REFUSED",
    "ISSUE_CODES",
    "ROOT_REFUSED",
    "check",
    "node",
    "of_target",
    "parsed",
    "uuid_nodes",
    "uuid_of",
    "with_rules",
]
