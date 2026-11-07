# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper narrower than the track width in force (change c0403).

The width in force for a track or an arc is the ``min`` of the governing ``track_width`` rule of the design:
the last rule in ``rule_precedence`` order whose selector selects the item and whose layers, if it names
any, hold the item's layer (``H-K-DRU-ORDER``). A governing rule of severity ``ignore`` silences the item.
The board-setup minimum is no floor over a governing rule: on ``kicad-cli`` 9.0.9 and 10.0.6 a board-wide
custom rule governs below every board-setup minimum (``H-K-PRO-MIN-RULE-2``;
``backends.kicad.lowering.FLOOR_OVER_RULES``). An item that no rule selects is not judged here.

Subjects are built as the copper check builds them (``ClearanceResolver.subject``): an arc is a ``track``,
an item without a net or class is in ``Default``, and the rule areas an item lies in come from
``checks.copper.track_areas`` when a rule names an area. The module imports no backend.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from fenolite.checks.clearance import ClearanceResolver, rule_precedence, selector_matches
from fenolite.checks.copper import NO_NET, track_areas
from fenolite.core.errors import Issue
from fenolite.core.units import Nm, format_length
from fenolite.model.board import Arc, Track
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSubject, Selector

TRACK_WIDTH = "copper.track-width"
"""The code of a finding of copper narrower than the governing ``track_width`` rule."""


def _names_area(selector: Selector | None) -> bool:
    if selector is None:
        return False
    if selector.op == "area":
        return True
    return any(_names_area(item) for item in selector.items)


@dataclass(frozen=True, slots=True)
class _Below:
    net: str
    rule: Rule
    width: Nm
    count: int


def track_width_findings(
    design: Design,
    *,
    ids: Collection[str] | None = None,
    code: str = TRACK_WIDTH,
    hint: str = "",
) -> tuple[Issue, ...]:
    """One finding per net and governing ``track_width`` rule whose tracks or arcs are narrower than the
    rule's ``min``: it names the narrowest width, the rule and its ``min``, how many items are below, and
    has ``where`` the net name (``NO_NET`` for copper on no net). The severity is the rule's (``error`` or
    ``warning``). ``ids`` limits the judgement to the items of those entity ids (the copper a route adds);
    ``code`` and ``hint`` are those of the caller's own code table. Findings come in (where, message) order.
    """
    board = design.board
    if board is None or design.rules is None:
        return ()
    ordered = rule_precedence(
        [r for r in design.rules.rules if r.kind == "track_width" and r.min is not None]
    )
    if not ordered:
        return ()
    candidates = tuple(
        (rule, frozenset(layer.casefold() for layer in rule.layers)) for rule in reversed(ordered)
    )
    """The ``track_width`` rules with a ``min``, the governing one first."""
    areas = (
        track_areas(design)
        if any(_names_area(rule.selector_a) or _names_area(rule.selector_b) for rule in ordered)
        else {}
    )
    resolver = ClearanceResolver(design)
    names = {net.id: net.name for net in design.circuit.nets}
    below: dict[tuple[str, str], _Below] = {}
    governing: dict[RuleSubject, Rule | None] = {}
    items: tuple[Track | Arc, ...] = (*board.tracks, *board.arcs)
    for item in items:
        if ids is not None and item.id not in ids:
            continue
        kind = "track" if isinstance(item, Track) else "arc"
        subject = resolver.subject(
            kind,
            item.net_id,
            ref=None,
            layer=item.layer,
            areas=areas.get((item.id, item.layer), frozenset()),
        )
        if subject not in governing:
            layer = item.layer.casefold()
            governing[subject] = next(
                (
                    rule
                    for rule, layers in candidates
                    if (not layers or layer in layers) and selector_matches(rule.selector_a, subject)
                ),
                None,
            )
        rule = governing[subject]
        if rule is None or rule.severity == "ignore" or rule.min is None or item.width >= rule.min:
            continue
        net = names.get(item.net_id, item.net_id) if item.net_id is not None else NO_NET
        key = (net, rule.id)
        found = below.get(key)
        below[key] = (
            _Below(net, rule, item.width, 1)
            if found is None
            else _Below(net, rule, min(found.width, item.width), found.count + 1)
        )
    issues = [
        Issue(
            code,
            "warning" if row.rule.severity == "warning" else "error",
            f"net {row.net} has {row.count} track(s) or arc(s) narrower than the "
            f"{format_length(row.rule.min or 0)} min of track_width rule {row.rule.name!r}; "
            f"the narrowest is {format_length(row.width)}",
            row.net,
            hint=hint or "widen the copper, or change the rule; KiCad's DRC reports it as track_width",
        )
        for row in below.values()
    ]
    return tuple(sorted(issues, key=lambda issue: (issue.where, issue.message)))


__all__ = ["NO_NET", "TRACK_WIDTH", "track_width_findings"]
