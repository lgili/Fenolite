# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Neutral design rules: kind, selectors, layers, min/opt/max, severity and explicit priority.

Backends lower rules to their own form (a KiCad custom-rules file, the second backend's rule
records). Priority 1 is the highest; backends preserve that meaning when lowering.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Literal

from fenolite.core.units import Nm
from fenolite.model.base import Entity
from fenolite.model.pairs import base_matches

RuleKind = Literal[
    "clearance",
    "track_width",
    "via_diameter",
    "via_drill",
    "hole_size",
    "edge_clearance",
    "hole_to_hole",
    "hole_clearance",
    "annular_width",
    "courtyard_clearance",
    "silk_clearance",
    "creepage",
    "no_tracks",
    "diff_pair_gap",
    "diff_pair_uncoupled",
    "skew",
    "diff_pair_skew",
    "length",
]
"""The first six kinds are those of v0.1; the next six were added by change c0071, and ``no_tracks`` (no
track or arc of the selected items on the rule's layers; it takes no limit) by change c0107. The last five,
the pair and length kinds, were added by change c0104 (``skew`` compares every net a rule selects with the
longest of them, ``diff_pair_skew`` the two nets of each pair it selects). Which sides, selector ops and
layer clause a kind takes, and for which targets it is written, is the backend's to say
(``backends.kicad.rulemap.KIND_SELECTORS`` and ``KIND_SUPPORT``)."""
RuleSeverity = Literal["error", "warning", "ignore"]
SelectorOp = Literal[
    "all", "net", "netclass", "ref", "layer", "item_kind", "area", "diff_pair", "and", "or", "not"
]
LEAF_OPS = ("net", "netclass", "ref", "layer", "item_kind", "area", "diff_pair")
"""The leaves. The value of ``diff_pair`` is a pair base (``model.pairs``) or ``*``, compared with its
letter case; the value of ``area`` is the name of a rule area, compared with its letter case and with ``*``
as a glob; the other leaves hold globs over names."""


@dataclass(frozen=True, slots=True)
class RuleSubject:
    """The properties of one object a selector is evaluated against."""

    item_kind: str
    net: str | None = None
    netclass: str | None = None
    ref: str | None = None
    layer: str | None = None
    areas: frozenset[str] = frozenset()
    """The names of the rule areas the object lies in (letter case counts)."""
    #: The base of the subject's net when the design holds the coupled net (``model.pairs.net_bases``).
    diff_pair: str | None = None


@dataclass(frozen=True, slots=True)
class Selector:
    """A small predicate algebra. Leaf values are globs such as ``PWR_*`` or ``U*``."""

    op: SelectorOp
    value: str = ""
    items: tuple[Selector, ...] = field(default=(), metadata={"ordered": True})

    def __post_init__(self) -> None:
        if self.op in ("and", "or") and len(self.items) < 2:
            raise ValueError(f"selector '{self.op}' needs at least two items")
        if self.op == "not" and len(self.items) != 1:
            raise ValueError("selector 'not' needs exactly one item")
        if self.op in LEAF_OPS and not self.value:
            raise ValueError(f"selector '{self.op}' needs a value")
        if self.op in (*LEAF_OPS, "all") and self.items:
            raise ValueError(f"selector '{self.op}' takes no items")

    def matches(self, subject: RuleSubject) -> bool:
        match self.op:
            case "all":
                return True
            case "and":
                return all(item.matches(subject) for item in self.items)
            case "or":
                return any(item.matches(subject) for item in self.items)
            case "not":
                return not self.items[0].matches(subject)
            case "net":
                return _glob(subject.net, self.value)
            case "netclass":
                return _glob(subject.netclass, self.value)
            case "ref":
                return _glob(subject.ref, self.value)
            case "layer":
                return _glob(subject.layer, self.value)
            case "item_kind":
                return _glob(subject.item_kind, self.value)
            case "area":
                return any(fnmatch.fnmatchcase(name, self.value) for name in subject.areas)
            case "diff_pair":
                return base_matches(subject.diff_pair, self.value)


def _glob(value: str | None, pattern: str) -> bool:
    return value is not None and fnmatch.fnmatchcase(value, pattern)


