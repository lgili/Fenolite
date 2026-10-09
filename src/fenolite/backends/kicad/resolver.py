# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The capability resolver of the KiCad downgrade (change c0162; capability kicad-version-gating,
"Downgrade resolver", "Downgrade edits" and "Downgrade consent").

A downgrade writes a file that KiCad 10 saved for KiCad 9. The table ``data/downgrade.toml`` says, for
each construct of 10 that 9 cannot read (a token row of ``tokens.toml``, a form row, a project key), what
the downgrade does: ``rewrite`` it in 9's form, drop it because 9 behaves the same (``same``), drop it and
report the loss of a drawing or of metadata (``presentation``), or drop it and report a loss of the design
(``design``), which needs consent. ``resolve`` edits a tree at the node each ``kicad.token.too-new``
issue of ``check_emittable`` locates, inside opaque content too, and never at a node that only holds the
construct. Facts and their sources: ``docs/formats/kicad/versions.md`` ("Downgrade") and the column
``downgrade`` of ``docs/formats/kicad/tokens.md``.
"""

from __future__ import annotations

import tomllib
from collections import Counter
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from importlib import resources
from types import MappingProxyType
from typing import Any, Literal, cast

from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node
from fenolite.backends.kicad.versions import (
    TARGET_MAJORS,
    FileKind,
    LossyWriteError,
    check_emittable,
    load_inventory,
)
from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-DOWN-ROWS", "H-K-DOWN-DEMOS"))
"""The table's actions: ``INFERRED`` until each row's bench passes on 9.0.9 and 10.0.6 (``H-K-DOWN-ROWS``)
and the demo projects of format 10 load in 9.0.9 (``H-K-DOWN-DEMOS``)."""

Action = Literal["rewrite", "same", "presentation", "design"]
ACTIONS: tuple[Action, ...] = ("rewrite", "same", "presentation", "design")
CHANGED: frozenset[Action] = frozenset({"rewrite", "same"})
"""The actions reported as a change: the target holds the construct, or behaves as the source."""
PROJECT_PREFIX = "project:"
PROJECT_VERSION_ROW = "project:/net_settings/meta/version"
"""The row of the project's net settings version, which no key path of ``pro.TEN_ONLY_PATHS`` names."""
NET_FORM_ROW = "net-by-name"
TOO_NEW = "kicad.token.too-new"
CHANGED_CODE = "kicad.downgrade.changed"
LOST_CODE = "kicad.downgrade.lost"
DESIGN_CODE = "kicad.downgrade.design-loss"
DEFECT_CODE = "kicad.downgrade.unresolved"
ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {CHANGED_CODE: "info", LOST_CODE: "warning", DESIGN_CODE: "error", DEFECT_CODE: "error"}
)
TABLE_FILE = "fenolite/backends/kicad/data/downgrade.toml"
_ROW_KEYS = {"id", "target", "action", "when", "else", "form", "sources", "note"}
_REASONS: Mapping[Action, str] = MappingProxyType(
    {
        "rewrite": "written in the form of KiCad {target}.0",
        "same": "dropped: KiCad {target}.0 behaves the same without it",
        "presentation": "dropped: a drawing, a text or metadata changes",
        "design": "dropped: what is made or checked changes",
    }
)


@dataclass(frozen=True, slots=True)
class Row:
    """One row of the table: the construct ``id``, the ``target`` major, the ``action``, the values ``when``
    for which it holds (``None``: every value), the action ``otherwise`` (the table's ``else``) for the
    other values and for a rewrite the target cannot hold, the target's ``form``, the sources and a note."""

    id: str
    target: int
    action: Action
    when: tuple[str, ...] | None = None
    otherwise: Action | None = None
    form: str = ""
    sources: tuple[str, ...] = ()
    note: str = ""

    def decide(self, values: Collection[str]) -> Action:
        """The action for a construct holding ``values`` (its symbol values and those of its children)."""
        if self.when is None or set(values) <= set(self.when):
            return self.action
        return self.otherwise or "design"

    @property
    def loss(self) -> Literal["refuse", "report"] | None:
        """The loss class of the row in a conversion report: ``refuse`` when it can be a ``design`` edit,
        ``report`` when it can only be a ``presentation`` one, ``None`` when it is never a loss."""
        actions = {self.action, *((self.otherwise,) if self.otherwise else ())}
        if "design" in actions:
            return "refuse"
        return "report" if "presentation" in actions else None


