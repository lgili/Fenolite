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

import dataclasses
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal, get_args

import fenolite.backends.altium.pcbrecords as rec
from fenolite.backends.altium.ascii import Field, text_problem
from fenolite.backends.altium.read.rul import RULE_FILE_COMMON, WRITTEN_END
from fenolite.backends.altium.read.rules import RULE_KIND_MAP, CopperLayers, map_rules
from fenolite.backends.altium.read.rules import Field as ReadField
from fenolite.backends.altium.read.scope import ANY_NET, GLOB_CHARACTERS, parse_scope
from fenolite.core.evidence import Evidence, Level
from fenolite.model.rules import Rule, RuleKind, Selector

EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-RULE-CLEARANCE-CELLS",
        "H-A-RULE-CLEARANCE-FORMS",
        "H-A-RULE-FILE",
        "H-A-RULE-KINDS",
        "H-A-RULE-OPEN-LIMIT",
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
ScopeForm = Literal["all", "net", "netclass", "ref", "item", "and", "or", "not", "pair"]
ALL_SCOPE = "All"
TOLERANCE_NM = 2
"""The largest difference between a neutral value and the value read back: the PCB unit is 2.54 nm."""

_UNARY: tuple[ScopeForm, ...] = ("all", "net", "netclass", "ref", "item", "and", "or", "not")
"""The scope forms of a rule with one scope: the leaves ``net``, ``netclass``, ``ref`` and ``item_kind``
and their combinations (``ref``, ``item``, ``or`` and ``not`` since change c0412)."""
ITEM_QUERIES: dict[str, str] = {"track": "IsTrack", "via": "IsVia", "pad": "IsPad", "zone": "InPolygon"}
"""The written query of each item kind (change c0412): the object type checks of the closed scope grammar,
and ``InPolygon`` for the copper of a pour, which a Clearance rule names so (``pcb-pour.md`` I3, S-1702)."""
_ITEM_NAMES: dict[str, str] = {"track": "track", "via": "via", "pad": "pad", "zone": "polygon"}
_FORMS: dict[str, ScopeForm] = {
    "net": "net",
    "netclass": "netclass",
    "ref": "ref",
    "item_kind": "item",
    "and": "and",
    "or": "or",
    "not": "not",
}
"""Selector op → the scope form it needs."""


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
PAIR_LAYERS: tuple[str, ...] = ("TOPLAYER", *(f"MIDLAYER{n}" for n in range(1, 31)), "BOTTOMLAYER")
"""The layer prefixes of the per-layer width keys of a Differential Pairs Routing record, in the order of
the public records (S-0297, S-1930): ``<LAYER>_MINWIDTH``, ``_MAXWIDTH`` and ``_PREFWIDTH`` per layer."""
PAIR_WIDTH_KEYS: tuple[str, ...] = tuple(
    f"{layer}_{limit}WIDTH" for layer in PAIR_LAYERS for limit in ("MIN", "MAX", "PREF")
)
_PAIR_KEYS = ("MAXLIMIT", "MINLIMIT", "MOSTFREQGAP", *PAIR_WIDTH_KEYS, "MAXUNCOUPLEDLENGTH")
OPEN_MAX = 100_000_000
"""The maximum written for a limit that a rule does not give (change c0434): 100 mm, the largest maximum of
a public record (``MAXWIDTH`` and ``MAXHOLEWIDTH`` 3937.0079 mil, S-1930). A missing minimum is written 0,
a missing preferred value as the rule's minimum (its maximum when it has none)."""
_PAIR_KINDS: tuple[tuple[RuleKind, str], ...] = (
    ("skew", "the length match of a group of nets"),
    ("diff_pair_skew", "the length match within a differential pair"),
    ("length", "the length of a net"),
)
"""The pair and length kinds of change c0104 and what each constrains, for the notes of their rows: no
row of them is written, because no fact about their records is recorded."""
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
        EXACT,
        "ComponentClearance",
        24,
        ("min",),
        ("GAP", "COLLISIONCHECKMODE", "VERTICALGAP", "SHOWDISTANCES"),
        scopes=(*_UNARY, "pair"),
        note="Component Clearance measures component bodies or selection areas, not courtyards; written "
        "with the vertical gap equal to the gap and the check mode 3 of every public record",
    ),
    RuleRow(
        "silk_clearance",
        EXACT,
        "SilkToSilkClearance",
        55,
        ("min",),
        ("SILKTOSILKCLEARANCE",),
        scopes=(*_UNARY, "pair"),
        note="written as Silk To Silk Clearance; the clearance of silkscreen to solder mask, which Altium "
        "holds in another kind, is not written",
    ),
    RuleRow(
        "creepage",
        "no-counterpart",
        note="Altium's Creepage Distance rule is in no public file, so its record is not known",
    ),
    RuleRow(
        "no_tracks",
        "no-counterpart",
        note="Altium's Routing Layers rule, which names the layers a scope may be routed on, is the nearest "
        "counterpart; its record (kind number, constraint keys) is in no public file read under the "
        "sources register",
    ),
    RuleRow(
        "diff_pair_gap",
        EXACT,
        "DiffPairsRouting",
        51,
        _ALL_LIMITS,
        _PAIR_KEYS,
        note="one record with the diff_pair_uncoupled rule of the same selector",
    ),
    RuleRow(
        "diff_pair_uncoupled",
        EXACT,
        "DiffPairsRouting",
        51,
        ("max",),
        _PAIR_KEYS,
        note="one record with the diff_pair_gap rule of the same selector",
    ),
    *(
        RuleRow(
            kind,
            "no-counterpart",
            note=f"the record of the Altium rule that would carry {what} is in no public source that "
            "pcb-copper.md records, so its keys are not known",
        )
        for kind, what in _PAIR_KINDS
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
    "ComponentClearance",
    "SilkToSilkClearance",
    "DiffPairsRouting",
)
"""The Altium kinds in the order their rules are written: the three kinds of change c0038 first, the last
three those of change c0434."""
KEPT_WHEN_READ: frozenset[str] = frozenset({"ComponentClearance", "SilkToSilkClearance", "DiffPairsRouting"})
"""The kinds of change c0434, which the writer writes in another form than the record it reads: a record of
them read from a PCB document is kept and written back as it was read (``adapter.rules.kept_indexes``), and
a neutral rule of them, a KiCad board's say, gets a record of its own."""
_ROWS: dict[str, RuleRow] = {row.neutral: row for row in TABLE}
_FIXED: dict[str, str] = {
    "IGNOREPADTOPADCLEARANCEINFOOTPRINT": "FALSE",
    "OBJECTCLEARANCES": "",
    "VIASTYLE": "Through Hole",
    "ABSOLUTEVALUES": "TRUE",
    "MAXPERCENT": "80.000",
    "MINPERCENT": "20.000",
    "ALLOWSTACKEDMICROVIAS": "FALSE",
    "COLLISIONCHECKMODE": "3",
    "SHOWDISTANCES": "FALSE",
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
    ("courtyard_clearance", "min"): ("GAP", "VERTICALGAP"),
    ("silk_clearance", "min"): ("SILKTOSILKCLEARANCE",),
    ("diff_pair_gap", "min"): ("MINLIMIT",),
    ("diff_pair_gap", "opt"): ("MOSTFREQGAP",),
    ("diff_pair_gap", "max"): ("MAXLIMIT",),
    ("diff_pair_uncoupled", "max"): ("MAXUNCOUPLEDLENGTH",),
}
"""(neutral kind, limit) → the keys that hold the limit."""
_PARTNER: dict[str, RuleKind] = {
    "via_diameter": "via_drill",
    "via_drill": "via_diameter",
    "diff_pair_gap": "diff_pair_uncoupled",
    "diff_pair_uncoupled": "diff_pair_gap",
}
"""The kinds whose rules of one selector share one record: a Routing Via Style holds the diameter and the
hole, a Differential Pairs Routing the gap and the uncoupled length."""
PAIRS = Selector("diff_pair", "*")


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
class Changed:
    """A rule that is written in another form (change c0434): the rule, its selector as text and why its
    record says more, or other, than the rule: a limit written open, the hole of a via taken from a
    hole_size rule, or a kind that Altium measures otherwise."""

    rule: Rule
    selector: str
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
    changed: tuple[Changed, ...] = ()
    """The rules that are written in another form (change c0434), in rule order."""

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
    """The scope text and the name part of a ``net``, ``netclass``, ``ref`` or ``item_kind`` leaf."""
    value = selector.value
    if selector.op == "item_kind":
        if value not in ITEM_QUERIES:
            raise _Refused(
                "scope-unsupported",
                f"the item kind {value!r} has no query of the closed grammar ({', '.join(ITEM_QUERIES)})",
            )
        return ITEM_QUERIES[value], _ITEM_NAMES[value]
    if selector.op == "net" and value == "*":  # any net: ``InAnyNet``, so ``NO_NET`` is ``Not InAnyNet``
        return ANY_NET, "any_net"  # (S-1680; change c0420, B7)
    problem = text_problem(value)
    if problem is None and "'" in value:
        problem = "holds an apostrophe, which the scope quotes"
    if problem is None and any(character in value for character in GLOB_CHARACTERS):
        problem = "holds a glob character; Altium's own wildcard rules are not stated"
    if problem is not None:
        raise _Refused("scope-unsupported", f"the value {value!r} of {selector.op} {problem}")
    if selector.op == "net":
        return f"InNet('{value}')", f"net_{value}"
    if selector.op == "ref":
        return f"InComponent('{value}')", f"ref_{value}"
    return f"InNetClass('{value}')", value


