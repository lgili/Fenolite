# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Tree passes of the board writer: net forms, the net table, rows a target no longer writes, and
the emit-check gate.

Facts and Fenolite choices: ``docs/formats/kicad/board.md`` ("The writer"). These passes see only
S-expression trees, so ``pcb`` (which builds the trees from the model) imports this module and never
the other way round. Every pass keeps the locators of the nodes it does not touch: it only adds,
removes or rewrites nodes headed ``net``, ``net_name`` or a row no longer written, and a locator
indexes a node among its siblings of the same head.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, dumps, walk
from fenolite.backends.kicad.versions import FileKind, check_emittable, load_inventory
from fenolite.core.errors import Issue

ROOT = "/kicad_pcb"
NET_REF_CODE = "kicad.board.opaque-net-ref"
OBSOLETE_CODE = "kicad.board.obsolete-dropped"
DROPPED_CODE = "kicad.board.dropped-too-new"
TOO_NEW = "kicad.token.too-new"
TABLE_ANCHORS = ("setup", "layers", "paper", "general", "generator_version", "generator", "version")
"""Root heads after which a net table goes when the tree holds none, nearest first."""


def _node(head: str, *children: Node | Atom) -> Node:
    return Node(Atom.symbol(head), children)


def _child_locators(loc: str, node: Node) -> list[tuple[str, Node | Atom]]:
    seen: Counter[str] = Counter()
    out: list[tuple[str, Node | Atom]] = []
    for child in node.children:
        if isinstance(child, Node):
            out.append((f"{loc}/{child.name}[{seen[child.name]}]", child))
            seen[child.name] += 1
        else:
            out.append(("", child))
    return out


# --- net forms ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class NetForms:
    """How net references are resolved and written for one target.

    ``source`` maps a number of the source table to the current name of that net; ``numbers`` maps a
    name to its number for target 9 (the model's nets in code-point order of their names, from 1).
    """

    target: int
    source: Mapping[int, str]
    numbers: Mapping[str, int]

    @classmethod
    def of(cls, target: int, source: Mapping[int, str], names: Collection[str]) -> NetForms:
        numbers = {name: i for i, name in enumerate(sorted(set(names)), start=1)}
        return cls(target, dict(source), numbers)

    def table(self) -> list[Node]:
        """The target-9 net table: ``(net 0 "")`` then one row per net."""
        rows = [_node("net", Atom.integer(0), Atom.string(""))]
        rows += [_node("net", Atom.integer(i), Atom.string(name)) for name, i in self.numbers.items()]
        return rows

    def resolve(self, node: Node) -> tuple[bool, str | None]:
        """``(understood, name)`` of a reference in any form; ``name`` is None for no net."""
        atoms = node.atoms()
        if node.nodes() or len(atoms) not in (1, 2):
            return False, None
        first = atoms[0]
        if first.kind == AtomKind.NUMBER:
            if len(atoms) == 2 and atoms[1].kind != AtomKind.STRING:
                return False, None
            try:
                number = first.to_int()
            except ValueError:
                return False, None
            if number == 0:
                return True, None
            name = self.source.get(number)
            return (name is not None), name
        if first.kind == AtomKind.STRING and len(atoms) == 1:
            return True, first.value or None
        return False, None

    def write(self, name: str | None, parent: str) -> tuple[Node | None, bool]:
        """``(node, known)``: the reference in the target's form (None removes it); ``known`` is false
        for a name that target 9 cannot number."""
        if self.target >= 10:
            return (None, True) if name is None else (_node("net", Atom.string(name)), True)
        if name is None:
            return _node("net", Atom.integer(0)), True
        number = self.numbers.get(name)
        if number is None:
            return None, False
        if parent == "pad":
            return _node("net", Atom.integer(number), Atom.string(name)), True
        return _node("net", Atom.integer(number)), True


def convert_nets(root: Node, forms: NetForms, errors: list[Issue]) -> Node:
    """Every ``net`` reference (the root's table rows excepted) in the target's form; for target 9 a
    zone also gets its ``net_name``. A reference that cannot be resolved gives ``opaque-net-ref``."""

    def visit(node: Node, loc: str) -> Node:
        children: list[Node | Atom] = []
        changed = False
        resolved: str | None = None
        net_at: int | None = None
        for child_loc, child in _child_locators(loc, node):
            if not isinstance(child, Node):
                children.append(child)
                continue
            if child.name == "net" and loc != ROOT:
                understood, name = forms.resolve(child)
                new: Node | None = child
                if not understood:
                    errors.append(_net_issue(child, child_loc, "matches no net reference form or table row"))
                else:
                    new, known = forms.write(name, node.name)
                    if not known:
                        why = f"names {name!r}, which is not a net of the design"
                        errors.append(_net_issue(child, child_loc, why))
                        new = child
                    elif net_at is None:
                        resolved, net_at = name, len(children)
                changed = changed or new is not child
                if new is not None:
                    children.append(new)
                continue
            new_child = visit(child, child_loc)
            changed = changed or new_child is not child
            children.append(new_child)
        if node.name == "zone" and forms.target < 10 and net_at is not None:
            children, named = _set_net_name(children, net_at, resolved or "")
            changed = changed or named
        return node.with_children(children) if changed else node

    return visit(root, ROOT)


def _net_issue(node: Node, loc: str, why: str) -> Issue:
    return Issue(NET_REF_CODE, "error", f"{dumps(node, style='compact')} {why}", where=loc)


def _set_net_name(children: list[Node | Atom], net_at: int, name: str) -> tuple[list[Node | Atom], bool]:
    """A zone's first ``net_name`` set to ``name``, or one inserted after its ``net``."""
    wanted = _node("net_name", Atom.string(name))
    for i, child in enumerate(children):
        if isinstance(child, Node) and child.name == "net_name":
            if child == wanted:
                return children, False
            return [*children[:i], wanted, *children[i + 1 :]], True
    return [*children[: net_at + 1], wanted, *children[net_at + 1 :]], True


