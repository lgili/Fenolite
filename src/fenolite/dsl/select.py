# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Selectors of ``design.rules.rule()``: which items a design rule holds for (``docs/dsl.md``, "Design
rules").

``net``, ``netclass``, ``ref``, ``item`` and ``area`` give leaves; ``&``, ``|`` and ``~`` combine them;
``ALL`` is every item and stands alone. A name may hold ``*``, which the model keeps as a glob. Whether a
target writes a selector for a rule kind is decided by the lowering, not here.
"""

from __future__ import annotations

from dataclasses import dataclass

from fenolite.dsl.errors import DslError
from fenolite.dsl.items import RuleArea
from fenolite.dsl.part import Net, Part
from fenolite.model.rules import Selector

ITEM_KINDS: tuple[str, ...] = ("track", "via", "pad", "zone")
"""The values of ``item()``."""
_FORBIDDEN = frozenset("'\"?[]")
"""Characters an area name cannot hold: a rules condition has no way to escape them."""


@dataclass(frozen=True, slots=True)
class Select:
    """A selector expression; ``to_model()`` gives the model ``Selector``."""

    selector: Selector

    def to_model(self) -> Selector:
        return self.selector

    def _join(self, op: str, other: object) -> Select:
        if not isinstance(other, Select):
            raise DslError(f"a selector can only be combined with a selector, not {other!r}")
        if self.selector.op == "all" or other.selector.op == "all":
            raise DslError("select.ALL stands alone: it cannot be combined with another selector")
        items: list[Selector] = []
        for side in (self.selector, other.selector):
            items.extend(side.items if side.op == op else (side,))
        return Select(Selector(op, items=tuple(items)))  # type: ignore[arg-type]

    def __and__(self, other: object) -> Select:
        return self._join("and", other)

    def __or__(self, other: object) -> Select:
        return self._join("or", other)

    def __invert__(self) -> Select:
        if self.selector.op == "all":
            raise DslError("select.ALL stands alone: it cannot be negated")
        return Select(Selector("not", items=(self.selector,)))


ALL = Select(Selector("all"))
"""Every item: the selector of a board-wide rule."""


def _name(value: object, what: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise DslError(f"select.{what}() takes a non-empty name, not {value!r}")
    return value


def net(name: str | Net) -> Select:
    """The items on a net, given by name or as the ``Net`` itself."""
    return Select(Selector("net", _name(name.name if isinstance(name, Net) else name, "net")))


def netclass(name: str) -> Select:
    """The items on the nets of a net class declared with ``design.rules.netclass``."""
    return Select(Selector("netclass", _name(name, "netclass")))


def ref(name: str | Part) -> Select:
    """The items of a part (for a courtyard rule, the part's footprint), by reference or as the ``Part``."""
    return Select(Selector("ref", _name(name.ref if isinstance(name, Part) else name, "ref")))


def item(kind: str) -> Select:
    """The items of one kind: ``track``, ``via``, ``pad`` or ``zone``."""
    if kind not in ITEM_KINDS:
        raise DslError(f"select.item() takes one of {', '.join(ITEM_KINDS)}, not {kind!r}")
    return Select(Selector("item_kind", kind))


def area(area: str | RuleArea) -> Select:
    """The items whose copper reaches into a rule area, given by name or as the ``RuleArea`` of
    ``design.rule_area()``. A name may hold ``*``; letter case counts. The area may be drawn in KiCad: the
    build checks, after the merge, that the board holds one of that name."""
    name = _name(area.name if isinstance(area, RuleArea) else area, "area")
    if _FORBIDDEN & set(name):
        raise DslError(f"select.area() takes a name without ' \" ? [ ], not {name!r}")
    return Select(Selector("area", name))


__all__ = ["ALL", "ITEM_KINDS", "Select", "area", "item", "net", "netclass", "ref"]