def _query(selector: Selector, row: RuleRow, *, nested: bool = False) -> tuple[str, str]:
    """The query of ``selector`` and its name part. An operand that is itself a conjunction, a disjunction
    or a negation is put in parentheses: the grammar holds one kind of operator per level."""
    form = _FORMS.get(selector.op)
    if form is None or form not in row.scopes:
        raise _Refused(
            "scope-unsupported",
            f"the selector {selector_text(selector)} is outside the scopes written for {row.altium} "
            "(all, a net, a net class, a component, a track, via, pad or pour, and their combinations "
            "with And, Or and Not)",
        )
    if selector.op in ("net", "netclass", "ref", "item_kind"):
        return _leaf(selector, row)
    if selector.op == "not":
        inner, inner_name = _query(selector.items[0], row, nested=True)
        text, name = f"Not {inner}", f"not_{inner_name}"
    else:
        parts = [_query(item, row, nested=True) for item in selector.items]
        word = " And " if selector.op == "and" else " Or "
        text = word.join(part for part, _name in parts)
        name = f"_{selector.op}_".join(name for _part, name in parts)
    return (f"({text})" if nested else text), name


def scope_of(selector: Selector | None, row: RuleRow) -> tuple[str, str]:
    """The scope text of ``selector`` for a rule of ``row`` and the part of the rule name it gives
    (``""`` for all objects). Raises the refusal ``scope-unsupported`` outside the written forms; the text
    is one that ``read.scope.parse_scope`` turns back into ``selector``."""
    if selector is None or selector.op == "all":
        return ALL_SCOPE, ""
    text, name = _query(selector, row)
    if parse_scope(text) != selector:  # the reader's grammar is the judge of what is written
        raise _Refused("scope-unsupported", f"the scope {text} does not read back as the selector")
    return text, name


