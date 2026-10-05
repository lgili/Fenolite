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
"""

# evidence: see import_evidence, read.project

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from fenolite.backends.altium.read.proptext import parse_length
from fenolite.backends.altium.read.scope import parse_scope
from fenolite.backends.altium.read.textfile import text_issue
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm
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
    key ``same_as``."""

    key: str
    values: tuple[str, ...] | None = None
    required: bool = False
    same_as: str = ""


@dataclass(frozen=True, slots=True)
class KindMap:
    """How one Altium rule kind maps: its neutral rules, the ``NETSCOPE`` it needs, its further
    conditions, and whether it is binary (a second scope)."""

    rules: tuple[NeutralLimits, ...]
    net_scope: str
    conditions: tuple[Condition, ...] = ()
    binary: bool = False

    @property
    def keys(self) -> frozenset[str]:
        """Every key of the kind: the limit keys and the condition keys."""
        return frozenset(key for limits in self.rules for key in limits.keys) | {
            c.key for c in self.conditions
        }


RULE_KIND_MAP: dict[str, KindMap] = {
    "Clearance": KindMap(
        (NeutralLimits("clearance", "GAP", None, None),),
        "DifferentNets",
        (
            Condition("OBJECTCLEARANCES", ("",)),
            Condition("GENERICCLEARANCE", same_as="GAP"),
            Condition("IGNOREPADTOPADCLEARANCEINFOOTPRINT", ("FALSE",)),
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
}
"""The closed table of the kinds that map (``rule-file.md``, "Rule kinds that map";
``H-A-RD-PRJ-RULE-MAP``)."""
PENDING_KINDS: dict[str, RuleKind] = {"BoardOutlineClearance": "edge_clearance"}
"""Kinds with a neutral counterpart but no permitted source for their keys: reported apart."""

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
)
"""The reasons in the order they are checked: the first one that holds is reported."""


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
        if condition.same_as:
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
    if kind == "Clearance" and not _has(fields, "GAP"):
        raise _Refusal("value", "the Clearance has no GAP")
    if not groups:
        raise _Refusal("value", f"the {kind} gives no limit")
    return groups


def _scopes(fields: Sequence[Field], table: KindMap) -> tuple[Selector, Selector | None]:
    first = _get(fields, "SCOPE1EXPRESSION")
    second = _get(fields, "SCOPE2EXPRESSION")
    if first is None:
        raise _Refusal("scope", "the record has no SCOPE1EXPRESSION")
    selector_a = parse_scope(first)
    if isinstance(selector_a, str):
        raise _Refusal("scope", f"SCOPE1EXPRESSION: {selector_a}")
    if not table.binary:
        if second is None or second.strip() != ALL:
            raise _Refusal("scope", "SCOPE2EXPRESSION is not All for a unary rule")
        return selector_a, None
    if second is None:
        raise _Refusal("scope", "the record has no SCOPE2EXPRESSION")
    if second.strip() == ALL:
        return selector_a, None
    selector_b = parse_scope(second)
    if isinstance(selector_b, str):
        raise _Refusal("scope", f"SCOPE2EXPRESSION: {selector_b}")
    return selector_a, selector_b


def _map_one(fields: Sequence[Field], index: int, origin: str) -> list[Rule]:
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
    selector_a, selector_b = _scopes(fields, table)
    unique_id = _get(fields, "UNIQUEID")
    native = {BACKEND: unique_id} if unique_id else {}
    bag = ExtBag(payload=(("record", record_text(fields)),))
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
                layers=(),
                min=low,
                opt=preferred,
                max=high,
                severity="error",
                priority=priority,
            )
        )
    return rules


def map_rules(records: Sequence[Sequence[Field]], *, origin: str, summary: bool = False) -> RuleMapping:
    """Map the field lists ``records`` onto neutral rules. Every record is either the source of one or
    two rules (``RuleMapping.sources``) or one ``Unmapped`` with the first reason of ``UNMAPPED_REASONS``
    that holds. ``origin`` names the source in ids and issue locations (``<origin>#<index>``). With
    ``summary`` (the records of a summary-form file) no record maps and one info
    ``altium.rule.summary-form`` comes first."""
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
            mapped = _map_one(fields, index, origin)
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
    return RuleMapping(ruleset, tuple(unmapped), tuple(issues), tuple(rule_records))


__all__ = [
    "HEADER_KEYS",
    "PENDING_KINDS",
    "RULE_KIND_MAP",
    "UNMAPPED_REASONS",
    "Condition",
    "Field",
    "KindMap",
    "NeutralLimits",
    "RuleMapping",
    "Unmapped",
    "UnmappedReason",
    "map_rules",
    "record_text",
]
