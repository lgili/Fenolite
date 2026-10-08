# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed table between the neutral rule kinds and Altium's rule kinds (capability altium-pcb-writer,
"Rule lowering table" and "Scoped rule records"; change c0084).

``TABLE`` holds one row per neutral rule kind: the Altium kind that carries it, or the reason it has no
counterpart (``docs/formats/altium/pcb-copper.md``, "Rule kinds lowered"). ``lower`` turns neutral rules
into rule records, exactly or not at all; ``lift`` reads records back through ``read.rules.map_rules``,
whose table (``RULE_KIND_MAP``) holds the same kinds and keys, so the writer and the reader cannot
disagree. A rule that is not written is named with one reason of ``NOT_LOWERED_REASONS``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, get_args

import fenolite.backends.altium.pcbrecords as rec
from fenolite.backends.altium.ascii import Field, text_problem
from fenolite.backends.altium.read.rul import RULE_FILE_COMMON, WRITTEN_END
from fenolite.backends.altium.read.rules import RULE_KIND_MAP, CopperLayers, map_rules
from fenolite.backends.altium.read.rules import Field as ReadField
from fenolite.backends.altium.read.scope import GLOB_CHARACTERS, parse_scope
from fenolite.core.evidence import Evidence, Level
from fenolite.model.rules import Rule, RuleKind, Selector

EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-RULE-CLEARANCE-CELLS",
        "H-A-RULE-CLEARANCE-FORMS",
        "H-A-RULE-FILE",
        "H-A-RULE-KINDS",
        "H-A-RULE-PRIORITY",
        "H-A-RULE-READBACK",
        "H-A-RULE-SCOPE",
    ),
)

Reason = Literal["no-counterpart", "scope-unsupported", "value-unsupported", "unit-loss"]
NOT_LOWERED_REASONS: tuple[Reason, ...] = get_args(Reason)
"""Why a rule is not written. ``unit-loss`` is kept for a field whose unit would move a value by more than
2 nm; no field of the table has such a unit today."""
EXACT = "exact"
ScopeForm = Literal["all", "net", "netclass", "and", "pair"]
ALL_SCOPE = "All"
TOLERANCE_NM = 2
"""The largest difference between a neutral value and the value read back: the PCB unit is 2.54 nm."""

_UNARY: tuple[ScopeForm, ...] = ("all", "net", "netclass", "and")
"""The scope forms of a rule with one scope."""


@dataclass(frozen=True, slots=True)
class RuleRow:
    """One row of ``TABLE``. ``status`` is ``exact`` or a reason of ``NOT_LOWERED_REASONS``; for an exact
    row ``altium`` is the ``RULEKIND`` text, ``number`` the kind number that opens the record, ``limits``
    the limits a neutral rule must give (all of them and no other), ``fields`` the constraint keys in
    written order, ``net_scope`` the ``NETSCOPE`` value and ``scopes`` the scope forms that are written."""

    neutral: RuleKind
    status: str
    altium: str = ""
    number: int = -1
    limits: tuple[str, ...] = ()
    fields: tuple[str, ...] = ()
    net_scope: str = "AnyNet"
    scopes: tuple[ScopeForm, ...] = _UNARY
    note: str = ""

    @property
    def exact(self) -> bool:
        return self.status == EXACT