def _filled(given: dict[str, int | None], limits: Sequence[str]) -> dict[str, int]:
    """The limits ``limits`` of ``given``, each one that is missing written open (``OPEN_MAX``)."""
    known = [value for value in given.values() if value is not None]
    low = given.get("min")
    high = given.get("max")
    values: dict[str, int] = {}
    for name in limits:
        value = given.get(name)
        if value is None:
            if name == "min":
                value = 0
            elif name == "max":
                value = max([OPEN_MAX, *known])
            else:
                value = low if low is not None else high if high is not None else 0
        values[name] = value
    return values


def _mil(name: str, value: int) -> str:
    """``value`` as mil text; refused below the PCB unit, negative or outside its range."""
    try:
        units = rec.to_units(value)
    except ValueError as error:
        raise _Refused("value-unsupported", str(error)) from error
    if value < 0 or (value > 0 and units == 0):
        raise _Refused(
            "value-unsupported", f"{name} of {value} nm is below the PCB unit of 2.54 nm or negative"
        )
    return rec.mil_text(units)


def _lengths(rule: Rule, row: RuleRow) -> tuple[dict[str, str], tuple[str, ...]]:
    """The length keys of ``rule`` as mil text and the limits of the row that the rule does not give,
    which are written open (``_filled``; change c0434). Refused: a severity other than ``error``, a limit
    the row does not take, no limit at all, and a value below the PCB unit or outside its range."""
    if rule.severity != "error":
        raise _Refused(
            "value-unsupported",
            f"the severity {rule.severity} has no place in a rule record (a rule is enabled or not)",
        )
    given = {"min": rule.min, "opt": rule.opt, "max": rule.max}
    extra = [name for name, value in given.items() if value is not None and name not in row.limits]
    if extra:
        raise _Refused("value-unsupported", f"{row.altium} holds no {', '.join(extra)}")
    missing = tuple(name for name in row.limits if given[name] is None)
    if len(missing) == len(row.limits):
        raise _Refused("value-unsupported", f"the rule gives none of {', '.join(row.limits)}")
    for name in row.limits:
        value = given[name]
        if value is not None:
            _mil(name, value)
    found: dict[str, str] = {}
    for name, value in _filled(given, row.limits).items():
        for key in _LENGTH_KEYS[(rule.kind, name)]:
            found[key] = _mil(name, value)
    return found, missing


