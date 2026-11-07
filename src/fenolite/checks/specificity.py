# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Explain overlapping rules using the exact precedence of the tool-free rule checks."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from fenolite.backends.base import BoardPad
from fenolite.checks.clearance import DEFAULT_CLASS, rule_precedence, selector_matches
from fenolite.checks.codes import issue
from fenolite.checks.copper import item_subjects
from fenolite.checks.padpath import model_pads
from fenolite.core.errors import Issue
from fenolite.model.design import Design
from fenolite.model.pairs import net_bases
from fenolite.model.rules import Rule, RuleSubject, Selector, selector_rank


def rank(selector: Selector) -> int:
    """ALL/not 0; area/item/layer 1; netclass 2; net glob 3; pair/ref 4; exact net 5."""
    return selector_rank(selector)


def rule_rank(rule: Rule) -> int:
    return rank(rule.selector_a) + (rank(rule.selector_b) if rule.selector_b is not None else 0)


def subjects(
    design: Design, *, pads: Sequence[BoardPad] | None = None
) -> tuple[tuple[str, RuleSubject], ...]:
    classes = {row.id: row.name for row in design.circuit.netclasses}
    nets = {net.id: net for net in design.circuit.nets}
    bases = net_bases(net.name for net in nets.values())
    rows: dict[str, RuleSubject] = {}

    def subject(
        net_id: str | None, kind: str, *, ref: str | None = None, layer: str | None = None
    ) -> RuleSubject:
        net = nets.get(net_id or "")
        return RuleSubject(
            kind,
            net.name if net else None,
            classes.get(net.netclass_id or "", DEFAULT_CLASS) if net else None,
            ref=ref,
            layer=layer,
            diff_pair=bases.get(net.name) if net else None,
        )

    for net in nets.values():
        rows[net.name] = subject(net.id, "track")
    for name, actual in item_subjects(design, pads=model_pads(design) if pads is None else pads):
        if actual.item_kind in ("track", "via"):
            area = "{" + ",".join(sorted(actual.areas)) + "}" if actual.areas else ""
            name = f"{actual.net}:{actual.item_kind}@{actual.layer}{area}"
        rows[name] = actual
    return tuple(sorted(rows.items()))


def _matches(rule: Rule, subject: RuleSubject, other: RuleSubject | None = None) -> bool:
    if rule.layers and subject.layer not in rule.layers:
        return False
    if rule.selector_b is None:
        return selector_matches(rule.selector_a, subject) or (
            other is not None and selector_matches(rule.selector_a, other)
        )
    if other is None:
        return False
    return (selector_matches(rule.selector_a, subject) and selector_matches(rule.selector_b, other)) or (
        selector_matches(rule.selector_a, other) and selector_matches(rule.selector_b, subject)
    )


def overlaps(
    design: Design, *, pads: Sequence[BoardPad] | None = None
) -> tuple[tuple[str, str, tuple[Rule, ...]], ...]:
    by_kind: dict[str, list[Rule]] = defaultdict(list)
    for rule in () if design.rules is None else design.rules.rules:
        by_kind[rule.kind].append(rule)
    rows: list[tuple[str, str, tuple[Rule, ...]]] = []
    if not any(len(rules) >= 2 for rules in by_kind.values()):
        return ()
    candidates = subjects(design, pads=pads)
    for kind, rules in sorted(by_kind.items()):
        if len(rules) < 2:
            continue
        ordered = rule_precedence(rules)
        for name, subject in candidates:
            matched = tuple(rule for rule in ordered if _matches(rule, subject))
            if len(matched) >= 2:
                rows.append((name, kind, matched))
        if any(rule.selector_b is not None for rule in rules):
            # Objects indistinguishable to these selectors have the same binary outcome. One stable
            # representative per predicate vector proves every overlap without a board-size square.
            contexts: dict[tuple[bool, ...], tuple[str, RuleSubject]] = {}
            for name, subject in candidates:
                signature = tuple(
                    value
                    for rule in ordered
                    for value in (
                        selector_matches(rule.selector_a, subject),
                        rule.selector_b is not None and selector_matches(rule.selector_b, subject),
                        not rule.layers or subject.layer in rule.layers,
                    )
                )
                contexts.setdefault(signature, (name, subject))
            representatives = sorted(contexts.values(), key=lambda row: row[0])
            for index, (name, subject) in enumerate(representatives):
                for other_name, other in representatives[index:]:
                    matched = tuple(rule for rule in ordered if _matches(rule, subject, other))
                    if len(matched) >= 2:
                        rows.append((f"{name}~{other_name}", kind, matched))
    return tuple(sorted(rows, key=lambda row: row[:2]))


def _row(rule: Rule) -> dict[str, object]:
    return {"name": rule.name, "id": rule.id, "priority": rule.priority, "rank": rule_rank(rule)}


def explain_rules(design: Design, *, pads: Sequence[BoardPad] | None = None) -> list[dict[str, object]]:
    """Stable subject/kind rows: the last match governs, and overrides retain lowering order."""
    return [
        {
            "subject": subject,
            "kind": kind,
            "governing": _row(rules[-1]),
            "rank": rule_rank(rules[-1]),
            "overrides": [_row(rule) for rule in rules[:-1]],
        }
        for subject, kind, rules in overlaps(design, pads=pads)
    ]


def shadowed_rules(design: Design, *, pads: Sequence[BoardPad] | None = None) -> tuple[Issue, ...]:
    seen: set[tuple[str, str]] = set()
    found: list[Issue] = []
    for subject, kind, rules in overlaps(design, pads=pads):
        governing = rules[-1]
        for overridden in rules[:-1]:
            key = (governing.id, overridden.id)
            if key in seen or rule_rank(governing) >= rule_rank(overridden):
                continue
            seen.add(key)
            found.append(
                issue(
                    "rules.shadowed",
                    f"{kind}: governing rule {governing.name!r} (rank {rule_rank(governing)}) "
                    f"overrides {overridden.name!r} (rank {rule_rank(overridden)}) on {subject}",
                    where=f"{subject}, {governing.name}, {overridden.name}",
                    hint='set priority= explicitly or call design.rules.precedence("specificity")',
                )
            )
    return tuple(found)


__all__ = ["explain_rules", "overlaps", "rank", "rule_rank", "shadowed_rules", "subjects"]
