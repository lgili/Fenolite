# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed grammar between the model's rules and KiCad custom rules, in both directions.

Facts and Fenolite choices: ``docs/formats/kicad/rules.md``. The rules reader (``dru``) and the
lowering (``lowering``) share these tables, so what one writes the other lifts back. A selector key is
written for a KiCad major only when ``SELECTOR_SUPPORT`` lists that major, which only a passing
``dru-cond-*`` probe adds (``H-K-DRU-COND``, ``H-K-DRU-GLOB``).
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.layers import is_canonical
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node
from fenolite.core.errors import Issue, Severity
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm, format_length, parse_length
from fenolite.model.base import Modeled, Slot
from fenolite.model.rules import Rule, RuleKind, RuleSeverity, Selector

KIND_MAP: Mapping[RuleKind, str] = MappingProxyType(
    {
        "clearance": "clearance",
        "edge_clearance": "edge_clearance",
        "track_width": "track_width",
        "via_diameter": "via_diameter",
        "hole_size": "hole_size",
        "via_drill": "hole_size",
    }
)
"""Model kind → written constraint type; ``via_drill`` adds the conjunct ``A.Type == 'Via'``."""
LIMITS: Mapping[RuleKind, frozenset[str]] = MappingProxyType(
    {
        "clearance": frozenset({"min"}),
        "edge_clearance": frozenset({"min"}),
        "track_width": frozenset({"min", "opt", "max"}),
        "via_diameter": frozenset({"min", "opt", "max"}),
        "hole_size": frozenset({"min", "max"}),
        "via_drill": frozenset({"min", "max"}),
    }
)
LIMIT_ORDER = ("min", "opt", "max")
ITEM_TYPES: Mapping[str, str] = MappingProxyType(
    {"track": "Track", "via": "Via", "pad": "Pad", "zone": "Zone"}
)
"""``item_kind`` values → KiCad ``Type`` names."""
SELECTOR_KEYS = (
    "net",
    "netclass",
    "ref",
    "item_kind",
    "and",
    "or",
    "not",
    "glob",
    "selector_b",
    "layer_clause",
)
_BOTH = frozenset({9, 10})
SELECTOR_SUPPORT: Mapping[str, frozenset[int]] = MappingProxyType({key: _BOTH for key in SELECTOR_KEYS})
"""Each key → the KiCad majors on which its ``dru-cond-<key>`` probe recorded ``present``
(``docs/evidence/kicad/probes/9.0.9.json`` and ``10.0.6.json``; every key holds on both majors)."""
RULE_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "rules.unsupported-selector": "error",
        "rules.unsupported-limit": "error",
        "rules.unsupported-layer": "error",
        "rules.dropped-for-target": "warning",
        "rules.kept-opaque": "info",
    }
)
VALUE_UNITS = ("mm", "mil", "in")
SEVERITIES: tuple[RuleSeverity, ...] = ("error", "warning", "ignore")
CLAUSE_FIELDS: Mapping[str, str] = MappingProxyType(
    {"constraint": "constraint", "condition": "condition", "layer": "layer", "severity": "severity"}
)
"""Clause heads of a lifted rule; with the positional ``name`` they are its clause slots."""
CLAUSE_ORDER = ("name", "layer", "condition", "constraint", "severity")
"""Where a clause the slots lack is inserted (the manuals' syntax summary; INFERRED, order has no meaning)."""

_VALUE = re.compile(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+))(mm|mil|in)$")
_LEAF_PROPS = {"net": "NetName", "netclass": "NetClass", "item_kind": "Type"}
_PROP_OPS = {prop: op for op, prop in _LEAF_PROPS.items()}
_TYPE_KINDS = {name: kind for kind, name in ITEM_TYPES.items()}
_FORBIDDEN = frozenset("'\"?[]")


def _issue(code: str, message: str, rule: Rule) -> Issue:
    return Issue(code, RULE_ISSUE_CODES[code], f"rule {rule.name!r}: {message}", where=rule.id)


# --- values and names -----------------------------------------------------------------------------