@dataclass(frozen=True, slots=True)
class _Draft:
    row: RuleRow
    scope1: str
    scope2: str
    name: str
    lengths: dict[str, str]
    rules: tuple[Rule, ...]
    notes: dict[str, tuple[str, ...]]
    """Rule id → why its record says more, or other, than the rule (``Changed``)."""


def _unpaired(selector: Selector | None) -> Selector | None:
    """The scope of a Differential Pairs Routing record for a pair rule's ``selector``: every pair
    (``diff_pair *``) is ``All``, and ``diff_pair *`` joined with ``and`` to a scope is that scope; the
    reader narrows the scope to the pairs again (``read.rules._pairs``)."""
    if selector is None or selector.op == "all" or selector == PAIRS:
        return None
    if selector.op == "and" and PAIRS in selector.items:
        rest = tuple(item for item in selector.items if item != PAIRS)
        return rest[0] if len(rest) == 1 else Selector("and", items=rest)
    raise _Refused(
        "scope-unsupported",
        f"the selector {selector_text(selector)} names no differential pairs as diff_pair *, alone or with "
        "and: a Differential Pairs Routing record selects every pair of its scope",
    )


def _draft(rule: Rule, row: RuleRow) -> _Draft:
    if rule.layers:
        raise _Refused(
            "scope-unsupported",
            f"the layers {', '.join(rule.layers)}: a layer condition is read from a PCB document "
            "with its board's layers and is not written",
        )
    first = _unpaired(rule.selector_a) if row.altium == "DiffPairsRouting" else rule.selector_a
    scope1, name1 = scope_of(first, row)
    scope2, name2 = ALL_SCOPE, ""
    if rule.selector_b is not None and rule.selector_b.op != "all":
        if "pair" not in row.scopes:
            raise _Refused("scope-unsupported", f"{row.altium} takes no second selector")
        scope2, name2 = scope_of(rule.selector_b, row)
    parts = [row.altium, *([name1] if name1 else []), *(["to", name2] if name2 else [])]
    lengths, missing = _lengths(rule, row)
    notes: list[str] = []
    if missing:
        notes.append(
            f"{row.altium} holds {', '.join(row.limits)}; the {', '.join(missing)} the rule does not give "
            "is written open (min 0, preferred as the rule's limit, max 100 mm)"
        )
    if rule.kind in _CHANGED_KINDS:
        notes.append(row.note)
    return _Draft(row, scope1, scope2, "_".join(parts), lengths, (rule,), {rule.id: tuple(notes)})


_CHANGED_KINDS = frozenset({"courtyard_clearance", "silk_clearance"})
"""The kinds whose Altium record measures otherwise than the rule (change c0434): every rule of them is
written and counted changed, with its row's note."""
_VIA = Selector("item_kind", "via")


def _plain(selector: Selector | None) -> Selector:
    return Selector("all") if selector is None else selector