@dataclass(frozen=True, slots=True)
class Rule(Entity):
    """One design rule. Binary rules (clearance, creepage) use ``selector_b`` for the second object."""

    name: str
    kind: RuleKind
    selector_a: Selector
    selector_b: Selector | None = None
    layers: tuple[str, ...] = ()
    min: Nm | None = None
    opt: Nm | None = None
    max: Nm | None = None
    severity: RuleSeverity = "error"
    priority: int = 0


PlacementSeverity = Literal["error", "warning"]
"""The severity of a placement rule. A rule that judges nothing (``ignore``) is not a value."""


@dataclass(frozen=True, slots=True)
class PadSelection:
    """Pads of one part, named by its component path.

    Every pad of the part, those of one ``number``, or the one at ``index`` among the pads of that number
    in the footprint's pad order.
    """

    path: str
    number: str = ""
    index: int | None = None

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("a pad selection needs a component path")
        if self.index is not None:
            if isinstance(self.index, bool) or self.index < 0:
                raise ValueError("the index of a pad selection is a non-negative integer")
            if not self.number:
                raise ValueError("the index of a pad selection needs a pad number")


@dataclass(frozen=True, slots=True)
class ProximityRule:
    """A placement rule: each part of ``parts`` stays near a pad of ``anchor``.

    A part keeps one of its selected pads within ``within`` (nm, pad centre to pad centre) of a selected
    pad of ``anchor``. A value object of the rules layer: its ``name`` is its key, it has no id and no
    ``RuleKind``, and no backend lowers it.
    """

    name: str
    parts: tuple[PadSelection, ...] = field(metadata={"ordered": True})
    anchor: tuple[PadSelection, ...] = field(metadata={"ordered": True})
    within: Nm
    severity: PlacementSeverity = "error"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("a proximity rule needs a name")
        if not self.parts:
            raise ValueError(f"proximity rule {self.name!r} names no part")
        if not self.anchor:
            raise ValueError(f"proximity rule {self.name!r} names no anchor")
        if isinstance(self.within, bool) or self.within <= 0:
            raise ValueError(f"proximity rule {self.name!r} needs a positive distance")
        if self.severity not in ("error", "warning"):
            raise ValueError(f"proximity rule {self.name!r}: severity is 'error' or 'warning'")


@dataclass(frozen=True, slots=True)
class HeightLimit:
    """A height limit: the parts under every rule area named ``area`` stay at most ``max`` tall.

    The height of a part is ``fenolite.model.board.outward_height`` of its footprint (change c0140). A
    value object of the rules layer: its ``area`` is its key, it has no id and no ``RuleKind``, and no
    backend lowers it.
    """

    area: str
    max: Nm
    severity: PlacementSeverity = "error"

    def __post_init__(self) -> None:
        if not self.area:
            raise ValueError("a height limit needs the name of a rule area")
        if isinstance(self.max, bool) or self.max <= 0:
            raise ValueError(f"height limit {self.area!r} needs a positive height")
        if self.severity not in ("error", "warning"):
            raise ValueError(f"height limit {self.area!r}: severity is 'error' or 'warning'")


@dataclass(frozen=True, slots=True)
class RuleSet(Entity):
    """The rules layer of a design (``rules.json``). ``severities`` gives the checks of a design-rule tool
    a severity, by the finding code of the check (``<oracle>.drc.<suffix>``; change c0114): a severity is
    not a rule, so it has no ``RuleKind``.

    ``proximity`` holds the placement rules, in name order; it is left out of the file when empty
    (change c0113). ``heights`` holds the height limits, in area order, left out when empty (change c0140).
    """

    rules: tuple[Rule, ...] = ()
    severities: dict[str, RuleSeverity] = field(default_factory=lambda: {})
    proximity: tuple[ProximityRule, ...] = field(default=(), metadata={"ordered": True})
    heights: tuple[HeightLimit, ...] = field(default=(), metadata={"ordered": True})

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for rule in self.proximity:
            if rule.name in seen:
                raise ValueError(f"two proximity rules are named {rule.name!r}")
            seen.add(rule.name)
        areas: set[str] = set()
        for limit in self.heights:
            if limit.area in areas:
                raise ValueError(f"two height limits name the area {limit.area!r}")
            areas.add(limit.area)


__all__ = [
    "LEAF_OPS",
    "HeightLimit",
    "PadSelection",
    "PlacementSeverity",
    "ProximityRule",
    "Rule",
    "RuleKind",
    "RuleSet",
    "RuleSeverity",
    "RuleSubject",
    "Selector",
    "SelectorOp",
]
