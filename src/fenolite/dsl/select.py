# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Selectors of ``design.rules.rule()``: which items a design rule holds for (``docs/dsl.md``, "Design
rules").

``net``, ``netclass``, ``ref``, ``item``, ``area`` and ``pair`` give leaves; ``&``, ``|`` and ``~`` combine
them; ``ALL`` is every item and stands alone. A name may hold ``*``, which the model keeps as a glob. Whether
a target writes a selector for a rule kind is decided by the lowering, not here.
"""

from __future__ import annotations

from dataclasses import dataclass

from fenolite.dsl.errors import DslError
from fenolite.dsl.interfaces import Interface
from fenolite.dsl.items import RuleArea
from fenolite.dsl.part import Net, Part
from fenolite.model.pairs import PAIR_ROLES, coupled_name, pair_base
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


def pair(x: Interface | str) -> Select:
    """The items on the two nets of a differential pair: a ``DiffPair``, a ``USB2`` or another interface
    of a pair kind, whose base is taken from its net names; or a base as text, ``"*"`` for every pair.

    A pair reaches KiCad through its net names, so the two names must form a pair: equal except for a
    ``P`` and an ``N``, or a ``+`` and a ``-``, which only digits and ``_`` may follow."""
    if isinstance(x, str):
        return Select(Selector("diff_pair", _name(x, "pair")))
    roles = PAIR_ROLES.get(x.kind) if isinstance(x, Interface) else None  # pyright: ignore[reportUnnecessaryIsInstance]
    if roles is None:
        raise DslError(
            f"select.pair() takes a DiffPair, a USB2, an interface of kind "
            f"{' or '.join(PAIR_ROLES)}, or a base name, not {x!r}"
        )
    positive, negative = (x.members.get(role) for role in roles)
    if positive is None or negative is None:
        raise DslError(f"select.pair(): interface {x.name} lacks its {roles[0]} or its {roles[1]} net")
    base = pair_base(positive.name, negative.name)
    if not base:
        other = coupled_name(positive.name)
        hint = (
            f"name the second net {other}"
            if other is not None and base is None
            else f"name them {positive.name}_P and {positive.name}_N"
        )
        raise DslError(
            f"select.pair(): the nets {positive.name} and {negative.name} of {x.name} do not form a "
            f"differential pair by name; {hint}"
        )
    return Select(Selector("diff_pair", base))


__all__ = ["ALL", "ITEM_KINDS", "Select", "area", "item", "net", "netclass", "pair", "ref"]