def _hole_rule(diameter: Rule, rules: Sequence[Rule]) -> Rule | None:
    """The hole_size rule whose limits a Routing Via Style record of the via_diameter rule ``diameter``
    takes when no via_drill rule has its selector (change c0434): a KiCad rule set holds the drill of a via
    as a hole_size rule on vias (``backends.kicad.rulemap``). In this order: a rule on the vias of the
    same selector, a rule of the same selector, a rule on every via, a rule on every hole; the most
    governing of each."""
    scope = _plain(diameter.selector_a)
    holes = [
        rule
        for rule in governing_order(rules)
        if rule.kind == "hole_size" and not rule.layers and rule.severity == "error"
        and (rule.selector_b is None or rule.selector_b.op == "all")
    ]  # fmt: skip

    def on_vias(rule: Rule, of: Selector) -> bool:
        selector = _plain(rule.selector_a)
        if of.op == "all":
            return selector == _VIA
        return selector.op == "and" and set(selector.items) == {_VIA, of}

    tests: tuple[Callable[[Rule], bool], ...] = (
        lambda hole: on_vias(hole, scope),
        lambda hole: _plain(hole.selector_a) == scope,
        lambda hole: on_vias(hole, Selector("all")),
        lambda hole: _plain(hole.selector_a).op == "all",
    )
    for test in tests:
        for rule in holes:
            if test(rule):
                return rule
    return None


def _hole_keys(hole: Rule) -> dict[str, str]:
    values = _filled({"min": hole.min, "opt": None, "max": hole.max}, _ALL_LIMITS)
    names = {"min": "MINHOLEWIDTH", "opt": "HOLEWIDTH", "max": "MAXHOLEWIDTH"}
    return {names[name]: _mil(name, value) for name, value in values.items()}


def _pair_widths(rules: Sequence[Rule]) -> tuple[dict[str, str], str]:
    """The per-layer width keys of a Differential Pairs Routing record and where they come from: the limits
    of the most governing track_width rule on every object, written open where it gives none, or open with
    Fenolite's default preferred width of 0.25 mm (``pcb-copper.md``, "Rules") without one."""
    for rule in governing_order(rules):
        if (
            rule.kind == "track_width" and not rule.layers and rule.severity == "error"
            and _plain(rule.selector_a).op == "all"
        ):  # fmt: skip
            values = _filled({"min": rule.min, "opt": rule.opt, "max": rule.max}, _ALL_LIMITS)
            source = "those of the track_width rule (all)"
            break
    else:
        values = {"min": 0, "opt": 250_000, "max": OPEN_MAX}
        source = "open, with the preferred width 0.25 mm: no track_width rule holds every object"
    try:
        text = {name: _mil(name, value) for name, value in values.items()}
    except _Refused:  # the rule's own limits are refused with it; the widths are written open
        values = {"min": 0, "opt": 250_000, "max": OPEN_MAX}
        text = {name: _mil(name, value) for name, value in values.items()}
        source = "open, with the preferred width 0.25 mm: the track_width rule (all) is not written"
    keys = {
        f"{layer}_{suffix}WIDTH": text[name]
        for layer in PAIR_LAYERS
        for suffix, name in (("MIN", "min"), ("MAX", "max"), ("PREF", "opt"))
    }
    return keys, f"the per-layer track widths of the record are {source}"


def governing_order(rules: Sequence[Rule]) -> tuple[Rule, ...]:
    """``rules`` from the most governing to the least: priority 1, 2, … and then priority 0 (unset); ties
    by falling name, then id. It is the reverse of the order in which the KiCad build writes its rules,
    where the last rule governs, so one script gives both targets the same precedence."""
    rising = sorted(rules, key=lambda r: (r.priority != 0, -r.priority, r.name, r.id))
    return tuple(reversed(rising))


def _kept(rule: Rule) -> bool:
    """Whether ``rule`` came from a kept record of an imported board (``adapter.rules.KEPT_RECORD``)."""
    held = rule.ext.get("altium")
    return held is not None and ("kept_record", "1") in held.payload