_CLEARANCE_KEYS = ("GAP", "GENERICCLEARANCE", "IGNOREPADTOPADCLEARANCEINFOOTPRINT", "OBJECTCLEARANCES")
_VIA_KEYS = ("HOLEWIDTH", "WIDTH", "VIASTYLE", "MINHOLEWIDTH", "MINWIDTH", "MAXHOLEWIDTH", "MAXWIDTH")
_ALL_LIMITS = ("min", "opt", "max")
TABLE: tuple[RuleRow, ...] = (
    RuleRow(
        "clearance", EXACT, "Clearance", 0, ("min",), _CLEARANCE_KEYS, "DifferentNets", (*_UNARY, "pair")
    ),
    RuleRow("track_width", EXACT, "Width", 2, _ALL_LIMITS, ("MAXLIMIT", "MINLIMIT", "PREFEREDWIDTH")),
    RuleRow(
        "via_diameter",
        EXACT,
        "RoutingVias",
        11,
        _ALL_LIMITS,
        _VIA_KEYS,
        note="one record with the via_drill rule of the same selector",
    ),
    RuleRow(
        "via_drill",
        EXACT,
        "RoutingVias",
        11,
        _ALL_LIMITS,
        _VIA_KEYS,
        note="one record with the via_diameter rule of the same selector",
    ),
    RuleRow(
        "hole_size",
        EXACT,
        "HoleSize",
        42,
        ("min", "max"),
        ("ABSOLUTEVALUES", "MAXLIMIT", "MINLIMIT", "MAXPERCENT", "MINPERCENT"),
    ),
    RuleRow("edge_clearance", EXACT, "BoardOutlineClearance", 63, ("min",), _CLEARANCE_KEYS, "DifferentNets"),
    RuleRow("hole_to_hole", EXACT, "HoleToHoleClearance", 52, ("min",), ("GAP", "ALLOWSTACKEDMICROVIAS")),
    RuleRow(
        "hole_clearance",
        "no-counterpart",
        note="Altium holds the clearance of a hole only as a cell of the Clearance matrix, whose text "
        "no permitted source explains",
    ),
    RuleRow("annular_width", EXACT, "MinimumAnnularRing", 19, ("min",), ("MINIMUMRING",)),
    RuleRow(
        "courtyard_clearance",
        "no-counterpart",
        note="Component Clearance measures component bodies or selection areas, with a vertical clearance "
        "and a check mode; it is not a clearance between courtyards",
    ),
    RuleRow(
        "silk_clearance",
        "no-counterpart",
        note="Altium splits the constraint into Silk To Solder Mask Clearance and Silk To Silk Clearance, "
        "each narrower than the neutral rule",
    ),
    RuleRow(
        "creepage",
        "no-counterpart",
        note="Altium's Creepage Distance rule is in no public file, so its record is not known",
    ),
)
"""One row per kind of ``model.rules.RuleKind``, in the model's order (``pcb-copper.md``, "Rule kinds
lowered"; ``H-A-RULE-KINDS``)."""
KIND_ORDER: tuple[str, ...] = (
    "Clearance",
    "Width",
    "RoutingVias",
    "HoleSize",
    "BoardOutlineClearance",
    "HoleToHoleClearance",
    "MinimumAnnularRing",
)
"""The Altium kinds in the order their rules are written: the three kinds of change c0038 first."""
_ROWS: dict[str, RuleRow] = {row.neutral: row for row in TABLE}
_FIXED: dict[str, str] = {
    "IGNOREPADTOPADCLEARANCEINFOOTPRINT": "FALSE",
    "OBJECTCLEARANCES": "",
    "VIASTYLE": "Through Hole",
    "ABSOLUTEVALUES": "TRUE",
    "MAXPERCENT": "80.000",
    "MINPERCENT": "20.000",
    "ALLOWSTACKEDMICROVIAS": "FALSE",
}
"""Constraint keys with one written value (``pcb-copper.md``, "Rule kinds lowered")."""
_LENGTH_KEYS: dict[tuple[str, str], tuple[str, ...]] = {
    ("clearance", "min"): ("GAP", "GENERICCLEARANCE"),
    ("edge_clearance", "min"): ("GAP", "GENERICCLEARANCE"),
    ("track_width", "min"): ("MINLIMIT",),
    ("track_width", "opt"): ("PREFEREDWIDTH",),
    ("track_width", "max"): ("MAXLIMIT",),
    ("via_diameter", "min"): ("MINWIDTH",),
    ("via_diameter", "opt"): ("WIDTH",),
    ("via_diameter", "max"): ("MAXWIDTH",),
    ("via_drill", "min"): ("MINHOLEWIDTH",),
    ("via_drill", "opt"): ("HOLEWIDTH",),
    ("via_drill", "max"): ("MAXHOLEWIDTH",),
    ("hole_size", "min"): ("MINLIMIT",),
    ("hole_size", "max"): ("MAXLIMIT",),
    ("hole_to_hole", "min"): ("GAP",),
    ("annular_width", "min"): ("MINIMUMRING",),
}
"""(neutral kind, limit) → the keys that hold the limit."""
_VIA_PARTNER: dict[str, RuleKind] = {"via_diameter": "via_drill", "via_drill": "via_diameter"}