def place_table(root: Node, rows: Sequence[Node]) -> Node:
    """The root with its ``net`` rows replaced by ``rows``, at the place of the first old row."""
    children = list(root.children)
    first = next((i for i, c in enumerate(children) if isinstance(c, Node) and c.name == "net"), None)
    kept = [c for c in children if not (isinstance(c, Node) and c.name == "net")]
    if first is None:
        index = len([c for c in kept if not isinstance(c, Node)])
        for head in TABLE_ANCHORS:
            found = [i for i, c in enumerate(kept) if isinstance(c, Node) and c.name == head]
            if found:
                index = found[-1] + 1
                break
    else:
        index = first
    return root.with_children([*kept[:index], *rows, *kept[index:]])


# --- rows a target no longer writes ---------------------------------------------------------------


def drop_obsolete(root: Node, target: int) -> tuple[Node, list[Issue]]:
    """The tree without the nodes of inventory rows whose ``until_major`` is older than ``target``,
    and one ``obsolete-dropped`` info per row id with the count of nodes removed."""
    inventory = load_inventory()
    counts: Counter[str] = Counter()
    first: dict[str, str] = {}
    paths: dict[str, str] = {}

    def visit(node: Node, loc: str, chain: tuple[str, ...]) -> Node:
        children: list[Node | Atom] = []
        changed = False
        for child_loc, child in _child_locators(loc, node):
            if not isinstance(child, Node):
                children.append(child)
                continue
            child_chain = (*chain, child.name)
            row = inventory.match(FileKind.BOARD, child_chain)
            if row is not None and row.until_major is not None and row.until_major < target:
                counts[row.id] += 1
                first.setdefault(row.id, child_loc)
                paths[row.id] = row.path
                changed = True
                continue
            new = visit(child, child_loc, child_chain)
            changed = changed or new is not child
            children.append(new)
        return node.with_children(children) if changed else node

    new_root = visit(root, ROOT, (root.name,))
    issues = [
        Issue(
            OBSOLETE_CODE,
            "info",
            f"{counts[row_id]} node(s) of '{paths[row_id]}' removed: KiCad {target}.0 no longer writes them",
            where=first[row_id],
            hint=f"row {row_id}",
        )
        for row_id in counts
    ]
    return new_root, issues


# --- the gate -------------------------------------------------------------------------------------


def opaque_locators(root: Node, ids: Collection[int]) -> set[str]:
    """The locators of the nodes whose identity is in ``ids`` (the opaque children a writer emitted)."""
    return {loc for loc, node in walk(root) if id(node) in ids}


def owner(locator: str, opaque: Collection[str]) -> str | None:
    """The innermost opaque locator that is ``locator`` or one of its ancestors."""
    best: str | None = None
    for candidate in opaque:
        if (locator == candidate or locator.startswith(candidate + "/")) and (
            best is None or len(candidate) > len(best)
        ):
            best = candidate
    return best


def gate(
    root: Node, target: int, opaque: Collection[str], kind: FileKind = FileKind.BOARD
) -> tuple[dict[str, list[Issue]], list[Issue], list[Issue]]:
    """Run ``check_emittable``: ``(droppable by opaque locator, other errors, warnings and infos)``.

    The footprint writer (``mod``) runs it with ``kind`` ``FOOTPRINT`` on a ``footprint`` root."""
    droppable: dict[str, list[Issue]] = {}
    errors: list[Issue] = []
    others: list[Issue] = []
    for issue in check_emittable(root, kind, target):
        if issue.severity != "error":
            others.append(issue)
            continue
        slot = owner(issue.where, opaque) if issue.code == TOO_NEW else None
        if slot is None:
            errors.append(issue)
        else:
            droppable.setdefault(slot, []).append(issue)
    return droppable, errors, others


def remove(root: Node, locators: Collection[str]) -> Node:
    """The tree without the nodes at ``locators``."""
    targets = set(locators)
    prefixes: set[str] = set()
    for loc in targets:
        parts = loc.split("/")
        prefixes.update("/".join(parts[:k]) for k in range(2, len(parts)))

    def visit(node: Node, loc: str) -> Node:
        if loc not in prefixes:
            return node
        children: list[Node | Atom] = []
        for child_loc, child in _child_locators(loc, node):
            if isinstance(child, Node):
                if child_loc in targets:
                    continue
                children.append(visit(child, child_loc))
            else:
                children.append(child)
        return node.with_children(children)

    return visit(root, f"/{root.name}")


def dropped(locator: str, node_head: str, issues: Sequence[Issue], code: str = DROPPED_CODE) -> Issue:
    """The ``dropped-too-new`` warning of one removed opaque slot (``code`` names the file kind)."""
    rows = sorted({i.hint.split(" ", 2)[1] for i in issues if i.hint.startswith("row ")})
    return Issue(
        code,
        "warning",
        f"removed '{node_head}': {issues[0].message}",
        where=locator,
        hint=f"row {', '.join(rows)}" if rows else issues[0].hint,
    )


def head_at(locator: str) -> str:
    """The head of the node at ``locator`` (its last step)."""
    return locator.rsplit("/", 1)[1].split("[", 1)[0]


__all__ = [
    "DROPPED_CODE",
    "NET_REF_CODE",
    "OBSOLETE_CODE",
    "ROOT",
    "NetForms",
    "convert_nets",
    "drop_obsolete",
    "dropped",
    "gate",
    "head_at",
    "opaque_locators",
    "owner",
    "place_table",
    "remove",
]