def lower(rules: Sequence[Rule]) -> Lowered:
    """The rule records of ``rules``, the rules that are not written, each with one reason, and the rules
    that are written in another form.

    A rule is written when its row is ``exact``, its selectors are scopes of the row and its severity is
    ``error``. A limit of the row that the rule does not give is written open (min 0, the preferred value
    as the rule's limit, max ``OPEN_MAX``) and the rule is counted changed (change c0434). A
    ``via_diameter`` and a ``via_drill`` rule of the same selector share one Routing Via Style record, a
    ``diff_pair_gap`` and a ``diff_pair_uncoupled`` rule one Differential Pairs Routing record. A
    ``via_diameter`` rule alone takes the hole limits of a hole_size rule (``_hole_rule``), a
    ``diff_pair_gap`` rule alone an open uncoupled length; a ``via_drill`` or ``diff_pair_uncoupled`` rule
    alone is not written. Names come from the kind and the scope (``Width``, ``Width_PWR``,
    ``Clearance_net_A_to_B``); a repeated name gets ``_2``, ``_3``… A rule of a kept record (the pair
    ``kept_record`` of an imported rule, change c0424) is left out without a reason: the record is written
    back as it was read."""
    rules = [rule for rule in rules if not _kept(rule)]
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
        partner = _PARTNER.get(rule.kind)
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
            row,
            first.scope1,
            first.scope2,
            first.name,
            first.lengths | draft.lengths,
            (*first.rules, rule),
            first.notes | draft.notes,
        )
    alone = {index for queue in waiting.values() for index in queue}
    for index in sorted(alone):
        draft = drafts[index]
        rule = draft.rules[0]
        notes = draft.notes[rule.id]
        if rule.kind == "via_diameter" and (hole := _hole_rule(rule, rules)) is not None:
            try:
                keys = _hole_keys(hole)
            except _Refused as refusal:
                refuse(rule, refusal.reason, refusal.detail)
                continue
            note = (
                f"a Routing Via Style rule holds the hole too: written with the limits of the hole_size rule "
                f"({rule_selector(hole)}), its preferred hole its min"
            )
            drafts[index] = dataclasses.replace(
                draft, lengths=draft.lengths | keys, notes={rule.id: (*notes, note)}
            )
            continue
        if rule.kind == "diff_pair_gap":
            note = "a Differential Pairs Routing rule holds the uncoupled length too: written open (100 mm)"
            uncoupled = {"MAXUNCOUPLEDLENGTH": rec.mil_text(rec.to_units(OPEN_MAX))}
            drafts[index] = dataclasses.replace(
                draft, lengths=draft.lengths | uncoupled, notes={rule.id: (*notes, note)}
            )
            continue
        what = {
            "via_diameter": "a Routing Via Style rule holds the diameter and the hole; no via_drill rule has "
            "the same selector, and no hole_size rule applies to its vias",
            "via_drill": "a Routing Via Style rule holds the diameter and the hole; no via_diameter rule has "
            "the same selector",
            "diff_pair_uncoupled": "a Differential Pairs Routing rule holds the gap and the uncoupled "
            "length; no diff_pair_gap rule has the same selector",
        }[rule.kind]
        refuse(rule, "value-unsupported", what)
    kept = [draft for draft in drafts if rule_ids(draft) - set(refused)]
    widths, width_note = _pair_widths(rules)
    records: list[LoweredRule] = []
    changed: dict[str, Changed] = {}
    used: set[str] = set()
    for kind in KIND_ORDER:
        of_kind = [draft for draft in kept if draft.row.altium == kind]
        for priority, draft in enumerate(of_kind, start=1):
            name, count = draft.name, 1
            while name in used:
                count += 1
                name = f"{draft.name}_{count}"
            used.add(name)
            lengths = draft.lengths | widths if kind == "DiffPairsRouting" else draft.lengths
            keys = tuple((key, lengths.get(key, _FIXED.get(key, ""))) for key in draft.row.fields)
            ordered = tuple(sorted(draft.rules, key=lambda r: r.kind))
            for rule in ordered:
                notes = draft.notes.get(rule.id, ())
                if rule.kind == "diff_pair_gap":
                    notes = (*notes, width_note)
                if notes:
                    changed[rule.id] = Changed(rule, rule_selector(rule), "; ".join(notes))
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
    return Lowered(
        tuple(records),
        tuple(refused[rule.id] for rule in rules if rule.id in refused),
        tuple(changed[rule.id] for rule in rules if rule.id in changed),
    )


def rule_ids(draft: _Draft) -> set[str]:
    return {rule.id for rule in draft.rules}


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
    "KEPT_WHEN_READ",
    "OPEN_MAX",
    "PAIR_LAYERS",
    "PAIR_WIDTH_KEYS",
    "Changed",
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
