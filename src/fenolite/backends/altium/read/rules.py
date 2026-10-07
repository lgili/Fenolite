# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Altium rule records onto the neutral rules, exactly or not at all (capability altium-project-reader,
"Rules onto the neutral model", change c0042).

``map_rules`` takes field lists, the ``(key, value)`` pairs of rule records in order: the records of an
exported rule file (``rul.RuleFile.records``) or the rule records of a PCB document, which hold the same
keys (``docs/formats/altium/rule-file.md``). A record maps only when its kind, header values, keys and
scopes are inside the closed tables of this module; every other record is listed as ``Unmapped`` with a
reason. No record is dropped and no value is approximated. Fenolite ships no rule value: every limit
comes from a record.

Change c0125 reads more forms of a Clearance record (``rule-file.md``, "Clearance forms that map"): a
blank or uniform ``OBJECTCLEARANCES``, the keys of a cell of the clearance matrix between net classes, and,
when the caller gives the copper layers of the record's board (``CopperLayers``), two layer conditions.
"""

# evidence: see import_evidence, read.project

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from fenolite.backends.altium.read.proptext import parse_length
from fenolite.backends.altium.read.scope import LayerScope, parse_layer_scope, parse_scope
from fenolite.backends.altium.read.textfile import text_issue
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm, round_half_even_div
from fenolite.model.base import ExtBag
from fenolite.model.rules import Rule, RuleKind, RuleSet, Selector

Field = tuple[str, str | None]
BACKEND = "altium"

HEADER_KEYS = (
    "RULEKIND",
    "NETSCOPE",
    "LAYERKIND",
    "SCOPE1EXPRESSION",
    "SCOPE2EXPRESSION",
    "NAME",
    "ENABLED",
    "PRIORITY",
    "COMMENT",
    "UNIQUEID",
    "DEFINEDBYLOGICALDOCUMENT",
)
"""The keys every rule record of a PCB document holds after its common keys (``rule-file.md``)."""
SAME_LAYER = "SameLayer"
ALL = "All"


@dataclass(frozen=True, slots=True)
class NeutralLimits:
    """One neutral rule of a kind: the keys of its minimum, preferred and maximum (``None``: none)."""

    kind: RuleKind
    min: str | None
    opt: str | None
    max: str | None

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(key for key in (self.min, self.opt, self.max) if key is not None)


@dataclass(frozen=True, slots=True)
class Condition:
    """A further key of a kind. Absent: allowed unless ``required``. Present: its value must be one of
    ``values`` (``None``: any value is allowed and unused), or equal, as a length, to the value of the
    key ``same_as``. With ``matrix_with`` the value is an object matrix that ``read_matrix`` must read,
    the generic clearance being the value of the key ``matrix_with``. ``read_only`` marks a key
    that is read and that the writer of ``rulemap`` never writes."""

    key: str
    values: tuple[str, ...] | None = None
    required: bool = False
    same_as: str = ""
    matrix_with: str = ""
    read_only: bool = False


@dataclass(frozen=True, slots=True)
class KindMap:
    """How one Altium rule kind maps: its neutral rules, the ``NETSCOPE`` it needs, its further
    conditions, and whether it is binary (a second scope)."""

    rules: tuple[NeutralLimits, ...]
    net_scope: str
    conditions: tuple[Condition, ...] = ()
    binary: bool = False

    @property
    def cells(self) -> bool:
        """Whether the kind holds an object matrix whose cells give rules of their own."""
        return any(condition.matrix_with for condition in self.conditions)

    @property
    def keys(self) -> frozenset[str]:
        """Every key of the kind: the limit keys and the condition keys."""
        return frozenset(key for limits in self.rules for key in limits.keys) | {
            c.key for c in self.conditions
        }


@dataclass(frozen=True, slots=True)
class CopperLayer:
    """One copper layer of a board: the name the document gives it, its neutral name, and whether it is an
    internal signal layer (neither the top, nor the bottom, nor an internal plane)."""

    document_name: str
    name: str
    inner_signal: bool = False


@dataclass(frozen=True, slots=True)
class CopperLayers:
    """The copper layers of the board whose rule records are mapped, from top to bottom. Without them a
    layer condition is refused: a layer name is the board's own."""

    layers: tuple[CopperLayer, ...]

    def named(self, document_name: str) -> tuple[CopperLayer, ...]:
        """The layers the document names ``document_name``, letter for letter."""
        return tuple(layer for layer in self.layers if layer.document_name == document_name)