def row_of(kind: str) -> RuleRow:
    """The row of the neutral kind ``kind``; ``KeyError`` for a kind the model lacks."""
    return _ROWS[kind]


@dataclass(frozen=True, slots=True)
class LoweredRule:
    """One rule record: the kind number and ``RULEKIND`` text, the name, the ``NETSCOPE``, the two scope
    texts, the priority among the lowered rules of its kind (1 the highest), the constraint keys in
    written order, and the neutral rules it carries (two for a Routing Via Style)."""

    number: int
    kind: str
    name: str
    net_scope: str
    scope1: str
    scope2: str
    priority: int
    keys: tuple[Field, ...]
    rules: tuple[Rule, ...]

    def fields(self, *, unique_id: str = "", priority: int | None = None) -> tuple[Field, ...]:
        """The record's pairs from ``RULEKIND`` on (``read.rules.HEADER_KEYS``, then the constraint
        keys); the caller puts the common keys of its file form before them."""
        return (
            ("RULEKIND", self.kind),
            ("NETSCOPE", self.net_scope),
            ("LAYERKIND", "SameLayer"),
            ("SCOPE1EXPRESSION", self.scope1),
            ("SCOPE2EXPRESSION", self.scope2),
            ("NAME", self.name),
            ("ENABLED", "TRUE"),
            ("PRIORITY", str(self.priority if priority is None else priority)),
            ("COMMENT", ""),
            ("UNIQUEID", unique_id),
            ("DEFINEDBYLOGICALDOCUMENT", "FALSE"),
            *self.keys,
        )


@dataclass(frozen=True, slots=True)
class NotLowered:
    """A rule that is not written: the rule, its selector as text, one reason and a sentence."""

    rule: Rule
    selector: str
    reason: Reason
    detail: str

    @property
    def kind(self) -> RuleKind:
        return self.rule.kind


@dataclass(frozen=True, slots=True)
class Lowered:
    """The records of the rules that are written, grouped by Altium kind in ``KIND_ORDER`` and within a
    kind from the most governing rule to the least, and the rules that are not written, in rule order."""

    records: tuple[LoweredRule, ...]
    not_lowered: tuple[NotLowered, ...]

    @property
    def written(self) -> tuple[Rule, ...]:
        return tuple(rule for record in self.records for rule in record.rules)


class _Refused(Exception):
    def __init__(self, reason: Reason, detail: str) -> None:
        super().__init__(detail)
        self.reason: Reason = reason
        self.detail = detail


def selector_text(selector: Selector | None) -> str:
    """A selector as short text: ``all``, ``netclass PWR``, ``and(net A, netclass B)``."""
    if selector is None or selector.op == "all":
        return "all"
    if selector.items:
        return f"{selector.op}({', '.join(selector_text(item) for item in selector.items)})"
    return f"{selector.op} {selector.value}"


def rule_selector(rule: Rule) -> str:
    """The selector of ``rule`` as text: its first side, `` | `` and its second side when it has one, and
    its layers."""
    text = selector_text(rule.selector_a)
    if rule.selector_b is not None and rule.selector_b.op != "all":
        text += f" | {selector_text(rule.selector_b)}"
    if rule.layers:
        text += f" on {', '.join(rule.layers)}"
    return text


