# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The differential pairs among the nets selected for routing (capability routing, "Pair selection for
routing"; change c0110).

Two nets form a pair by the name rule of ``model.pairs`` (change c0104), the rule by which KiCad's DRC
(``inDiffPair``) and its router find pairs: ``route`` reads KiCad's files, which hold no pair object. A
pair is routed as a pair only when both nets are candidates and share a class whose pair width and gap
are known; otherwise its candidates are left out with ``route.pair-skipped``, because half a pair routed
alone is uncoupled copper that blocks the other half.
"""

from __future__ import annotations

from collections.abc import Sequence

from fenolite.core.errors import Issue
from fenolite.core.units import Nm
from fenolite.model.circuit import Net, NetClass
from fenolite.model.design import Design
from fenolite.model.pairs import POSITIVE, coupled_name, pair_base, split_pair_name
from fenolite.model.rules import Rule, RuleSubject
from fenolite.routing.layers import DEFAULT_CLASS
from fenolite.routing.protocol import JobPair

SKEW_KIND = "diff_pair_skew"


def _precedence(rules: Sequence[Rule]) -> tuple[Rule, ...]:
    """The rules in the order they are lowered: priority 0 first, then descending priority (priority 1
    last), ties by name, then id; the later rule governs (``rules-model``, "Lowered rules follow
    priority"; ``H-K-DRU-ORDER``)."""
    return tuple(sorted(rules, key=lambda r: (r.priority != 0, -r.priority, r.name, r.id)))


def _class_of(net: Net, classes: dict[str, NetClass]) -> NetClass | None:
    return classes.get(net.netclass_id or "")


def _skipped(name: str, why: str, hint: str) -> Issue:
    return Issue(
        "route.pair-skipped",
        "warning",
        f"the pair {name} is not routed: {why}",
        name,
        hint=hint,
    )


def skew_max(design: Design, positive: str, netclass: str, base: str) -> Nm | None:
    """The ``max`` of the ``diff_pair_skew`` rule that governs the positive net of a pair: the last one, in
    lowered order, whose ``selector_a`` matches a track of the net, ignoring rules of severity ``ignore``;
    ``None`` without one."""
    if design.rules is None:
        return None
    subject = RuleSubject("track", net=positive, netclass=netclass, diff_pair=base)
    governing: Rule | None = None
    for rule in _precedence(design.rules.rules):
        if rule.kind == SKEW_KIND and rule.severity != "ignore" and rule.selector_a.matches(subject):
            governing = rule
    return None if governing is None else governing.max


def job_pairs(
    design: Design, candidates: Sequence[str]
) -> tuple[tuple[JobPair, ...], tuple[str, ...], tuple[Issue, ...]]:
    """The pairs among ``candidates``, the candidates that stay single nets (in their order), and one
    ``route.pair-skipped`` per pair left out. Equal inputs give equal results."""
    nets = {net.name: net for net in design.circuit.nets}
    classes = {item.id: item for item in design.circuit.netclasses}
    default = next((item for item in design.circuit.netclasses if item.name.casefold() == "default"), None)
    wanted = set(candidates)
    pairs: list[JobPair] = []
    issues: list[tuple[str, Issue]] = []
    left_out: set[str] = set()
    in_pair: set[str] = set()
    seen: set[str] = set()
    for name in candidates:
        if name in seen or name not in nets:
            continue
        split = split_pair_name(name)
        other = coupled_name(name)
        if split is None or other is None or other not in nets:
            continue  # a single net
        positive, negative = (name, other) if split.polarity in POSITIVE else (other, name)
        base = pair_base(positive, negative)
        if base is None:
            continue
        seen.update((positive, negative))
        label = f"{positive}/{negative}"
        hint = "select both nets of the pair, or pass --pairs-as-nets to route them as single nets"
        if other not in wanted:
            left_out.add(name)
            issues.append((positive, _skipped(label, f"only {name} is selected, {other} is not", hint)))
            continue
        first, second = _class_of(nets[positive], classes), _class_of(nets[negative], classes)
        if (first.id if first else None) != (second.id if second else None):
            names = (item.name if item else DEFAULT_CLASS for item in (first, second))
            left_out.update((positive, negative))
            issues.append(
                (
                    positive,
                    _skipped(
                        label,
                        "its nets are in different classes, {} and {}".format(*names),
                        "put both nets of the pair in one net class",
                    ),
                )
            )
            continue

        def value(key: str, netclass: NetClass | None = first) -> Nm | None:
            return getattr(netclass, key, None) or getattr(default, key, None)

        width, gap = value("diff_pair_width"), value("diff_pair_gap")
        if width is None or gap is None:
            missing = [what for what, found in (("gap", gap), ("width", width)) if found is None]
            class_label = first.name if first else DEFAULT_CLASS
            left_out.update((positive, negative))
            issues.append(
                (
                    positive,
                    _skipped(
                        label,
                        f"its class {class_label} and the Default class give no pair "
                        f"{' and no pair '.join(missing)}",
                        "set diff_pair_width and diff_pair_gap of the class",
                    ),
                )
            )
            continue
        in_pair.update((positive, negative))
        pairs.append(
            JobPair(
                label,
                positive,
                negative,
                width,
                gap,
                via_gap=value("diff_pair_via_gap"),
                skew_max=skew_max(design, positive, first.name if first else DEFAULT_CLASS, base),
            )
        )
    pairs.sort(key=lambda pair: pair.positive)
    singles = tuple(name for name in candidates if name not in in_pair and name not in left_out)
    ordered = tuple(issue for _, issue in sorted(issues, key=lambda item: item[0]))
    return tuple(pairs), singles, ordered


__all__ = ["SKEW_KIND", "job_pairs", "skew_max"]
