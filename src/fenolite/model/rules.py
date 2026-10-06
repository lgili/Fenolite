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
]
"""The first six kinds are those of v0.1; the last six were added by change c0071. Which sides, selector
ops and layer clause a kind takes, and for which targets it is written, is the backend's to say
(``backends.kicad.rulemap.KIND_SELECTORS`` and ``KIND_SUPPORT``)."""
RuleSeverity = Literal["error", "warning", "ignore"]
SelectorOp = Literal["all", "net", "netclass", "ref", "layer", "item_kind", "and", "or", "not"]
LEAF_OPS = ("net", "netclass", "ref", "layer", "item_kind")


@dataclass(frozen=True, slots=True)
class RuleSubject:
    """The properties of one object a selector is evaluated against."""

    item_kind: str
    net: str | None = None
    netclass: str | None = None
    ref: str | None = None
    layer: str | None = None


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


@dataclass(frozen=True, slots=True)
class RuleSet(Entity):
    """The rules layer of a design (``rules.json``)."""

    rules: tuple[Rule, ...] = ()


__all__ = ["LEAF_OPS", "Rule", "RuleKind", "RuleSet", "RuleSeverity", "RuleSubject", "Selector", "SelectorOp"]
