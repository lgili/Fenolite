# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rule records of an Altium document carried through KiCad (change c0434; capability
design-conversion, "Rule records through KiCad").

A conversion of an Altium document to KiCad writes, in the board property ``Fenolite.Altium.Rules6``
(``backends.kicad.boardcarrier``), every rule record of the document (its kind number and its keys from
``RULEKIND`` on, ``adapter.rules``'s ``kept_text`` form) with two SHA-256 keys of each rule list of the
``.kicad_dru`` that it gave (change c0457): its content and its shape (``rule_keys``). Both leave out the
rule's name, the order of its children and the spaces of its condition, so a rules file that a build of
the imported design writes again, with other names or in another order, still holds the record's rules.
A conversion of that board back to Altium (``match``) writes each record whose rules are all still in the
rules file, or that gave none, as it was read (name, priority, scopes, enabled state, limits). A record
whose rules keep their names and shapes but not their limits is written with KiCad's limits. The rules
of any other record are lowered as KiCad holds them. Version 0 of the property (change c0434) keyed each
rule list by its text, name included; it is still read, a rule then matching under its own name or under
the name the record gave.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from fenolite.backends.kicad.sexpr import Node

PROPERTY = "Fenolite.Altium.Rules6"
"""The board property that carries the records (``boardcarrier``)."""
SCHEMA = "fenolite.altium-rules.v1"
SCHEMAS = ("fenolite.altium-rules.v0", SCHEMA)
"""The versions ``read_carrier`` reads; version 0 keyed each rule list by its text (change c0434)."""
LIMITS = frozenset({"min", "opt", "max"})


@dataclass(frozen=True, slots=True)
class Carried:
    """One rule record of the source document: its kind number, its keys from ``RULEKIND`` on, and the
    rule lists it gave in the rules file (rule name → the SHA-256 of the list as Fenolite writes it,
    ``digest``)."""

    number: int
    fields: tuple[tuple[str, str], ...]
    blocks: Mapping[str, str]
    shapes: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    """Rule name → the shape key of the list (``rule_keys``); empty in version 0."""
    texts: bool = False
    """Version 0: ``blocks`` holds the ``digest`` of each list's text, its name included."""

    @property
    def name(self) -> str:
        return dict(self.fields).get("NAME", "")

    def kept(self, current: Mapping[str, str]) -> bool:
        """True when every rule list it gave is in ``current`` (rule name → its content key) under its own
        name; always, when it gave none."""
        return all(current.get(name) == text for name, text in self.blocks.items())


def digest(text: str) -> str:
    """The SHA-256 (hex) of a rule list's text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def carrier_text(records: Sequence[Carried]) -> str:
    """The JSON text the property packs: one object, keys sorted, one record per line."""
    rows = [
        json.dumps(
            {
                "number": r.number,
                "fields": [list(p) for p in r.fields],
                "blocks": dict(sorted(r.blocks.items())),
                "shapes": dict(sorted(r.shapes.items())),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        for r in records
    ]
    body = ",\n".join(f"  {row}" for row in rows)
    return f'{{"schema": "{SCHEMA}", "records": [\n{body}\n]}}\n'


def read_carrier(text: str) -> tuple[Carried, ...]:
    """The records of a carrier text; ``ValueError`` for another schema or a malformed record."""
    data = json.loads(text)
    schema = cast(dict[str, Any], data).get("schema") if isinstance(data, dict) else None
    if schema not in SCHEMAS:
        raise ValueError(f"not a {SCHEMA} file")
    texts = schema != SCHEMA
    found: list[Carried] = []
    try:
        for row in cast(list[dict[str, Any]], data["records"]):
            pairs = cast(list[list[Any]], row["fields"])
            fields = tuple((str(key), str(value)) for key, value in pairs)
            blocks = {str(name): str(body) for name, body in cast(dict[str, Any], row["blocks"]).items()}
            shapes = {str(k): str(v) for k, v in cast(dict[str, Any], row.get("shapes", {})).items()}
            found.append(Carried(int(row["number"]), fields, blocks, shapes, texts))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"a malformed {SCHEMA} record: {error}") from None
    return tuple(found)


@dataclass(frozen=True, slots=True)
class DruRule:
    """A rule of a rules file: its name, the node as parsed, and its content and shape keys."""

    name: str
    node: Node
    content: str
    shape: str

    def text_key(self, name: str) -> str:
        """The version-0 key of the rule under ``name``: the ``digest`` of its text with that name."""
        from fenolite.backends.kicad.dru import rule_text
        from fenolite.backends.kicad.sexpr import Atom, Node

        renamed = Node(self.node.head, (Atom.string(name), *self.node.children[1:]))
        return digest(rule_text(renamed))


_SPACES = re.compile(r"\s+")


def rule_keys(node: Node) -> tuple[str, str]:
    """The content key and the shape key of a rule list: the SHA-256 of its children after the name, each in
    compact form, in sorted order, a condition with its runs of spaces made one. The shape leaves out the
    values of the ``min``, ``opt`` and ``max`` of each constraint (change c0457)."""
    from fenolite.backends.kicad.sexpr import Atom, Node, dumps

    def item(child: Node | Atom, shape: bool) -> str:
        if not isinstance(child, Node):
            return dumps(child, style="compact")
        if child.name == "condition" and child.atoms():
            text = _SPACES.sub(" ", child.atoms()[0].value).strip()
            return dumps(Node(child.head, (Atom.string(text),)), style="compact")
        if shape and child.name == "constraint":
            kept = [
                c if not (isinstance(c, Node) and c.name in LIMITS) else Node(c.head) for c in child.children
            ]
            return dumps(Node(child.head, tuple(kept)), style="compact")
        return dumps(child, style="compact")

    rest = node.children[1:]
    content = "\n".join(sorted(item(c, False) for c in rest))
    shape = "\n".join(sorted(item(c, True) for c in rest))
    return digest(content), digest(shape)


def dru_rules(text: str | None) -> tuple[DruRule, ...]:
    """Every rule of a rules file, in order; none without a file or for a file that does not parse."""
    from fenolite.backends.kicad.dru import RuleItem, parse_rules
    from fenolite.core.errors import FormatError

    if not text:
        return ()
    try:
        document = parse_rules(text)
    except FormatError:
        return ()
    found: list[DruRule] = []
    for item in document.items:
        if not isinstance(item, RuleItem):
            continue
        atoms = item.node.atoms()
        if atoms:
            found.append(DruRule(str(atoms[0].value), item.node, *rule_keys(item.node)))
    return tuple(found)


def dru_blocks(text: str | None) -> dict[str, str]:
    """Rule name → its content key (``rule_keys``), for every rule of a rules file (the first of a name)."""
    found: dict[str, str] = {}
    for rule in dru_rules(text):
        found.setdefault(rule.name, rule.content)
    return found


def dru_shapes(text: str | None) -> dict[str, str]:
    """Rule name → its shape key (``rule_keys``), for every rule of a rules file (the first of a name)."""
    found: dict[str, str] = {}
    for rule in dru_rules(text):
        found.setdefault(rule.name, rule.shape)
    return found


@dataclass(frozen=True, slots=True)
class Matched:
    """What the rules file holds of the carried records (``match``): the records written as read, the
    records whose limits alone were edited with the names of their rules, the names of the rules those
    records stand for (not lowered again), and the names of the rules of every other record that are still
    in the file (edited in KiCad)."""

    kept: tuple[Carried, ...]
    limits: tuple[tuple[Carried, tuple[str, ...]], ...]
    taken: frozenset[str]
    edited: frozenset[str]


def match(records: Sequence[Carried], rules: Sequence[DruRule]) -> Matched:
    """The carried ``records`` against the rules of a rules file (change c0457).

    A record is kept when each of its rule lists is a distinct rule of the file of the same content, its own
    name first; the name, the order of the children and the spaces of a condition do not count. Version 0
    keys compare the text under the record's name. A rule of the same content as a kept record's rule is a
    copy of it and is taken too (an import may hold one rule as a board minimum and as a rule). A record not
    kept whose rule lists are rules of the file under their names, of the same shapes, has its limits edited.
    """
    free = list(range(len(rules)))
    used: dict[int, str] = {}

    def find(name: str, key: str, record: Carried) -> int | None:
        order = sorted(free, key=lambda i: rules[i].name != name)
        for i in order:
            rule = rules[i]
            if (rule.text_key(name) if record.texts else rule.content) == key:
                return i
        return None

    kept: list[Carried] = []
    rest: list[Carried] = []
    for record in records:
        chosen: list[int] = []
        for name, key in record.blocks.items():
            at = find(name, key, record)
            if at is None:
                break
            chosen.append(at)
            free.remove(at)
        if len(chosen) == len(record.blocks):
            kept.append(record)
            used.update({i: rules[i].content for i in chosen})
        else:
            free.extend(chosen)
            free.sort()
            rest.append(record)
    contents = set(used.values())
    taken = {rules[i].name for i in used} | {rules[i].name for i in free if rules[i].content in contents}
    free = [i for i in free if rules[i].content not in contents]
    limits: list[tuple[Carried, tuple[str, ...]]] = []
    edited: set[str] = set()
    for record in rest:
        by_name = {rules[i].name: i for i in reversed(free)}
        at = [by_name.get(name) for name in record.blocks]
        if (
            record.shapes
            and record.blocks
            and all(
                i is not None and rules[i].shape == record.shapes.get(n)
                for n, i in zip(record.blocks, at, strict=True)
            )
        ):
            for i in at:
                assert i is not None
                free.remove(i)
            limits.append((record, tuple(record.blocks)))
            continue
        edited |= {name for name in record.blocks if name in by_name}
    return Matched(tuple(kept), tuple(limits), frozenset(taken), frozenset(edited))


__all__ = [
    "LIMITS",
    "PROPERTY",
    "SCHEMA",
    "SCHEMAS",
    "Carried",
    "DruRule",
    "Matched",
    "carrier_text",
    "digest",
    "dru_blocks",
    "dru_rules",
    "dru_shapes",
    "match",
    "read_carrier",
    "rule_keys",
]
