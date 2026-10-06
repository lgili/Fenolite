# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The clearance in force between two copper items on a layer (capability copper-check, "Clearance in
force").

The value is defined from the model alone: the ``clearance`` rules of the design, the clearance of the two
nets' classes, the board minimum that the caller passes, and, for a pair of one zone fill and one other
item, the zone's own clearance. How they combine follows what KiCad is measured to do
(``docs/formats/kicad/copper.md``): the last matching rule governs, and two switches say whether a governing
rule also replaces the class clearances (and with them the zone's clearance, ``H-K-COPPER-ZONECLR``) and
whether the board minimum also raises a rule's value. A backend fills the switches for the tool version a
board is judged against (``backends.base.DesignRules``); this module imports no backend.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from fenolite.core.units import Nm
from fenolite.model.design import Design
from fenolite.model.pairs import coupled_name, net_bases
from fenolite.model.rules import LEAF_OPS, Rule, RuleSeverity, RuleSubject, Selector

CopperKind = Literal["track", "arc", "via", "pad", "fill", "zone", "keepout"]
"""The kinds of copper items; a rule sees an arc as a ``track`` and a fill as a ``zone``. ``keepout`` names
the area of a ``copper.keepout`` finding; no rule subject takes it."""
ITEM_KINDS: dict[str, str] = {
    "track": "track",
    "arc": "track",
    "via": "via",
    "pad": "pad",
    "fill": "zone",
    "zone": "zone",
}
DEFAULT_CLASS = "Default"
"""The class of a net without one, when the design holds a class of this name."""
PAIR_GAP_SOURCE = "pair-gap"
"""The prefix of the source of a value that is the pair gap of a class: ``pair-gap:<class name>``."""
ZONE_SOURCE = "zone"
"""The source of a value that is the own clearance of the zone of a fill."""


@dataclass(frozen=True, slots=True)
class Clearance:
    """What ``resolve`` returns: the value in nanometres, the severity of a finding below it, and where the
    value comes from (``rule:<name>``, ``class:<name>``, ``pair-gap:<class name>``, ``zone`` or ``floor``).

    ``value`` is ``None`` when the pair is not judged for clearance: ``source`` is then ``rule:<name>`` for a
    governing rule of severity ``ignore``, and empty when nothing sets a clearance.
    """

    value: Nm | None
    severity: Literal["error", "warning"] | None
    source: str = ""

    @property
    def unset(self) -> bool:
        """Nothing sets a clearance for the pair (no rule silenced it either)."""
        return self.value is None and not self.source


UNSET = Clearance(None, None)


@dataclass(frozen=True, slots=True)
class ClearanceCandidate:
    """An immutable value candidate; rule identity never depends on its display name."""

    source: str
    value: Nm | None
    severity: RuleSeverity | None
    rule_id: str | None = None
    priority: int | None = None
    layers: tuple[str, ...] = ()
    selector_a: Selector | None = None
    selector_b: Selector | None = None


@dataclass(frozen=True, slots=True)
class ClearanceExplanation:
    """Matched subjects and candidate values, without entities or design advice."""

    subjects: tuple[RuleSubject, RuleSubject]
    candidates: tuple[ClearanceCandidate, ...]
    rules_over_classes: bool
    floor_over_rules: bool
    governing: Clearance


def rule_precedence(rules: Sequence[Rule]) -> tuple[Rule, ...]:
    """The rules in the order a backend writes them: priority 0 first, then descending priority (priority 1
    last); ties by name, then id. The later rule governs (``H-K-DRU-ORDER``)."""
    return tuple(sorted(rules, key=lambda r: (r.priority != 0, -r.priority, r.name, r.id)))


def _fold(text: str | None) -> str | None:
    return None if text is None else text.casefold()


def _fold_selector(selector: Selector) -> Selector:
    """``selector`` with every leaf value case-folded: names compare without regard to letter case. An
    ``area`` leaf is kept as written: KiCad compares area names with letter case (``H-K-AREA-COND``). A
    ``diff_pair`` leaf keeps its value too, because KiCad compares a pair base with its letter case
    (``H-K-DRU-PAIRSEL``)."""
    if selector.op in ("area", "diff_pair"):
        return selector
    if selector.op in LEAF_OPS:
        return dataclasses.replace(selector, value=selector.value.casefold())
    if selector.items:
        return dataclasses.replace(selector, items=tuple(_fold_selector(item) for item in selector.items))
    return selector


def _fold_subject(subject: RuleSubject) -> RuleSubject:
    return RuleSubject(
        item_kind=subject.item_kind.casefold(),
        net=_fold(subject.net),
        netclass=_fold(subject.netclass),
        ref=_fold(subject.ref),
        layer=_fold(subject.layer),
        areas=subject.areas,
        diff_pair=subject.diff_pair,
    )


def selector_matches(selector: Selector, subject: RuleSubject) -> bool:
    """Whether ``selector`` selects ``subject``, names compared as the clearance rules compare them: without
    regard to letter case, except an ``area`` leaf and a ``diff_pair`` leaf (``_fold_selector``). The
    length stage (``checks.length``) matches its rules with it."""
    return _fold_selector(selector).matches(_fold_subject(subject))


@dataclass(frozen=True, slots=True)
class _Candidate:
    rule: Rule
    selector_a: Selector
    selector_b: Selector | None
    layers: frozenset[str]

    def matches(self, a: RuleSubject, b: RuleSubject) -> bool:
        if self.layers and a.layer not in self.layers:
            return False
        first, second = self.selector_a, self.selector_b
        if second is None:
            return first.matches(a) or first.matches(b)
        return (first.matches(a) and second.matches(b)) or (first.matches(b) and second.matches(a))


class ClearanceResolver:
    """The clearance in force for pairs of copper items of one design."""

    def __init__(
        self,
        design: Design,
        *,
        min_clearance: Nm | None = None,
        rules_over_classes: bool = True,
        floor_over_rules: bool = False,
    ) -> None:
        circuit = design.circuit
        classes = {netclass.id: netclass for netclass in circuit.netclasses}
        named = {netclass.name: netclass for netclass in circuit.netclasses}
        self._class_values: dict[str, Nm] = {
            name: netclass.clearance for name, netclass in named.items() if netclass.clearance is not None
        }
        self._pair_gaps: dict[str, Nm] = {
            name: netclass.diff_pair_gap
            for name, netclass in named.items()
            if netclass.diff_pair_gap is not None
            and netclass.clearance is not None
            and netclass.diff_pair_gap < netclass.clearance
        }
        """Class name → its pair gap, for the classes whose gap is below their clearance."""
        self._bases = net_bases(net.name for net in circuit.nets)
        self._nets: dict[str, tuple[str, str]] = {}
        for net in circuit.nets:
            netclass = classes.get(net.netclass_id) if net.netclass_id is not None else None
            self._nets[net.id] = (net.name, netclass.name if netclass is not None else DEFAULT_CLASS)
        rules = design.rules.rules if design.rules is not None else ()
        ordered = rule_precedence([r for r in rules if r.kind == "clearance" and r.min is not None])
        self._candidates = tuple(
            _Candidate(
                rule,
                _fold_selector(rule.selector_a),
                None if rule.selector_b is None else _fold_selector(rule.selector_b),
                frozenset(layer.casefold() for layer in rule.layers),
            )
            for rule in reversed(ordered)
        )
        """The clearance rules with a ``min``, the governing one first."""
        self._floor: Nm | None = min_clearance if min_clearance is not None and min_clearance > 0 else None
        self._rules_over_classes = rules_over_classes
        self._floor_over_rules = floor_over_rules
        self._memo: dict[tuple[RuleSubject, RuleSubject, Nm | None], Clearance] = {}
        values = [
            c.rule.min for c in self._candidates if c.rule.min is not None and c.rule.severity != "ignore"
        ]
        values += list(self._class_values.values())
        if self._floor is not None:
            values.append(self._floor)
        if design.board is not None:
            values += [
                zone.settings.clearance
                for zone in design.board.zones
                if zone.fills and zone.settings.clearance > 0
            ]
        self.max_value: Nm = max(values, default=0)
        """The largest value ``resolve`` can return for the design, the own clearance of every zone that
        has fills included, or 0."""

    def subject(
        self,
        kind: CopperKind,
        net_id: str | None,
        *,
        ref: str | None,
        layer: str,
        areas: frozenset[str] = frozenset(),
    ) -> RuleSubject:
        """The subject of a copper item of ``kind`` on ``layer``: its net name and class name, the
        component reference for a pad, and the names of the rule areas it lies in on that layer. An item
        without a net, or whose net has no class, is in the class named ``Default``. ``diff_pair`` is the
        base of the net when the design holds its coupled net."""
        name, netclass = (
            self._nets.get(net_id, (None, DEFAULT_CLASS)) if net_id is not None else (None, DEFAULT_CLASS)
        )
        return RuleSubject(
            item_kind=ITEM_KINDS[kind],
            net=name,
            netclass=netclass,
            ref=ref,
            layer=layer,
            areas=areas,
            diff_pair=self._bases.get(name) if name is not None else None,
        )

    def _class_candidates(self, a: RuleSubject, b: RuleSubject) -> tuple[tuple[Nm, str], ...]:
        return tuple(
            (self._class_values[name], name)
            for name in sorted({n for n in (a.netclass, b.netclass) if n is not None})
            if name in self._class_values
        )

    def _class_value(self, a: RuleSubject, b: RuleSubject) -> tuple[Nm, str] | None:
        """The larger clearance of the two subjects' classes that set one, and the name of that class."""
        found = self._class_candidates(a, b)
        if not found:
            return None
        value = max(v for v, _ in found)
        return value, min(name for v, name in found if v == value)

    def _pair_gap(self, a: RuleSubject, b: RuleSubject) -> tuple[Nm, str] | None:
        """The pair gap of the class of two subjects on the two nets of one pair, and the name of that
        class, when the gap is below the class clearance: KiCad then judges the pair by the gap
        (``H-K-PRO-PAIR``)."""
        if a.diff_pair is None or a.diff_pair != b.diff_pair or a.net is None or a.net == b.net:
            return None
        if a.netclass is None or a.netclass != b.netclass or coupled_name(a.net) != b.net:
            return None
        gap = self._pair_gaps.get(a.netclass)
        return None if gap is None else (gap, a.netclass)

    def resolve(self, a: RuleSubject, b: RuleSubject, *, zone_clearance: Nm | None = None) -> Clearance:
        """The clearance in force between two subjects on the same layer; the same for ``(b, a)``.

        ``zone_clearance`` is the own clearance of the zone of a fill, for a pair of one fill and one item
        that is not a fill: it counts as a class value does, so the largest of it, the class value and the
        board minimum governs without a rule, and a governing rule replaces it wherever it replaces a
        class value."""
        zone = zone_clearance if zone_clearance is not None and zone_clearance > 0 else None
        key = (a, b, zone)
        cached = self._memo.get(key)
        if cached is None:
            cached = self._resolve(a, b, zone)
            self._memo[key] = cached
            self._memo[(b, a, zone)] = cached
        return cached

    def _resolve(self, a: RuleSubject, b: RuleSubject, zone: Nm | None) -> Clearance:
        folded_a, folded_b = _fold_subject(a), _fold_subject(b)
        governing = next((c.rule for c in self._candidates if c.matches(folded_a, folded_b)), None)
        classes = self._class_value(a, b)
        floor = self._floor
        # the values a rule may replace, the class first: among equal values the class names the source
        kept: list[Clearance] = []
        pair = self._pair_gap(a, b)
        if pair is not None:
            kept.append(Clearance(pair[0], "error", f"{PAIR_GAP_SOURCE}:{pair[1]}"))
        elif classes is not None:
            kept.append(Clearance(classes[0], "error", f"class:{classes[1]}"))
        if zone is not None:
            kept.append(Clearance(zone, "error", ZONE_SOURCE))
        if governing is None:
            if floor is not None:
                kept.append(Clearance(floor, "error", "floor"))
            found = UNSET
            for candidate in kept:
                if found.value is None or (candidate.value is not None and candidate.value > found.value):
                    found = candidate
            return found
        if governing.severity == "ignore":
            return Clearance(None, None, f"rule:{governing.name}")
        assert governing.min is not None
        found = Clearance(governing.min, governing.severity, f"rule:{governing.name}")
        if not self._rules_over_classes:
            for candidate in kept:
                if candidate.value is not None and found.value is not None and candidate.value > found.value:
                    found = candidate
        assert found.value is not None
        if self._floor_over_rules and floor is not None and floor > found.value:
            found = Clearance(floor, "error", "floor")
        return found

    def explain(
        self, a: RuleSubject, b: RuleSubject, *, zone_clearance: Nm | None = None
    ) -> ClearanceExplanation:
        """Explain the same resolution, including overshadowed matching rules and class values."""
        folded_a, folded_b = _fold_subject(a), _fold_subject(b)
        rows = [
            ClearanceCandidate(
                source=f"rule:{c.rule.name}",
                value=c.rule.min,
                severity=c.rule.severity,
                rule_id=c.rule.id,
                priority=c.rule.priority,
                layers=c.rule.layers,
                selector_a=c.rule.selector_a,
                selector_b=c.rule.selector_b,
            )
            for c in reversed(self._candidates)
            if c.matches(folded_a, folded_b)
        ]
        rows.extend(
            ClearanceCandidate(f"class:{name}", value, "error")
            for value, name in self._class_candidates(a, b)
        )
        if self._floor is not None:
            rows.append(ClearanceCandidate("floor", self._floor, "error"))
        if zone_clearance is not None and zone_clearance > 0:
            rows.append(ClearanceCandidate(ZONE_SOURCE, zone_clearance, "error"))
        return ClearanceExplanation(
            (a, b),
            tuple(rows),
            self._rules_over_classes,
            self._floor_over_rules,
            self.resolve(a, b, zone_clearance=zone_clearance),
        )


__all__ = [
    "DEFAULT_CLASS",
    "ITEM_KINDS",
    "PAIR_GAP_SOURCE",
    "UNSET",
    "ZONE_SOURCE",
    "Clearance",
    "ClearanceCandidate",
    "ClearanceExplanation",
    "ClearanceResolver",
    "CopperKind",
    "rule_precedence",
    "selector_matches",
]
