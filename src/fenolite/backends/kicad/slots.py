# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slots: keep the children a typed reader does not model, in place, so a writer re-emits them.

``split`` maps each child of a node to ``Modeled(field)`` or ``Opaque(fragment, min_version)`` (the
types of ``fenolite.model.base``); ``rebuild`` walks the slots in order and asks a ``SlotSource`` for
the modelled children, so unknown children keep their position. Slot lists persist in the ``kicad``
extension bag of an entity as ``slot:<rel>:<kind>`` pairs, one group per relative locator (``.`` for
the entity node, ``effects[0]`` for a modelled sub-list), so no model dataclass changes.
"""

# evidence: see dru, mod, pcb, sch, sym, wks

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Protocol

from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse_fragment
from fenolite.model.base import ExtBag, Modeled, Opaque, Slot

SLOT_PREFIX = "slot:"
MinVersion = str | Callable[[Node | Atom], str | None] | None
_KIND = re.compile(r"modeled|opaque(?:@(\d+))?")


class SlotSource(Protocol):
    """What a writer knows: the current children of each modelled field."""

    def items(self, field: str) -> Sequence[Node | Atom]: ...

    def fields(self) -> Iterable[str]: ...


def split(
    node: Node,
    fields: Mapping[str, str],
    *,
    positional: Sequence[str] = (),
    min_version: MinVersion = None,
) -> tuple[Slot, ...]:
    """One slot per child of ``node``, in child order."""
    slots: list[Slot] = []
    leading = 0
    seen_list = False
    for child in node.children:
        if isinstance(child, Node):
            seen_list = True
            field = fields.get(child.head.text)
            if field is not None:
                slots.append(Modeled(field))
                continue
        elif not seen_list and leading < len(positional):
            slots.append(Modeled(positional[leading]))
            leading += 1
            continue
        version = min_version(child) if callable(min_version) else min_version
        slots.append(Opaque(dumps(child, style="compact"), version))
    return tuple(slots)


def opaque_child(slot: Opaque) -> Node | Atom:
    """The child an opaque slot stands for, decoded from its fragment."""
    return parse_fragment(slot.fragment)


def rebuild(
    head: Atom,
    slots: Sequence[Slot],
    source: SlotSource,
    *,
    canonical: Sequence[str] = (),
    opaque: Callable[[Opaque], Node | Atom] = opaque_child,
) -> Node:
    """A node whose children follow ``slots``; modelled children come from ``source``.

    ``opaque`` turns an opaque slot into its child; a writer passes its own to see each child it emits.
    """
    last: dict[str, int] = {}
    for index, slot in enumerate(slots):
        if isinstance(slot, Modeled):
            last[slot.field] = index
    wanted = list(source.fields())
    for field in wanted:
        if field not in last and field not in canonical:
            raise ValueError(f"field {field!r} has no slot and no position in canonical")
    emitted: list[list[Node | Atom]] = [[] for _ in slots]
    taken: dict[str, int] = {}
    for index, slot in enumerate(slots):
        if isinstance(slot, Opaque):
            emitted[index].append(opaque(slot))
            continue
        items = source.items(slot.field)
        k = taken.get(slot.field, 0)
        taken[slot.field] = k + 1
        if k < len(items):
            emitted[index].append(items[k])
        if last[slot.field] == index:
            emitted[index].extend(items[k + 1 :])
    front: list[Node | Atom] = []
    for field in sorted((f for f in wanted if f not in last), key=list(canonical).index):
        items = source.items(field)
        before = canonical[: list(canonical).index(field)]
        anchors = [last[f] for f in before if f in last]
        (emitted[max(anchors)] if anchors else front).extend(items)
    children = [child for group in emitted for child in group]
    first_list = next((i for i, c in enumerate(children) if isinstance(c, Node)), len(children))
    return Node(head, tuple(children[:first_list] + front + children[first_list:]))


def _pairs(rel: str, slots: Sequence[Slot]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for slot in slots:
        if isinstance(slot, Modeled):
            pairs.append((f"{SLOT_PREFIX}{rel}:modeled", slot.field))
        elif slot.min_version is None:
            pairs.append((f"{SLOT_PREFIX}{rel}:opaque", slot.fragment))
        else:
            if not slot.min_version.isdigit():
                raise ValueError(f"min_version must be a decimal version, got {slot.min_version!r}")
            pairs.append((f"{SLOT_PREFIX}{rel}:opaque@{slot.min_version}", slot.fragment))
    return pairs


def _parse_key(key: str, value: str) -> tuple[str, Slot]:
    rel, sep, kind = key[len(SLOT_PREFIX) :].rpartition(":")
    match = _KIND.fullmatch(kind)
    if not sep or not rel or match is None:
        raise ValueError(f"unknown slot key {key!r}")
    if kind == "modeled":
        return rel, Modeled(value)
    return rel, Opaque(value, match.group(1))


def from_ext_all(bag: ExtBag) -> dict[str, tuple[Slot, ...]]:
    """Every slot list in ``bag``, keyed by relative locator."""
    groups: dict[str, list[Slot]] = {}
    for key, value in bag.payload:
        if key.startswith(SLOT_PREFIX):
            rel, slot = _parse_key(key, value)
            groups.setdefault(rel, []).append(slot)
    return {rel: tuple(slots) for rel, slots in groups.items()}


def from_ext(bag: ExtBag, at: str = ".") -> tuple[Slot, ...]:
    """The slot list of relative locator ``at`` (empty when the bag has none)."""
    return from_ext_all(bag).get(at, ())


def _max_version(versions: Iterable[str | None]) -> str | None:
    known = [v for v in versions if v is not None]
    return max(known, key=int) if known else None


def to_ext(slots: Sequence[Slot] | Mapping[str, Sequence[Slot]], base: ExtBag | None = None) -> ExtBag:
    """Store slot lists in an ``ExtBag``; foreign pairs and other locators of ``base`` are kept."""
    new: dict[str, Sequence[Slot]] = dict(slots) if isinstance(slots, Mapping) else {".": slots}
    foreign: list[tuple[str, str]] = []
    groups: dict[str, Sequence[Slot]] = {}
    if base is not None:
        foreign = [(k, v) for k, v in base.payload if not k.startswith(SLOT_PREFIX)]
        groups = {rel: s for rel, s in from_ext_all(base).items() if rel not in new}
    groups.update(new)
    order = sorted(groups, key=lambda rel: (rel != ".", rel))
    payload = foreign + [pair for rel in order for pair in _pairs(rel, groups[rel])]
    versions = [s.min_version for rel in order for s in groups[rel] if isinstance(s, Opaque)]
    return ExtBag(_max_version([base.min_version if base else None, *versions]), tuple(payload))


__all__ = [
    "SLOT_PREFIX",
    "MinVersion",
    "SlotSource",
    "from_ext",
    "from_ext_all",
    "opaque_child",
    "rebuild",
    "split",
    "to_ext",
]