def parse_value(text: str) -> Nm:
    """A rule value in ``mm``, ``mil`` or ``in`` as exact nanometres; other units raise ``ValueError``."""
    match = _VALUE.fullmatch(text)
    if match is None:
        raise ValueError(f"value {text!r} is not a number in {', '.join(VALUE_UNITS)}")
    return parse_length(text)


def format_value(nm: Nm) -> str:
    """The shortest exact millimetre decimal, with the unit (``250000`` → ``0.25mm``)."""
    return format_length(nm, "mm")


def slug(text: str) -> str:
    """Lower case, each run outside ``[a-z0-9]`` replaced by ``_``, trimmed; ``rule`` when empty."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "rule"


# --- conditions: model → text ---------------------------------------------------------------------


def _supported(key: str, target: int) -> bool:
    return target in SELECTOR_SUPPORT.get(key, frozenset())


def _term(selector: Selector, side: str, target: int, rule: Rule, issues: list[Issue]) -> str:
    def refuse(message: str) -> str:
        issues.append(_issue("rules.unsupported-selector", message, rule))
        return ""

    op = selector.op
    if op in ("and", "or"):
        if not _supported(op, target):
            return refuse(f"'{op}' is not proved for KiCad {target}")
        parts = [_term(item, side, target, rule, issues) for item in selector.items]
        return "(" + (" && " if op == "and" else " || ").join(parts) + ")"
    if op == "not":
        if not _supported(op, target):
            return refuse(f"'not' is not proved for KiCad {target}")
        return f"!({_term(selector.items[0], side, target, rule, issues)})"
    if op == "all":
        return refuse("'all' is allowed only as a whole side")
    if op == "layer":
        return refuse("the 'layer' op is not lowered; use Rule.layers")
    value = selector.value
    if _FORBIDDEN & set(value):
        return refuse(f"value {value!r} contains one of ' \" ? [ ]")
    if not _supported(op, target):
        return refuse(f"'{op}' is not proved for KiCad {target}")
    if "*" in value and not _supported("glob", target):
        return refuse(f"the glob {value!r} is not proved for KiCad {target}")
    if op == "ref":
        return f"{side}.memberOfFootprint('{value}')"
    if op == "item_kind":
        if value not in ITEM_TYPES:
            return refuse(f"item kind {value!r} is not one of {', '.join(ITEM_TYPES)}")
        value = ITEM_TYPES[value]
    return f"{side}.{_LEAF_PROPS[op]} == '{value}'"


def condition_text(rule: Rule, *, target: int) -> tuple[str | None, tuple[Issue, ...]]:
    """The condition of ``rule`` for KiCad ``target`` (``None`` when both sides are ``all``)."""
    issues: list[Issue] = []
    terms: list[str] = []
    if rule.kind == "via_drill":
        terms.append(f"A.Type == '{ITEM_TYPES['via']}'")
    if rule.selector_a.op != "all":
        terms.append(_term(rule.selector_a, "A", target, rule, issues))
    b = rule.selector_b
    if b is not None and b.op != "all":
        if rule.kind != "clearance":
            issues.append(
                _issue("rules.unsupported-selector", "selector_b is allowed only for clearance", rule)
            )
        elif not _supported("selector_b", target):
            issues.append(
                _issue("rules.unsupported-selector", f"selector_b is not proved for KiCad {target}", rule)
            )
        else:
            terms.append(_term(b, "B", target, rule, issues))
    return (" && ".join(terms) if terms else None), tuple(issues)


# --- conditions: text → model ---------------------------------------------------------------------

_TOKEN = re.compile(
    r"\s*(?:(?P<op>&&|\|\||==|!|\(|\))|(?P<str>'[^']*')|(?P<leaf>[AB]\.[A-Za-z]+)|(?P<bad>\S))"
)


_Tree = tuple[str, object]
"""``("leaf", (side, selector))`` or ``(op, [trees])`` for ``and``, ``or`` and ``not``."""


class _Parse:
    """A recursive-descent reader of the closed expression grammar (rules.md, "Selectors")."""

    def __init__(self, text: str) -> None:
        self.tokens: list[tuple[str, str]] = []
        for match in _TOKEN.finditer(text):
            kind = match.lastgroup or "bad"
            self.tokens.append((kind, match.group(kind)))
        if "".join(m.group(0) for m in _TOKEN.finditer(text)).strip() != text.strip():
            self.tokens.append(("bad", ""))
        self.i = 0

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self, value: str | None = None, kind: str | None = None) -> str:
        token = self.peek()
        if (
            token is None
            or (value is not None and token[1] != value)
            or (kind is not None and token[0] != kind)
        ):
            raise ValueError("outside the closed grammar")
        self.i += 1
        return token[1]

    def expr(self) -> _Tree:
        return self.binary("||", "or", lambda: self.binary("&&", "and", self.unary))

    def binary(self, symbol: str, op: str, inner: Callable[[], _Tree]) -> _Tree:
        items = [inner()]
        while self.peek() == ("op", symbol):
            self.take(symbol)
            items.append(inner())
        return items[0] if len(items) == 1 else (op, items)

    def unary(self) -> _Tree:
        if self.peek() == ("op", "!"):
            self.take("!")
            if self.peek() != ("op", "("):
                raise ValueError("'!' must be followed by a parenthesised term")
            return ("not", [self.primary()])
        return self.primary()

    def primary(self) -> _Tree:
        if self.peek() == ("op", "("):
            self.take("(")
            found = self.expr()
            self.take(")")
            return found
        side, prop = self.take(kind="leaf").split(".", 1)
        if prop == "memberOfFootprint":
            self.take("(")
            value = self.take(kind="str")[1:-1]
            self.take(")")
            return ("leaf", (side, Selector("ref", value)))
        op = _PROP_OPS.get(prop)
        if op is None:
            raise ValueError(f"property {prop!r} is outside the closed grammar")
        self.take("==")
        value = self.take(kind="str")[1:-1]
        if op == "item_kind":
            if value not in _TYPE_KINDS:
                raise ValueError(f"type {value!r} is outside the closed grammar")
            value = _TYPE_KINDS[value]
        if not value:
            raise ValueError("empty value")
        return ("leaf", (side, Selector(op, value)))  # type: ignore[arg-type]


def _side(tree: _Tree) -> set[str]:
    op, payload = tree
    if op == "leaf":
        return {payload[0]}  # type: ignore[index]
    return set().union(*(_side(t) for t in payload))  # type: ignore[union-attr]


def _selector(tree: _Tree) -> Selector:
    op, payload = tree
    if op == "leaf":
        return payload[1]  # type: ignore[index,no-any-return]
    return Selector(op, items=tuple(_selector(t) for t in payload))  # type: ignore[arg-type,union-attr]


def _flatten(selector: Selector) -> Selector:
    """Nested ``and`` in ``and`` and ``or`` in ``or`` flattened, recursively."""
    if selector.op not in ("and", "or", "not"):
        return selector
    items: list[Selector] = []
    for item in (_flatten(i) for i in selector.items):
        if item.op == selector.op and selector.op != "not":
            items.extend(item.items)
        else:
            items.append(item)
    return dataclasses.replace(selector, items=tuple(items))


def _join(items: list[Selector]) -> Selector:
    if not items:
        return Selector("all")
    return _flatten(items[0] if len(items) == 1 else Selector("and", items=tuple(items)))


def parse_condition(text: str) -> tuple[Selector, Selector | None] | None:
    """``(selector_a, selector_b)`` of a condition in the closed grammar, or ``None``.

    The top-level conjuncts are split by side; each must use one side only.
    """
    parser = _Parse(text)
    try:
        tree = parser.expr()
        if parser.peek() is not None:
            return None
    except ValueError:
        return None
    conjuncts: list[_Tree] = tree[1] if tree[0] == "and" else [tree]  # type: ignore[assignment]
    sides: dict[str, list[Selector]] = {"A": [], "B": []}
    for conjunct in conjuncts:
        side = _side(conjunct)
        if len(side) != 1 or not side <= {"A", "B"}:
            return None
        sides[side.pop()].append(_selector(conjunct))
    return _join(sides["A"]), (_join(sides["B"]) if sides["B"] else None)


# --- rules: model ↔ nodes -------------------------------------------------------------------------


class _Clauses:
    """A ``slots.SlotSource`` over the clauses of one rule."""

    def __init__(self, items: Mapping[str, Sequence[Node | Atom]]) -> None:
        self._items = {k: tuple(v) for k, v in items.items() if v}

    def items(self, field: str) -> Sequence[Node | Atom]:
        return self._items.get(field, ())

    def fields(self) -> list[str]:
        return list(self._items)


def _node(head: str, *children: Node | Atom) -> Node:
    return Node(Atom.symbol(head), children)


def rule_nodes(
    rule: Rule, *, target: int, slots: Sequence[Slot] = ()
) -> tuple[tuple[Node, ...], tuple[Issue, ...]]:
    """The ``rule`` lists of ``rule`` for KiCad ``target``: one per layer, in the clause order of
    ``slots``; with errors, no node and every issue."""
    issues: list[Issue] = []
    constraint_type = KIND_MAP[rule.kind]
    limits = [(name, getattr(rule, name)) for name in LIMIT_ORDER if getattr(rule, name) is not None]
    if not limits:
        issues.append(_issue("rules.unsupported-limit", f"a {rule.kind} rule needs a limit", rule))
    for name, _ in limits:
        if name not in LIMITS[rule.kind]:
            issues.append(_issue("rules.unsupported-limit", f"{rule.kind} takes no '{name}' limit", rule))
    condition, found = condition_text(rule, target=target)
    issues += found
    for layer in rule.layers:
        if not is_canonical(layer):
            issues.append(
                _issue("rules.unsupported-layer", f"layer {layer!r} is not a KiCad layer name", rule)
            )
    if rule.layers and not _supported("layer_clause", target):
        issues.append(
            _issue("rules.unsupported-layer", f"layer clauses are not proved for KiCad {target}", rule)
        )
    if issues:
        return (), tuple(issues)
    constraint = _node(
        "constraint",
        Atom.symbol(constraint_type),
        *(_node(name, Atom.symbol(format_value(value))) for name, value in limits),
    )
    fields = {s.field for s in slots if isinstance(s, Modeled)}
    severity = not slots or "severity" in fields or rule.severity != "error"
    nodes: list[Node] = []
    for layer in rule.layers or (None,):
        name = rule.name if layer is None or len(rule.layers) == 1 else f"{rule.name}_{slug(layer)}"
        items: dict[str, list[Node | Atom]] = {
            "name": [Atom.string(name)],
            "layer": [] if layer is None else [_node("layer", Atom.string(layer))],
            "condition": [] if condition is None else [_node("condition", Atom.string(condition))],
            "constraint": [constraint],
            "severity": [_node("severity", Atom.symbol(rule.severity))] if severity else [],
        }
        nodes.append(slotlib.rebuild(Atom.symbol("rule"), slots, _Clauses(items), canonical=CLAUSE_ORDER))
    return tuple(nodes), ()


def _limit(node: Node) -> tuple[str, Nm] | str:
    atoms = node.atoms()
    if node.name not in LIMIT_ORDER or node.nodes() or len(atoms) != 1:
        return f"constraint child {node.name!r} is not a single min, opt or max value"
    try:
        return node.name, parse_value(atoms[0].text)
    except ValueError as exc:
        return str(exc)


def lift_rule(node: Node) -> Rule | str:
    """The model rule of a ``rule`` list in the closed grammar, or the reason it stays opaque."""
    if node.name != "rule":
        return f"top-level list {node.name!r} is not a rule"
    names = node.atoms()
    if len(names) != 1 or names[0].kind == AtomKind.NUMBER:
        return "the rule needs exactly one name"
    name = names[0].value
    clauses: dict[str, list[Node]] = {}
    for child in node.nodes():
        if child.name not in CLAUSE_FIELDS:
            return f"clause {child.name!r} is outside the closed grammar"
        clauses.setdefault(child.name, []).append(child)
    if len(clauses.get("constraint", [])) != 1:
        return "the rule needs exactly one constraint"
    if any(len(found) > 1 for found in clauses.values()):
        return "a clause appears twice"
    constraint = clauses["constraint"][0]
    types = constraint.atoms()
    kinds: list[RuleKind] = [
        k for k, written in KIND_MAP.items() if k != "via_drill" and types and written == types[0].value
    ]
    if len(types) != 1 or types[0].kind != AtomKind.SYMBOL or not kinds:
        return f"constraint {' '.join(a.text for a in types) or '()'} is not a lowered kind"
    kind: RuleKind = kinds[0]
    limits: dict[str, Nm] = {}
    for child in constraint.nodes():
        found = _limit(child)
        if isinstance(found, str):
            return found
        if found[0] in limits or found[0] not in LIMITS[kind]:
            return f"limit {found[0]!r} is not allowed for {kind}"
        limits[found[0]] = found[1]
    if not limits:
        return "the constraint has no limit"
    selector_a, selector_b = Selector("all"), None
    if "condition" in clauses:
        cond = clauses["condition"][0]
        texts = cond.atoms()
        if cond.nodes() or len(texts) != 1 or texts[0].kind != AtomKind.STRING:
            return "the condition is not one string"
        parsed = parse_condition(texts[0].value)
        if parsed is None:
            return "the condition is outside the closed grammar"
        selector_a, selector_b = parsed
        if selector_b is not None and kind != "clearance":
            return "a B side is lifted only for clearance"
    layers: tuple[str, ...] = ()
    if "layer" in clauses:
        atoms = clauses["layer"][0].atoms()
        if clauses["layer"][0].nodes() or len(atoms) != 1 or not is_canonical(atoms[0].value):
            return "the layer clause is not one KiCad layer name"
        layers = (atoms[0].value,)
    severity: RuleSeverity = "error"
    if "severity" in clauses:
        atoms = clauses["severity"][0].atoms()
        if len(atoms) != 1 or atoms[0].value not in SEVERITIES:
            return f"severity {' '.join(a.text for a in atoms)!r} is not error, warning or ignore"
        severity = atoms[0].value  # type: ignore[assignment]
    return Rule(
        id=derived_id("rul", "kicad", f"rule:{name}"),
        name=name,
        kind=kind,
        selector_a=selector_a,
        selector_b=selector_b,
        layers=layers,
        min=limits.get("min"),
        opt=limits.get("opt"),
        max=limits.get("max"),
        severity=severity,
    )


def normal_form(rule: Rule) -> Rule:
    """What lifting gives back: ``via_drill`` as ``hole_size`` on vias, flattened selectors, no
    ``all`` B side."""
    selector_a = _flatten(rule.selector_a)
    kind: RuleKind = rule.kind
    if kind == "via_drill":
        kind = "hole_size"
        via = Selector("item_kind", "via")
        selector_a = via if selector_a.op == "all" else _flatten(Selector("and", items=(via, selector_a)))
    selector_b = rule.selector_b
    if selector_b is not None:
        selector_b = None if selector_b.op == "all" else _flatten(selector_b)
    return dataclasses.replace(rule, kind=kind, selector_a=selector_a, selector_b=selector_b)


def rule_order(rules: Sequence[Rule]) -> tuple[Rule, ...]:
    """Priority 0 first, then descending priority (priority 1 last); ties by name, then id.

    The later rule governs in KiCad (``H-K-DRU-ORDER``), so priority 1 governs.
    """
    return tuple(sorted(rules, key=lambda r: (r.priority != 0, -r.priority, r.name, r.id)))


__all__ = [
    "CLAUSE_FIELDS",
    "CLAUSE_ORDER",
    "ITEM_TYPES",
    "KIND_MAP",
    "LIMITS",
    "LIMIT_ORDER",
    "RULE_ISSUE_CODES",
    "SELECTOR_KEYS",
    "SELECTOR_SUPPORT",
    "SEVERITIES",
    "VALUE_UNITS",
    "condition_text",
    "format_value",
    "lift_rule",
    "normal_form",
    "parse_condition",
    "parse_value",
    "rule_nodes",
    "rule_order",
    "slug",
]