MATRIX_UNIT = (254, 100)
"""One count of an entry of ``OBJECTCLEARANCES`` in nanometres, as a fraction: 0.0001 mil, the unit of
the document's coordinates (``rule-file.md``, "Clearance forms that map"; ``H-A-RULE-CLEARANCE-FORMS``)."""
_MATRIX_ENTRY = re.compile(r"ClearanceObj_([A-Za-z]+)-ClearanceObj_([A-Za-z]+):(\d+)")
ITEM_KINDS = ("track", "pad", "via", "zone")
"""The item kinds of the copper check that a cell rule names (``model.rules`` ``item_kind``; the check
sees an arc as a ``track`` and the fill of a poured polygon as a ``zone``)."""
MATRIX_KINDS: dict[str, str | None] = {
    "Arc": "track",
    "Track": "track",
    "SMDPad": "pad",
    "THPad": "pad",
    "Via": "via",
    "Poly": "zone",
    "Fill": None,
    "Region": None,
    "Text": None,
    "Hole": None,
}
"""Object kind of the matrix → the item kind of the copper check that holds it, or ``None`` when the check
holds no item of the kind: a fill and a region are graphics in the model, text is no copper item, and the
clearance of a hole is another neutral kind (``rule-file.md``, "Cells of an object matrix";
``H-A-RULE-CLEARANCE-CELLS``)."""
CELL_PAIR = "cell"
UNJUDGED_PAIR = "cells_not_lifted"
"""Pairs that the mapper adds to a rule's bag: the item kinds of a cell rule (``track-via``), and on the
rule of the generic clearance the entries of the matrix that no rule holds, as written."""

RULE_KIND_MAP: dict[str, KindMap] = {
    "Clearance": KindMap(
        (NeutralLimits("clearance", "GAP", None, None),),
        "DifferentNets",
        (
            Condition("OBJECTCLEARANCES", matrix_with="GAP"),
            Condition("GENERICCLEARANCE", same_as="GAP"),
            Condition("IGNOREPADTOPADCLEARANCEINFOOTPRINT", ("FALSE",)),
            Condition("ISMATRIX", ("TRUE",), read_only=True),
            Condition("SOURCERULE", read_only=True),
            Condition("CELLROWNAME", ("All",), read_only=True),
            Condition("CELLROWTYPE", ("0",), read_only=True),
            Condition("CELLCOLNAME", ("All",), read_only=True),
            Condition("CELLCOLTYPE", ("0",), read_only=True),
            Condition("INNERLAYERS", ("TRUE",), read_only=True),
            Condition("OUTERLAYERS", ("TRUE",), read_only=True),
        ),
        binary=True,
    ),
    "Width": KindMap((NeutralLimits("track_width", "MINLIMIT", "PREFEREDWIDTH", "MAXLIMIT"),), "AnyNet"),
    "RoutingVias": KindMap(
        (
            NeutralLimits("via_diameter", "MINWIDTH", "WIDTH", "MAXWIDTH"),
            NeutralLimits("via_drill", "MINHOLEWIDTH", "HOLEWIDTH", "MAXHOLEWIDTH"),
        ),
        "AnyNet",
        (Condition("VIASTYLE", ("Through Hole",), required=True),),
    ),
    "HoleSize": KindMap(
        (NeutralLimits("hole_size", "MINLIMIT", None, "MAXLIMIT"),),
        "AnyNet",
        (
            Condition("ABSOLUTEVALUES", ("TRUE",), required=True),
            Condition("MINPERCENT"),
            Condition("MAXPERCENT"),
        ),
    ),
    "BoardOutlineClearance": KindMap(
        (NeutralLimits("edge_clearance", "GAP", None, None),),
        "DifferentNets",
        (
            Condition("OBJECTCLEARANCES", ("",)),
            Condition("GENERICCLEARANCE", same_as="GAP"),
            Condition("IGNOREPADTOPADCLEARANCEINFOOTPRINT", ("FALSE",)),
        ),
    ),
    "HoleToHoleClearance": KindMap(
        (NeutralLimits("hole_to_hole", "GAP", None, None),),
        "AnyNet",
        (Condition("ALLOWSTACKEDMICROVIAS", ("FALSE",), required=True),),
    ),
    "MinimumAnnularRing": KindMap((NeutralLimits("annular_width", "MINIMUMRING", None, None),), "AnyNet"),
}
"""The closed table of the kinds that map (``rule-file.md``, "Rule kinds that map";
``H-A-RD-PRJ-RULE-MAP``; the last three kinds are those of change c0084, ``H-A-RULE-KINDS``). It holds
every Altium kind of an ``exact`` row of ``rulemap.TABLE``. The keys of Clearance after
``IGNOREPADTOPADCLEARANCEINFOOTPRINT`` and its uniform matrix are those of change c0125
(``H-A-RULE-CLEARANCE-FORMS``); the writer writes none of them."""
PENDING_KINDS: dict[str, RuleKind] = {}
"""Kinds with a neutral counterpart but no permitted source for their keys: reported apart. Empty since
change c0084, which found the keys of ``BoardOutlineClearance`` in the public corpus."""