@dataclass(frozen=True, slots=True)
class Table:
    """The rows by id."""

    rows: Mapping[str, Row]

    def row(self, row_id: str) -> Row:
        return self.rows[row_id]


def required_ids(target: int) -> frozenset[str]:
    """The ids the table must hold for ``target``: each token and form row of the inventory newer than
    ``target``, each key path of ``pro.TEN_ONLY_PATHS`` for a target older than 10, and the project's net
    settings version."""
    inventory = load_inventory()
    ids = {row.id for row in inventory.tokens if row.since_major > target}
    ids |= {row.id for row in inventory.forms if row.since_major > target}
    if target < 10:
        from fenolite.backends.kicad.pro import TEN_ONLY_PATHS  # noqa: PLC0415  (pro imports the writers)

        ids |= {PROJECT_PREFIX + path for path in TEN_ONLY_PATHS}
        ids.add(PROJECT_VERSION_ROW)
    return frozenset(ids)


def _fail(message: str, file: str) -> FormatError:
    return FormatError(message, file=file)


def _action(raw: Any, label: str, file: str) -> Action:
    if raw not in ACTIONS:
        raise _fail(f"{label}: action {raw!r} is not one of {', '.join(ACTIONS)}", file)
    return raw


def parse_table(text: str, *, file: str = TABLE_FILE) -> Table:
    """The table in ``text``, checked against the inventory and the project key paths (closure): a
    missing row, an unknown or repeated id, an unknown key or action, and a ``rewrite`` without ``form``,
    sources or rewriter raise ``FormatError`` naming the row."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise _fail(f"invalid TOML: {exc}", file) from exc
    if set(data) - {"format", "row"} or data.get("format") != 1:
        raise _fail("the table holds format = 1 and [[row]] entries only", file)
    rows: dict[str, Row] = {}
    for entry in cast(list[dict[str, Any]], data.get("row", [])):
        ident = str(entry.get("id", "?"))
        label = f"row {ident}"
        unknown = sorted(set(entry) - _ROW_KEYS)
        if unknown:
            raise _fail(f"{label}: unknown key(s) {', '.join(unknown)}", file)
        target = entry.get("target")
        if target not in TARGET_MAJORS or target == max(TARGET_MAJORS):
            raise _fail(f"{label}: target {target!r} is not a target older than another", file)
        if ident in rows:
            raise _fail(f"{label}: duplicate id", file)
        when = entry.get("when")
        if when is not None and (not isinstance(when, list) or not when):
            raise _fail(f"{label}: when must be a non-empty list of values", file)
        otherwise = entry.get("else")
        row = Row(
            ident,
            int(target),
            _action(entry.get("action"), label, file),
            tuple(str(v) for v in cast(list[Any], when)) if when is not None else None,
            _action(otherwise, label, file) if otherwise is not None else None,
            str(entry.get("form", "")),
            tuple(str(s) for s in cast(list[Any], entry.get("sources", []))),
            str(entry.get("note", "")),
        )
        if when is not None and row.otherwise is None:
            raise _fail(f"{label}: when needs an else action", file)
        if row.action == "rewrite":
            if not row.form or not row.sources:
                raise _fail(f"{label}: a rewrite needs its form and its sources", file)
            if not ident.startswith(PROJECT_PREFIX) and ident != NET_FORM_ROW and ident not in REWRITERS:
                raise _fail(f"{label}: no rewriter is registered for this rewrite", file)
        rows[ident] = row
    for target in sorted({row.target for row in rows.values()} or {min(TARGET_MAJORS)}):
        expected = required_ids(target)
        held = {ident for ident, row in rows.items() if row.target == target}
        missing = sorted(expected - held)
        if missing:
            raise _fail(f"no resolver row for {', '.join(missing)} (target {target})", file)
        extra = sorted(held - expected)
        if extra:
            raise _fail(f"unknown resolver id(s) {', '.join(extra)} (target {target})", file)
    return Table(MappingProxyType(rows))


@cache
def load() -> Table:
    """The packaged table (cached), checked by ``parse_table``."""
    text = (
        resources.files("fenolite.backends.kicad").joinpath("data/downgrade.toml").read_text(encoding="utf-8")
    )
    return parse_table(text)


# --- rewriters ------------------------------------------------------------------------------------------

SAME = object()
"""What a rewriter returns for a construct that the target holds by its absence: the node is dropped as
``same``."""
Rewriter = Callable[[Node, tuple[str, ...]], "Node | object | None"]
"""A rewriter gets the node and the head chain of its parent; it returns the node in the target's form,
``SAME``, or ``None`` when the target cannot hold the construct (the row's ``else`` action)."""


def _node(head: str, *children: Node | Atom) -> Node:
    return Node(Atom.symbol(head), tuple(children))


def _symbols(node: Node) -> list[str]:
    found: list[str] = []
    for child in node.children:
        if isinstance(child, Atom):
            if child.kind == AtomKind.SYMBOL:
                found.append(child.text)
        else:
            found += _symbols(child)
    return found


def _tenting(node: Node, chain: tuple[str, ...]) -> Node | object | None:
    """``(tenting (front V) (back V))`` in 9's form ``(tenting <sides>)``. In ``setup`` the named sides are
    tented and the others not (``(tenting none)`` for neither); for a via or a pad 10.0.6 reads the named
    sides as ``yes`` and the others as ``none``, so ``no`` cannot be written there, and both sides ``none``
    is the absence of the node (task 1.2)."""
    sides: dict[str, str] = {}
    for child in node.nodes():
        atoms = child.atoms()
        if child.name not in ("front", "back") or len(atoms) != 1 or child.nodes():
            return None
        sides[child.name] = atoms[0].text
    values = set(sides.values())
    named = [Atom.symbol(side) for side in ("front", "back") if sides.get(side) == "yes"]
    if chain and chain[-1] == "setup":
        if not values <= {"yes", "no"}:
            return None
        return _node("tenting", *(named or [Atom.symbol("none")]))
    if not values <= {"yes", "none"}:
        return None
    return _node("tenting", *named) if named else SAME


def _bare(node: Node, chain: tuple[str, ...]) -> Node | object | None:
    """``(head value)`` without its value: ``(island yes)`` as ``(island)``, ``(power global)`` as
    ``(power)``."""
    del chain
    return node.with_children(())


def _renamed(head: str) -> Rewriter:
    def rewrite(node: Node, chain: tuple[str, ...]) -> Node | object | None:
        del chain
        return Node(Atom.symbol(head), node.children, node.offset, node.comments)

    return rewrite


def _blind(node: Node, chain: tuple[str, ...]) -> Node | object | None:
    """``(via buried …)`` as ``(via blind …)``: 9.0 has one type for blind and buried vias."""
    del chain
    return node.with_children(
        Atom.symbol("blind")
        if isinstance(c, Atom) and c.kind == AtomKind.SYMBOL and c.text == "buried"
        else c
        for c in node.children
    )


REWRITERS: Mapping[str, Rewriter] = MappingProxyType(
    {
        "tenting-front": _tenting,
        "tenting-back": _tenting,
        "island-yes": _bare,
        "sch-lib-power-global": _bare,
        "sym-power-global": _bare,
        "sch-symbol-body-style": _renamed("convert"),
        "via-buried": _blind,
    }
)
"""The rewriter of each token row whose action is ``rewrite``."""
PARENT_SCOPE: frozenset[str] = frozenset({"tenting-front", "tenting-back"})
"""Rows whose construct is the parent of the node the issue locates: ``front`` and ``back`` of one
``tenting``."""


# --- resolving ------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Edit:
    """One construct resolved: its row, the action taken, its locator in the tree and, set by the caller,
    the file."""

    row: str
    action: Action
    where: str
    file: str = ""


@dataclass(frozen=True, slots=True)
class Resolution:
    """The resolved tree and its edits, in document order."""

    root: Node
    edits: tuple[Edit, ...] = ()

    @property
    def counts(self) -> Counter[tuple[str, Action]]:
        return Counter((edit.row, edit.action) for edit in self.edits)


def row_id(issue: Issue) -> str:
    """The inventory row an emit-check issue names in its hint (``row <id> (sources)``)."""
    return issue.hint.split(" ", 2)[1] if issue.hint.startswith("row ") else ""


def _parent(locator: str) -> str:
    return locator.rsplit("/", 1)[0]


def _children(loc: str, node: Node) -> Iterable[tuple[str, Node | Atom]]:
    seen: Counter[str] = Counter()
    for child in node.children:
        if isinstance(child, Node):
            yield f"{loc}/{child.name}[{seen[child.name]}]", child
            seen[child.name] += 1
        else:
            yield "", child


def edit_issues(edits: Sequence[Edit], target: int) -> list[Issue]:
    """One ``kicad.downgrade.changed`` info or ``kicad.downgrade.lost`` warning per row and action, with the
    count of constructs and the first locator."""
    first: dict[tuple[str, Action], str] = {}
    counts: Counter[tuple[str, Action]] = Counter()
    for edit in edits:
        key = (edit.row, edit.action)
        counts[key] += 1
        first.setdefault(key, edit.where)
    found: list[Issue] = []
    for (row, action), count in counts.items():
        reason = _REASONS[action].format(target=target)
        changed = action in CHANGED
        found.append(
            Issue(
                CHANGED_CODE if changed else LOST_CODE,
                "info" if changed else "warning",
                f"{count} construct(s) of row {row} {reason}",
                where=first[(row, action)],
                hint=f"row {row} ({action})",
            )
        )
    return found


def resolve(
    root: Node, kind: FileKind, target: int, *, allow_lossy: bool = False, table: Table | None = None
) -> Resolution:
    """``root`` with each too-new construct for ``target`` resolved by its row, at the node its issue of
    ``check_emittable`` locates. ``LossyWriteError`` (droppable) lists the ``design`` edits unless
    ``allow_lossy``; a too-new issue without a row, or one that remains after the edits, raises
    ``LossyWriteError`` that is not droppable (``kicad.downgrade.unresolved``, a defect of the table)."""
    table = table if table is not None else load()
    planned: dict[str, list[tuple[Row, Issue]]] = {}
    defects: list[Issue] = []
    for issue in check_emittable(root, kind, target):
        if issue.code != TOO_NEW:
            continue
        ident = row_id(issue)
        row = table.rows.get(ident)
        if row is None or row.target != target:
            defects.append(
                Issue(DEFECT_CODE, "error", f"{issue.message}; no resolver row {ident!r}", where=issue.where)
            )
            continue
        node_at = _parent(issue.where) if ident in PARENT_SCOPE else issue.where
        planned.setdefault(node_at, []).append((row, issue))
    if defects:
        raise LossyWriteError(defects, droppable=False)
    edits: list[Edit] = []
    refused: list[Issue] = []

    def apply(node: Node, loc: str, chain: tuple[str, ...]) -> Node | None:
        found = planned[loc]
        row = found[0][0]
        replacement: Node | object | None = None
        action: Action = row.decide(_symbols(node))
        if action == "rewrite":
            replacement = REWRITERS[row.id](node, chain)
            if replacement is None:
                action = row.otherwise or "design"
            elif replacement is SAME:
                action = "same"
        for each, issue in found:
            edits.append(Edit(each.id, action, issue.where))
            if action == "design" and not allow_lossy:
                refused.append(
                    Issue(
                        DESIGN_CODE,
                        "error",
                        f"{issue.message}: dropping it changes the design (row {each.id})",
                        where=issue.where,
                        hint=f"row {each.id}",
                    )
                )
        if action == "rewrite":
            return cast(Node, replacement)
        return None

    def visit(node: Node, loc: str, chain: tuple[str, ...]) -> Node | None:
        inside = (*chain, node.name)
        children: list[Node | Atom] = []
        changed = False
        for child_loc, child in _children(loc, node):
            if not isinstance(child, Node):
                children.append(child)
                continue
            new = visit(child, child_loc, inside) if child_loc in prefixes else child
            changed = changed or new is not child
            if new is not None:
                children.append(new)
        current = node.with_children(children) if changed else node
        if loc in planned:
            return apply(current, loc, chain)
        return current

    prefixes = _prefixes(planned)
    new_root = visit(root, f"/{root.name}", ()) if planned else root
    assert new_root is not None
    if refused:
        raise LossyWriteError(refused, droppable=True)
    left = [i for i in check_emittable(new_root, kind, target) if i.code == TOO_NEW]
    if left:
        raise LossyWriteError(
            [Issue(DEFECT_CODE, "error", f"{i.message}; still present after the downgrade", where=i.where)
             for i in left],
            droppable=False,
        )  # fmt: skip
    edits.sort(key=lambda e: _order(e.where))
    return Resolution(new_root, tuple(edits))


def _prefixes(planned: Mapping[str, object]) -> frozenset[str]:
    found: set[str] = set()
    for loc in planned:
        parts = loc.split("/")
        found.update("/".join(parts[:k]) for k in range(2, len(parts) + 1))
    return frozenset(found)


def _order(locator: str) -> tuple[tuple[str, int], ...]:
    steps: list[tuple[str, int]] = []
    for part in locator.strip("/").split("/"):
        head, _, index = part.partition("[")
        steps.append((head, int(index.rstrip("]")) if index else 0))
    return tuple(steps)


def with_header(root: Node, version: int, target: int) -> Node:
    """``root`` with the header of a file Fenolite writes for ``target``: ``(version N)``, ``(generator
    "fenolite")`` and ``(generator_version "<target>.0")``, each replaced where the root holds it."""
    values = {
        "version": Atom.integer(version),
        "generator": Atom.string("fenolite"),
        "generator_version": Atom.string(f"{target}.0"),
    }
    return root.with_children(
        child.with_children((values[child.name],))
        if isinstance(child, Node) and child.name in values
        else child
        for child in root.children
    )


def downgraded(
    root: Node,
    kind: FileKind,
    version: int,
    target: int,
    *,
    allow_lossy: bool = False,
    edits: list[Edit] | None = None,
    issues: list[Issue] | None = None,
) -> Node:
    """A whole tree written for ``target`` by the resolver alone: the header of ``with_header``, every
    too-new construct resolved, and no error of ``check_emittable`` left (``LossyWriteError`` otherwise).
    The edits are appended to ``edits`` and their issues to ``issues`` when lists are given."""
    resolution = resolve(with_header(root, version, target), kind, target, allow_lossy=allow_lossy)
    left = [i for i in check_emittable(resolution.root, kind, target) if i.severity == "error"]
    if left:
        raise LossyWriteError(left, droppable=False)
    if edits is not None:
        edits.extend(resolution.edits)
    if issues is not None:
        issues.extend(edit_issues(resolution.edits, target))
    return resolution.root


def describe(row: Row) -> str:
    """The cell of the column ``downgrade`` of the token page: the action, its condition and the form."""
    text = row.action + (f" to `{row.form}`" if row.form else "")
    if row.when is not None:
        text += f" when {' or '.join(row.when)}, else {row.otherwise}"
    elif row.otherwise is not None:
        text += f", else {row.otherwise}"
    return text


__all__ = [
    "ACTIONS",
    "CHANGED",
    "CHANGED_CODE",
    "DESIGN_CODE",
    "EVIDENCE",
    "ISSUE_CODES",
    "LOST_CODE",
    "NET_FORM_ROW",
    "PROJECT_PREFIX",
    "PROJECT_VERSION_ROW",
    "REWRITERS",
    "Action",
    "Edit",
    "Resolution",
    "Row",
    "Table",
    "describe",
    "downgraded",
    "edit_issues",
    "load",
    "parse_table",
    "required_ids",
    "resolve",
    "row_id",
    "with_header",
]