def _leaf(selector: Selector, row: RuleRow) -> tuple[str, str]:
    """The scope text and the name part of a ``net`` or ``netclass`` leaf."""
    if selector.op not in ("net", "netclass") or selector.op not in row.scopes:
        raise _Refused(
            "scope-unsupported",
            f"the selector {selector_text(selector)} is outside the scopes written for {row.altium} "
            "(all, a net, a net class, and the conjunction of those)",
        )
    value = selector.value
    problem = text_problem(value)
    if problem is None and "'" in value:
        problem = "holds an apostrophe, which the scope quotes"
    if problem is None and any(character in value for character in GLOB_CHARACTERS):
        problem = "holds a glob character; Altium's own wildcard rules are not stated"
    if problem is not None:
        raise _Refused("scope-unsupported", f"the value {value!r} of {selector.op} {problem}")
    if selector.op == "net":
        return f"InNet('{value}')", f"net_{value}"
    return f"InNetClass('{value}')", value


def scope_of(selector: Selector | None, row: RuleRow) -> tuple[str, str]:
    """The scope text of ``selector`` for a rule of ``row`` and the part of the rule name it gives
    (``""`` for all objects). Raises the refusal ``scope-unsupported`` outside the written forms; the text
    is one that ``read.scope.parse_scope`` turns back into ``selector``."""
    if selector is None or selector.op == "all":
        return ALL_SCOPE, ""
    if selector.op == "and":
        if "and" not in row.scopes:
            raise _Refused("scope-unsupported", f"{row.altium} takes no conjunction")
        parts = [_leaf(item, row) for item in selector.items]
        text = " And ".join(part for part, _name in parts)
        name = "_and_".join(name for _part, name in parts)
    else:
        text, name = _leaf(selector, row)
    if parse_scope(text) != selector:  # the reader's grammar is the judge of what is written
        raise _Refused("scope-unsupported", f"the scope {text} does not read back as the selector")
    return text, name


def _lengths(rule: Rule, row: RuleRow) -> dict[str, str]:
    """The length keys of ``rule`` as mil text. Refused: a severity other than ``error``, a limit the row
    does not take, a missing limit, and a positive value below the PCB unit or outside its range."""
    if rule.severity != "error":
        raise _Refused(
            "value-unsupported",
            f"the severity {rule.severity} has no place in a rule record (a rule is enabled or not)",
        )
    given = {"min": rule.min, "opt": rule.opt, "max": rule.max}
    extra = [name for name, value in given.items() if value is not None and name not in row.limits]
    if extra:
        raise _Refused("value-unsupported", f"{row.altium} holds no {', '.join(extra)}")
    missing = [name for name in row.limits if given[name] is None]
    if missing:
        raise _Refused(
            "value-unsupported",
            f"{row.altium} holds {', '.join(row.limits)} and the rule gives no {', '.join(missing)}",
        )
    found: dict[str, str] = {}
    for name in row.limits:
        value = given[name]
        assert value is not None
        try:
            units = rec.to_units(value)
        except ValueError as error:
            raise _Refused("value-unsupported", str(error)) from error
        if value < 0 or (value > 0 and units == 0):
            raise _Refused(
                "value-unsupported", f"{name} of {value} nm is below the PCB unit of 2.54 nm or negative"
            )
        for key in _LENGTH_KEYS[(rule.kind, name)]:
            found[key] = rec.mil_text(units)
    return found


@dataclass(frozen=True, slots=True)
class _Draft:
    row: RuleRow
    scope1: str
    scope2: str
    name: str
    lengths: dict[str, str]
    rules: tuple[Rule, ...]


def _draft(rule: Rule, row: RuleRow) -> _Draft:
    if rule.layers:
        raise _Refused(
            "scope-unsupported",
            f"the layers {', '.join(rule.layers)}: a layer condition is read from a PCB document "
            "with its board's layers and is not written",
        )
    scope1, name1 = scope_of(rule.selector_a, row)
    scope2, name2 = ALL_SCOPE, ""
    if rule.selector_b is not None and rule.selector_b.op != "all":
        if "pair" not in row.scopes:
            raise _Refused("scope-unsupported", f"{row.altium} takes no second selector")
        scope2, name2 = scope_of(rule.selector_b, row)
    parts = [row.altium, *([name1] if name1 else []), *(["to", name2] if name2 else [])]
    return _Draft(row, scope1, scope2, "_".join(parts), _lengths(rule, row), (rule,))