UnmappedReason = Literal[
    "summary-form",
    "malformed",
    "no-counterpart",
    "no-verified-keys",
    "disabled",
    "net-scope",
    "layer-kind",
    "keys",
    "value",
    "scope",
    "no-layer",
]
UNMAPPED_REASONS: tuple[UnmappedReason, ...] = (
    "summary-form",
    "malformed",
    "no-counterpart",
    "no-verified-keys",
    "disabled",
    "net-scope",
    "layer-kind",
    "keys",
    "value",
    "scope",
    "no-layer",
)
"""The reasons in the order they are checked: the first one that holds is reported."""
NOT_APPLYING: frozenset[UnmappedReason] = frozenset({"disabled", "no-layer"})
"""The reasons of a record that takes no part in a check: Altium skips a disabled rule, and a rule whose
scope names a kind of layer the board does not hold applies to no object. Every other reason leaves a rule
of the document unread."""


@dataclass(frozen=True, slots=True)
class Unmapped:
    """A record that gives no rule: its index in the input, its kind and name as written, the reason and
    a detail."""

    index: int
    kind: str
    name: str
    reason: UnmappedReason
    detail: str


@dataclass(frozen=True, slots=True)
class RuleMapping:
    """The neutral rules of the mapped records, the unmapped records, the issues, and for each rule of
    ``ruleset`` the index of the record it came from (``rule_records``)."""

    ruleset: RuleSet
    unmapped: tuple[Unmapped, ...]
    issues: tuple[Issue, ...]
    rule_records: tuple[int, ...] = ()
    matrix_cells: tuple[tuple[int, int, int], ...] = ()
    """For each enabled Clearance record with entries in its object matrix: its index, the number of
    entries that a rule of ``ruleset`` holds, and the number that none holds (every entry of an unmapped
    record; of a mapped one, the entries with an object kind the copper check holds no item of)."""

    @property
    def sources(self) -> tuple[int, ...]:
        """The indexes of the records that gave at least one rule, ascending."""
        return tuple(sorted(set(self.rule_records)))


