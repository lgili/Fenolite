# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Voltage propagation through links (change c0274; capability verification-loop, "Voltage propagation
through links" and "Origins of applied values"; ``docs/contracts.md``, "Propagation through links";
hypothesis ``H-G-CIRCUIT-PROPAGATION``).

A **link** is a part with exactly two nets whose class (``fenolite.roles.classify``, injected by the command)
is ``ferrite``, ``fuse`` or ``net_tie``, a ``jumper`` whose class the user stated (``design.part_class``: a
stated jumper is a closed one), or a ``resistor`` or ``shunt`` whose value range is exactly 0 Ω. Nothing else
is crossed: no inductor, regulator, diode or resistor above 0 Ω.

After the stated sources of ``values.resolve``, each net without a stated voltage takes the hull of the stated
voltages of the nets it reaches through links, breadth first in net-name order, stopping at a stated net. The
range is the source's: no drop is subtracted (a later change may, once records state a DC resistance). Two
stated nets joined by links whose ranges do not overlap give ``circuit.value-conflict`` naming the links.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from fenolite.checks.circuit.rails import Propagated, View, bounds
from fenolite.checks.circuit.values import Value
from fenolite.checks.codes import issue
from fenolite.core.errors import Issue
from fenolite.core.requirement_table import Origin
from fenolite.model.circuit import Component
from fenolite.model.design import Design

HYPOTHESIS = "H-G-CIRCUIT-PROPAGATION"
LINK_CLASSES: frozenset[str] = frozenset({"ferrite", "fuse", "net_tie"})
"""The classes whose two-net parts are links whatever states them."""
STATED_LINK = "jumper"
"""The class that is a link only when the user states it (a closed jumper)."""
ZERO_OHM_CLASSES: frozenset[str] = frozenset({"resistor", "shunt"})
"""The classes that are links when their value range is exactly 0 Ω."""


@dataclass(frozen=True, slots=True)
class Link:
    """One link: the part's reference and its two net ids (sorted)."""

    ref: str
    nets: tuple[str, str]


@dataclass(slots=True)
class Propagation:
    """The voltages taken through links (net id → value) and the conflicts found."""

    values: dict[str, Propagated] = field(default_factory=lambda: {})
    issues: list[Issue] = field(default_factory=lambda: [])


def _zero_ohm(component: Component) -> bool:
    value = component.value_range
    if value is None or value.unit != "ohm":
        return False
    low, high = bounds(value)
    return low == 0 and high == 0


def links(design: Design, view: View, classes: Mapping[str, str | None]) -> list[Link]:
    """The links of ``design`` (module docstring), sorted by reference; ``classes`` maps a component id to its
    class."""
    roles = design.rules.roles if design.rules is not None else None
    stated = {found.ref: found.cls for found in (roles.classes if roles is not None else ())}
    found: list[Link] = []
    for component in sorted(design.circuit.components, key=lambda c: c.ref):
        nets = sorted(set(view.pins.get(component.id, [])))
        if len(nets) != 2:
            continue
        cls = classes.get(component.id)
        if (
            cls in LINK_CLASSES
            or stated.get(component.ref) == STATED_LINK
            or (cls in ZERO_OHM_CLASSES and _zero_ohm(component))
        ):
            found.append(Link(component.ref, (nets[0], nets[1])))
    return found


def _overlap(a: Value, b: Value) -> bool:
    if a.high is not None and b.low is not None and a.high < b.low:
        return False
    return not (b.high is not None and a.low is not None and b.high < a.low)


def propagate(view: View, stated: Mapping[str, Value], found: Sequence[Link]) -> Propagation:
    """The voltages of the nets without a stated one that ``found`` links reach from ``stated`` (net id →
    value), and a ``circuit.value-conflict`` per pair of linked stated nets whose ranges do not overlap."""
    result = Propagation()
    adjacent: dict[str, list[tuple[str, str]]] = {}
    for link in found:
        first, second = link.nets
        adjacent.setdefault(first, []).append((second, link.ref))
        adjacent.setdefault(second, []).append((first, link.ref))
    for net in adjacent:
        adjacent[net].sort(key=lambda pair: (view.net_name(pair[0]), pair[1]))
    nets = sorted(adjacent, key=view.net_name)
    for start in nets:
        if start in stated:
            continue
        reached = _reach(start, adjacent, stated)
        if not reached:
            continue
        values = [stated[net] for net, _via in reached]
        low = None if any(v.low is None for v in values) else min(v.low for v in values if v.low is not None)
        high = (
            None if any(v.high is None for v in values) else max(v.high for v in values if v.high is not None)
        )
        source_net, via = reached[0]
        origin = Origin("propagated", via, view.net_name(source_net))
        basis = origin.text()
        source = "user" if any(v.source == "user" for v in values) else values[0].source
        rigs = frozenset[str]().union(*(v.rigs for v in values))
        result.values[start] = Propagated(low, high, source, basis, origin, rigs)
    reported: set[tuple[str, str]] = set()
    for start in nets:
        if start not in stated:
            continue
        for other, via in _reach(start, adjacent, stated):
            pair = tuple(sorted((start, other), key=view.net_name))
            if pair in reported or _overlap(stated[start], stated[other]):
                continue
            reported.add((pair[0], pair[1]))
            a, b = stated[pair[0]], stated[pair[1]]
            names = (view.net_name(pair[0]), view.net_name(pair[1]))
            result.issues.append(
                issue(
                    "circuit.value-conflict",
                    f"{names[0]} and {names[1]} are joined by {', '.join(via)}: {a.basis} gives "
                    f"{a.bound('volt').text()} and {b.basis} gives {b.bound('volt').text()}",
                    where=names[0],
                    hint="state one voltage for the linked nets, or correct the link",
                )
            )
    return result


def _reach(
    start: str, adjacent: Mapping[str, Sequence[tuple[str, str]]], stated: Mapping[str, Value]
) -> list[tuple[str, tuple[str, ...]]]:
    """The stated nets reached from ``start`` breadth first through links, never through a stated net, each
    with the link references of its path, in the order reached."""
    seen = {start}
    queue: deque[tuple[str, tuple[str, ...]]] = deque([(start, ())])
    found: list[tuple[str, tuple[str, ...]]] = []
    while queue:
        net, via = queue.popleft()
        for other, ref in adjacent.get(net, ()):
            if other in seen:
                continue
            seen.add(other)
            path = (*via, ref)
            if other in stated:
                found.append((other, path))
            else:
                queue.append((other, path))
    return found


def as_value(found: Propagated) -> Value:
    """A propagated voltage as an applied value of ``values.Values``."""
    return Value(found.low, found.high, found.source, found.basis, "propagated", found.rigs, found.origin)


__all__ = ["HYPOTHESIS", "LINK_CLASSES", "Link", "Propagation", "as_value", "links", "propagate"]