def governing_order(rules: Sequence[Rule]) -> tuple[Rule, ...]:
    """``rules`` from the most governing to the least: priority 1, 2, … and then priority 0 (unset); ties
    by falling name, then id. It is the reverse of the order in which the KiCad build writes its rules,
    where the last rule governs, so one script gives both targets the same precedence."""
    rising = sorted(rules, key=lambda r: (r.priority != 0, -r.priority, r.name, r.id))
    return tuple(reversed(rising))


def lower(rules: Sequence[Rule]) -> Lowered:
    """The rule records of ``rules`` and the rules that are not written, each with one reason.

    A rule is written only when its row is ``exact``, its selectors are scopes of the row, its severity is
    ``error`` and it gives exactly the limits of the row; nothing is approximated. A ``via_diameter`` and
    a ``via_drill`` rule of the same selector share one Routing Via Style record; either one alone is not
    written. Names come from the kind and the scope (``Width``, ``Width_PWR``, ``Clearance_net_A_to_B``);
    a repeated name gets ``_2``, ``_3``…"""
    refused: dict[str, NotLowered] = {}
    drafts: list[_Draft] = []
    waiting: dict[tuple[RuleKind, str], list[int]] = {}

    def refuse(rule: Rule, reason: Reason, detail: str) -> None:
        refused[rule.id] = NotLowered(rule, rule_selector(rule), reason, detail)

    for rule in governing_order(rules):
        row = _ROWS[rule.kind]
        if not row.exact:
            refuse(rule, "no-counterpart", row.note)
            continue
        try:
            draft = _draft(rule, row)
        except _Refused as refusal:
            refuse(rule, refusal.reason, refusal.detail)
            continue
        partner = _VIA_PARTNER.get(rule.kind)
        if partner is None:
            drafts.append(draft)
            continue
        queue = waiting.get((partner, draft.scope1))
        if not queue:
            waiting.setdefault((rule.kind, draft.scope1), []).append(len(drafts))
            drafts.append(draft)
            continue
        index = queue.pop(0)
        first = drafts[index]
        drafts[index] = _Draft(
            row, first.scope1, first.scope2, first.name, first.lengths | draft.lengths, (*first.rules, rule)
        )
    alone = {index for queue in waiting.values() for index in queue}
    for index in sorted(alone):
        rule = drafts[index].rules[0]
        refuse(
            rule,
            "value-unsupported",
            f"a Routing Via Style rule holds the diameter and the hole; no {_VIA_PARTNER[rule.kind]} rule "
            "has the same selector",
        )
    kept = [draft for index, draft in enumerate(drafts) if index not in alone]
    records: list[LoweredRule] = []
    used: set[str] = set()
    for kind in KIND_ORDER:
        of_kind = [draft for draft in kept if draft.row.altium == kind]
        for priority, draft in enumerate(of_kind, start=1):
            name, count = draft.name, 1
            while name in used:
                count += 1
                name = f"{draft.name}_{count}"
            used.add(name)
            keys = tuple((key, draft.lengths.get(key, _FIXED.get(key, ""))) for key in draft.row.fields)
            ordered = tuple(sorted(draft.rules, key=lambda r: r.kind))
            records.append(
                LoweredRule(
                    draft.row.number,
                    kind,
                    name,
                    draft.row.net_scope,
                    draft.scope1,
                    draft.scope2,
                    priority,
                    keys,
                    ordered,
                )
            )
    return Lowered(tuple(records), tuple(refused[rule.id] for rule in rules if rule.id in refused))