class _Refusal(Exception):
    reason: UnmappedReason
    detail: str

    def __init__(self, reason: UnmappedReason, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def _get(fields: Sequence[Field], key: str) -> str | None:
    for name, value in fields:
        if name == key:
            return value
    return None


def _has(fields: Sequence[Field], key: str) -> bool:
    return any(name == key for name, _value in fields)


def record_text(fields: Sequence[Field]) -> str:
    """The property text of a field list: ``KEY=VALUE`` parts (a key alone without value) joined by ``|``."""
    return "|".join(key if value is None else f"{key}={value}" for key, value in fields)


def _header(fields: Sequence[Field]) -> tuple[str, str, int]:
    kind = _get(fields, "RULEKIND")
    name = _get(fields, "NAME")
    priority = _get(fields, "PRIORITY")
    if not kind:
        raise _Refusal("malformed", "the record has no RULEKIND")
    if not name:
        raise _Refusal("malformed", "the record has no NAME")
    if priority is None or not (priority.isascii() and priority.isdigit()) or int(priority) < 1:
        raise _Refusal("malformed", f"PRIORITY {priority!r} is not a positive integer")
    return kind, name, int(priority)


@dataclass(frozen=True, slots=True)
class Matrix:
    """What an object matrix says in the item kinds of the copper check (``read_matrix``): ``cells`` are
    the pairs of item kinds whose clearance differs from the generic one, as (kind, kind, nanometres) in
    the order of ``ITEM_KINDS``; ``judged`` counts the entries of the text whose two object kinds the check
    holds items of, and ``unjudged`` lists the other entries as written."""

    cells: tuple[tuple[str, str, Nm], ...] = ()
    judged: int = 0
    unjudged: tuple[str, ...] = ()


def read_matrix(text: str, gap: str | None) -> Matrix | str:
    """The object matrix ``text`` (the value of ``OBJECTCLEARANCES``) of a record whose generic clearance
    is the length ``gap``, or a string that says why a neutral rule set cannot say it.

    Entries are ``ClearanceObj_<kind>-ClearanceObj_<kind>:<count>`` joined by ``;``; a count is
    ``MATRIX_UNIT`` long, and a pair the text leaves out holds ``gap``. The object kinds fall into the item
    kinds of the copper check by ``MATRIX_KINDS``. A pair of item kinds is said exactly when every pair of
    object kinds in it holds one value: that value is a cell when it differs from ``gap``. When the object
    kinds of one item kind disagree (an arc and a track, a through-hole pad and a surface pad) no neutral
    rule says the pair, and the matrix is refused. An entry with an object kind that the check holds no
    item of (a fill, a region, text, a hole) is listed in ``unjudged`` and changes nothing else."""
    if not text.strip():
        return Matrix()
    length = parse_length(gap or "")
    listed: dict[tuple[str, str], Nm] = {}
    unjudged: list[str] = []
    judged = 0
    for part in text.strip().split(";"):
        entry = part.strip()
        match = _MATRIX_ENTRY.fullmatch(entry)
        if match is None:
            return "OBJECTCLEARANCES holds text that is no entry of an object matrix"
        first, second = match.group(1), match.group(2)
        for name in (first, second):
            if name not in MATRIX_KINDS:
                return f"OBJECTCLEARANCES names the object kind {name}, which is outside the table"
        first, second = sorted((first, second))
        if (first, second) in listed:
            return f"OBJECTCLEARANCES holds two entries for {first} and {second}"
        listed[(first, second)] = round_half_even_div(int(match.group(3)) * MATRIX_UNIT[0], MATRIX_UNIT[1])
        if MATRIX_KINDS[first] is None or MATRIX_KINDS[second] is None:
            unjudged.append(entry)
        else:
            judged += 1
    if length is None:
        return "OBJECTCLEARANCES holds entries and the record holds no GAP that is a length"
    values: dict[tuple[str, str], set[Nm]] = {}
    names = sorted(name for name, kind in MATRIX_KINDS.items() if kind is not None)
    for position, first in enumerate(names):
        for second in names[position:]:
            kinds = sorted((MATRIX_KINDS[first] or "", MATRIX_KINDS[second] or ""), key=ITEM_KINDS.index)
            values.setdefault((kinds[0], kinds[1]), set()).add(listed.get((first, second), length))
    ordered = sorted(values, key=lambda pair: (ITEM_KINDS.index(pair[0]), ITEM_KINDS.index(pair[1])))
    mixed = [f"{first} to {second}" for first, second in ordered if len(values[(first, second)]) > 1]
    if mixed:
        return (
            f"OBJECTCLEARANCES is a matrix of differing clearances whose cells for {', '.join(mixed)} hold "
            "more than one value: a neutral rule tells a track, a pad, a via and a poured polygon apart, "
            "and not an arc from a track or a through-hole pad from a surface pad"
        )
    cells = tuple(
        (first, second, value)
        for first, second in ordered
        for value in values[(first, second)]
        if value != length
    )
    return Matrix(cells, judged, tuple(unjudged))


def matrix_problem(text: str, gap: str | None) -> str:
    """Why ``read_matrix`` refuses the object matrix ``text``, or ``""`` when it reads it."""
    found = read_matrix(text, gap)
    return found if isinstance(found, str) else ""


def _check_keys(fields: Sequence[Field], kind: str, table: KindMap) -> None:
    first = next(position for position, (key, _value) in enumerate(fields) if key == "RULEKIND")
    allowed = {key for key, _value in fields[:first]} | set(HEADER_KEYS) | table.keys
    unknown = sorted({key for key, _value in fields} - allowed)
    if unknown:
        raise _Refusal("keys", f"the keys {', '.join(unknown)} are not in the table of {kind}")
    for condition in table.conditions:
        value = _get(fields, condition.key)
        if not _has(fields, condition.key):
            if condition.required:
                raise _Refusal("keys", f"{condition.key} is required for {kind}")
            continue
        if condition.matrix_with:
            problem = matrix_problem(value or "", _get(fields, condition.matrix_with))
            if problem:
                raise _Refusal("keys", problem)
        elif condition.same_as:
            other = _get(fields, condition.same_as)
            mine = parse_length(value or "")
            if mine is None or other is None or mine != parse_length(other):
                raise _Refusal("keys", f"{condition.key} differs from {condition.same_as}")
        elif condition.values is not None and value not in condition.values:
            raise _Refusal("keys", f"{condition.key}={value} is outside the table of {kind}")


def _limits(
    fields: Sequence[Field], kind: str, table: KindMap
) -> list[tuple[NeutralLimits, tuple[Nm | None, ...]]]:
    groups: list[tuple[NeutralLimits, tuple[Nm | None, ...]]] = []
    for limits in table.rules:
        values: list[Nm | None] = []
        for key in (limits.min, limits.opt, limits.max):
            if key is None or not _has(fields, key):
                values.append(None)
                continue
            text = _get(fields, key)
            length = parse_length(text or "")
            if length is None:
                raise _Refusal("value", f"{key}={text} is not a length (a decimal number and mil or mm)")
            values.append(length)
        if any(value is not None for value in values):
            groups.append((limits, tuple(values)))
    if kind in ("Clearance", "BoardOutlineClearance") and not _has(fields, "GAP"):
        raise _Refusal("value", f"the {kind} has no GAP")
    if not groups:
        raise _Refusal("value", f"the {kind} gives no limit")
    return groups


def _layer_scope(first: LayerScope, second: LayerScope | None, layers: CopperLayers) -> tuple[str, ...]:
    """The neutral layers of a binary rule whose two scopes are the layer condition ``first``
    (``rule-file.md``, "Layer scopes of Clearance"). The neutral layer condition is the layer a pair of
    objects is judged on, and a via or a through-hole pad is judged on every layer it spans, so a
    condition maps only where the two say the same for every pair; any other is refused."""
    if second != first:
        raise _Refusal(
            "scope",
            "a layer condition maps only when the two scopes hold the same one: the neutral layer "
            "condition holds for both objects of a pair",
        )
    if first.inner:
        if any(layer.inner_signal for layer in layers.layers):
            raise _Refusal(
                "scope",
                "OnMid on a board with internal signal layers: no permitted source says whether a via "
                "or a through-hole pad is on them, so the pairs of the rule are not known",
            )
        raise _Refusal(
            "no-layer", "OnMid on a board without an internal signal layer: the rule applies to no object"
        )
    named: list[str] = []
    for name in first.names:
        found = layers.named(name)
        if len(found) != 1:
            raise _Refusal(
                "scope",
                f"ExistsOnLayer names {name!r}, which {len(found)} copper layers of the board are called",
            )
        named.append(found[0].name)
    missing = [layer.name for layer in layers.layers if layer.name not in named]
    if missing:
        raise _Refusal(
            "scope",
            f"ExistsOnLayer names {len(set(named))} of the board's {len(layers.layers)} copper layers: a "
            f"via or a through-hole pad that exists on them is also judged on {', '.join(missing)}, where "
            "the neutral layer condition does not hold",
        )
    return tuple(layer.name for layer in layers.layers)


def _scopes(
    fields: Sequence[Field], table: KindMap, layers: CopperLayers | None = None
) -> tuple[Selector, Selector | None, tuple[str, ...]]:
    first = _get(fields, "SCOPE1EXPRESSION")
    second = _get(fields, "SCOPE2EXPRESSION")
    if first is None:
        raise _Refusal("scope", "the record has no SCOPE1EXPRESSION")
    if layers is not None and table.binary and second is not None:
        layered = parse_layer_scope(first)
        if layered is not None:
            return Selector("all"), None, _layer_scope(layered, parse_layer_scope(second), layers)
    selector_a = parse_scope(first)
    if isinstance(selector_a, str):
        raise _Refusal("scope", f"SCOPE1EXPRESSION: {selector_a}")
    if not table.binary:
        if second is None or second.strip() != ALL:
            raise _Refusal("scope", "SCOPE2EXPRESSION is not All for a unary rule")
        return selector_a, None, ()
    if second is None:
        raise _Refusal("scope", "the record has no SCOPE2EXPRESSION")
    if second.strip() == ALL:
        return selector_a, None, ()
    selector_b = parse_scope(second)
    if isinstance(selector_b, str):
        raise _Refusal("scope", f"SCOPE2EXPRESSION: {selector_b}")
    return selector_a, selector_b, ()


def _map_one(fields: Sequence[Field], index: int, origin: str, layers: CopperLayers | None) -> list[Rule]:
    kind, name, priority = _header(fields)
    table = RULE_KIND_MAP.get(kind)
    if table is None:
        if kind in PENDING_KINDS:
            raise _Refusal(
                "no-verified-keys",
                f"the model has {PENDING_KINDS[kind]}, but no permitted source gives the keys of {kind}",
            )
        raise _Refusal("no-counterpart", f"the model has no counterpart of {kind}")
    enabled = _get(fields, "ENABLED")
    if enabled != "TRUE":
        raise _Refusal("disabled", f"ENABLED={enabled}: a disabled rule is skipped and the next one applies")
    net_scope = _get(fields, "NETSCOPE")
    if net_scope != table.net_scope:
        raise _Refusal("net-scope", f"NETSCOPE={net_scope}; the table needs {table.net_scope}")
    layer_kind = _get(fields, "LAYERKIND")
    if layer_kind != SAME_LAYER:
        raise _Refusal("layer-kind", f"LAYERKIND={layer_kind}; the table needs {SAME_LAYER}")
    _check_keys(fields, kind, table)
    groups = _limits(fields, kind, table)
    selector_a, selector_b, on_layers = _scopes(fields, table, layers)
    unique_id = _get(fields, "UNIQUEID")
    native = {BACKEND: unique_id} if unique_id else {}
    record = ("record", record_text(fields))
    matrix = read_matrix(_get(fields, "OBJECTCLEARANCES") or "", _get(fields, "GAP")) if table.cells else None
    assert not isinstance(matrix, str)  # _check_keys refused it
    left = ((UNJUDGED_PAIR, ";".join(matrix.unjudged)),) if matrix is not None and matrix.unjudged else ()
    bag = ExtBag(payload=(record, *left))
    rules: list[Rule] = []
    for limits, (low, preferred, high) in groups:
        rules.append(
            Rule(
                id=derived_id("rul", BACKEND, f"{origin}:{index}:{limits.kind}"),
                native_ids=dict(native),
                ext={BACKEND: bag},
                name=name,
                kind=limits.kind,
                selector_a=selector_a,
                selector_b=selector_b,
                layers=on_layers,
                min=low,
                opt=preferred,
                max=high,
                severity="error",
                priority=priority,
            )
        )
    for first, second, value in matrix.cells if matrix is not None else ():
        sides = [(first, second)]
        if first != second and (selector_b or Selector("all")) != selector_a:
            sides.append((second, first))  # the two scopes differ: either object may be of either kind
        for one, other in sides:
            label = f"{one}-{other}"
            rules.append(
                Rule(
                    id=derived_id("rul", BACKEND, f"{origin}:{index}:clearance:{label}"),
                    native_ids=dict(native),
                    ext={BACKEND: ExtBag(payload=(record, (CELL_PAIR, label)))},
                    name=f"{name}/{label}",
                    kind="clearance",
                    selector_a=_of_kind(selector_a, one),
                    selector_b=_of_kind(selector_b or Selector("all"), other),
                    layers=on_layers,
                    min=value,
                    severity="error",
                    priority=priority,
                )
            )
    return rules


def _of_kind(selector: Selector, kind: str) -> Selector:
    """``selector`` narrowed to the items of ``kind``."""
    leaf = Selector("item_kind", kind)
    return leaf if selector.op == "all" else Selector("and", items=(selector, leaf))


def _matrix_cells(
    records: Sequence[Sequence[Field]], mapped: frozenset[int]
) -> tuple[tuple[int, int, int], ...]:
    found: list[tuple[int, int, int]] = []
    for index, fields in enumerate(records):
        table = RULE_KIND_MAP.get(_get(fields, "RULEKIND") or "")
        text = (_get(fields, "OBJECTCLEARANCES") or "").strip()
        if table is None or not table.cells or not text or _get(fields, "ENABLED") != "TRUE":
            continue
        matrix = read_matrix(text, _get(fields, "GAP")) if index in mapped else None
        if isinstance(matrix, Matrix):
            found.append((index, matrix.judged, len(matrix.unjudged)))
        else:
            found.append((index, 0, len([part for part in text.split(";") if part.strip()])))
    return tuple(found)


def map_rules(
    records: Sequence[Sequence[Field]],
    *,
    origin: str,
    summary: bool = False,
    layers: CopperLayers | None = None,
) -> RuleMapping:
    """Map the field lists ``records`` onto neutral rules. Every record is either the source of one or
    two rules (``RuleMapping.sources``) or one ``Unmapped`` with the first reason of ``UNMAPPED_REASONS``
    that holds. ``origin`` names the source in ids and issue locations (``<origin>#<index>``). With
    ``summary`` (the records of a summary-form file) no record maps and one info
    ``altium.rule.summary-form`` comes first. ``layers`` are the copper layers of the board the records
    belong to (the records of a PCB document); without them, as for a rule file, a layer condition is
    refused."""
    issues: list[Issue] = []
    rules: list[Rule] = []
    rule_records: list[int] = []
    unmapped: list[Unmapped] = []
    if summary:
        issues.append(
            text_issue(
                "altium.rule.summary-form",
                f"the {len(records)} record(s) come from a summary-form rule file: their values carry no "
                "unit, so no rule is mapped",
                origin,
            )
        )
    for index, fields in enumerate(records):
        kind = _get(fields, "RULEKIND") or _get(fields, "RuleKind") or ""
        name = _get(fields, "NAME") or _get(fields, "RuleName") or ""
        try:
            if summary:
                raise _Refusal("summary-form", "the value has no unit")
            mapped = _map_one(fields, index, origin, layers)
        except _Refusal as refusal:
            unmapped.append(Unmapped(index, kind, name, refusal.reason, refusal.detail))
            issues.append(
                text_issue(
                    "altium.rule.unmapped",
                    f"the rule {name!r} of kind {kind or '(none)'} is not mapped ({refusal.reason}): "
                    f"{refusal.detail}",
                    f"{origin}#{index}",
                )
            )
            continue
        rules += mapped
        rule_records += [index] * len(mapped)
    ruleset = RuleSet(id=derived_id("rst", BACKEND, origin), rules=tuple(rules))
    cells = _matrix_cells(records, frozenset(rule_records))
    return RuleMapping(ruleset, tuple(unmapped), tuple(issues), tuple(rule_records), cells)


__all__ = [
    "CELL_PAIR",
    "HEADER_KEYS",
    "ITEM_KINDS",
    "MATRIX_KINDS",
    "MATRIX_UNIT",
    "NOT_APPLYING",
    "PENDING_KINDS",
    "RULE_KIND_MAP",
    "UNJUDGED_PAIR",
    "UNMAPPED_REASONS",
    "Condition",
    "CopperLayer",
    "CopperLayers",
    "Field",
    "KindMap",
    "Matrix",
    "NeutralLimits",
    "RuleMapping",
    "Unmapped",
    "UnmappedReason",
    "map_rules",
    "matrix_problem",
    "read_matrix",
    "record_text",
]