def lift(
    records: Sequence[LoweredRule | Sequence[ReadField]],
    *,
    origin: str = "rules",
    layers: CopperLayers | None = None,
) -> tuple[tuple[Rule, ...], dict[str, int]]:
    """The neutral rules of ``records`` (lowered rules or field lists) that an ``exact`` row describes, in
    record order, and the number of the other records by Altium kind. The reading is
    ``read.rules.map_rules``: a record of a kind of the table that it refuses (a matrix of differing
    clearances, a scope outside the grammar) is counted too. ``layers`` are the copper layers of the board
    the records belong to; without them a layer condition is refused. The forms of change c0125 (a uniform
    matrix, the keys of a matrix cell, a layer condition) and the cell rules of change c0130 are read and
    never written: ``lower`` writes one form per rule and an empty matrix."""
    lists = [record.fields() if isinstance(record, LoweredRule) else tuple(record) for record in records]
    mapping = map_rules(lists, origin=origin, layers=layers)
    opaque = Counter(unmapped.kind or "(none)" for unmapped in mapping.unmapped)
    return mapping.ruleset.rules, dict(sorted(opaque.items()))


def same_rule(first: Rule, second: Rule, *, tolerance: int = TOLERANCE_NM) -> bool:
    """Whether two rules hold the same kind, selectors and limits, each limit within ``tolerance`` nm. A
    second selector ``all`` equals none; names, ids and priority numbers are not compared (a record's
    priority counts within its Altium kind)."""

    def side(selector: Selector | None) -> Selector | None:
        return None if selector is None or selector.op == "all" else selector

    def near(one: int | None, other: int | None) -> bool:
        if one is None or other is None:
            return one is other
        return abs(one - other) <= tolerance

    return (
        first.kind == second.kind
        and first.selector_a == second.selector_a
        and side(first.selector_b) == side(second.selector_b)
        and first.layers == second.layers
        and near(first.min, second.min)
        and near(first.opt, second.opt)
        and near(first.max, second.max)
    )


def same_rules(first: Sequence[Rule], second: Sequence[Rule], *, tolerance: int = TOLERANCE_NM) -> bool:
    """Whether the two sequences hold the same rules in the same order (``same_rule``)."""
    return len(first) == len(second) and all(
        same_rule(one, other, tolerance=tolerance) for one, other in zip(first, second, strict=True)
    )


def write_rule_file(rules: Sequence[Rule], *, name: str = "rules") -> bytes:
    """The bytes of a rule file in the export form that holds the rules of ``rules`` that ``lower``
    writes, one record per line in the order of the lowering (capability altium-project-reader, "Rule file
    written"; ``rule-file.md``, "Writing a rule file"). ``name`` seeds the unique ids, so the same rules
    and name give the same bytes. Without a lowered rule the result is empty, which is no rule file: the
    caller writes none. ``read.rul.read_rule_file`` reads the bytes back and ``read.rules.map_rules`` maps
    every record."""
    from fenolite.backends.altium.project import (
        unique_id,
    )  # project imports the PCB writer, which imports this

    lines: list[bytes] = []
    for record in lower(rules).records:
        fields = (
            *RULE_FILE_COMMON,
            *record.fields(unique_id=unique_id(f"rul:{name}:rule:{record.name}")),
        )
        text = "|".join(f"{key}={value}" for key, value in fields)
        lines.append(text.encode("ascii") + WRITTEN_END)
    return b"".join(lines)


assert {row.altium for row in TABLE if row.exact} == set(KIND_ORDER) <= set(RULE_KIND_MAP)

__all__ = [
    "ALL_SCOPE",
    "EVIDENCE",
    "EXACT",
    "KIND_ORDER",
    "NOT_LOWERED_REASONS",
    "TABLE",
    "TOLERANCE_NM",
    "Lowered",
    "LoweredRule",
    "NotLowered",
    "Reason",
    "RuleRow",
    "ScopeForm",
    "governing_order",
    "lift",
    "lower",
    "row_of",
    "rule_selector",
    "same_rule",
    "same_rules",
    "scope_of",
    "selector_text",
    "write_rule_file",
]
