# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Level 6 of a design comparison: the rules (capability design-equivalence, "Level 6 compares rules";
``docs/equivalence.md``, "Level 6").

Net classes match by name, custom rules by name, the board-wide fields of the rule set compare as one
entity, the stack-up layers match in order by name, and the board layers by kind and ordinal. The fields of
an entity are those of its dataclass, walked to the leaves (``fields``), without ``id``, ``native_ids``,
``ext`` and ``provenance``, so a copy with other ids is equal. ``field`` is the dotted path of the leaf
(``selector_a.value``), so the kinds stay closed while the model grows. Integers compare with the length
tolerance (the lengths of these entities are integers of nanometres), texts and booleans exactly. Net class
members compare as sets of net names.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from collections.abc import Mapping, Sequence
from enum import Enum

from fenolite.checks.equivalence import norm
from fenolite.checks.equivalence.model import EXACT, Difference, LevelResult, Tolerances
from fenolite.core.coords import Point, Size
from fenolite.model.board import Board, StackLayer
from fenolite.model.design import Design
from fenolite.model.rules import RuleSet

LEVEL = 6
IDENTITY = frozenset({"id", "native_ids", "ext", "provenance"})
"""The fields of an entity that say who it is or where it came from, never what it is."""
Leaf = str | int | bool | Point | Size | None
"""A leaf of an entity: points and sizes stay whole, so ``position`` is one field compared per coordinate."""


def fields(value: object, *, skip: Sequence[str] = ()) -> dict[str, Leaf]:
    """The leaves of ``value`` by dotted path: a dataclass is walked field by field (``IDENTITY`` and
    ``skip`` left out at the top), a tuple or list of dataclasses by index, a mapping by key; a point is
    ``x,y``, a size ``wxh``, a tuple of plain values its items joined by ``,``."""
    out: dict[str, Leaf] = {}

    def walk(item: object, path: str, top: bool) -> None:
        if item is None or isinstance(item, (bool, int, str, Point, Size)):
            out[path] = item
        elif isinstance(item, Enum):
            out[path] = str(item.value)
        elif dataclasses.is_dataclass(item) and not isinstance(item, type):
            for found in dataclasses.fields(item):
                if found.name in IDENTITY or (top and found.name in skip):
                    continue
                walk(getattr(item, found.name), f"{path}.{found.name}" if path else found.name, False)
        elif isinstance(item, Mapping):
            mapping: Mapping[object, object] = item  # pyright: ignore[reportUnknownVariableType]
            for key in sorted(mapping, key=str):
                walk(mapping[key], f"{path}.{key}" if path else str(key), False)
        elif isinstance(item, (tuple, list, frozenset, set)):
            seq: list[object] = list(item)  # pyright: ignore[reportUnknownArgumentType]
            if isinstance(item, (frozenset, set)):
                seq = sorted(seq, key=str)
            if seq and all(dataclasses.is_dataclass(x) or isinstance(x, (tuple, list)) for x in seq):
                out[f"{path}.count" if path else "count"] = len(seq)
                for index, x in enumerate(seq):
                    walk(x, f"{path}.{index}" if path else str(index), False)
            else:
                out[path] = ",".join(_plain(x) for x in seq)
        else:
            out[path] = str(item)

    walk(value, "", True)
    return out


def _plain(value: object) -> str:
    """An item of a tuple of plain values as text (a point ``(x y)`` in brackets, as a list of points)."""
    if isinstance(value, Point):
        return f"({value.x} {value.y})"
    if isinstance(value, Size):
        return f"({value.w}x{value.h})"
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, (bool, int, str)) or value is None:
        return text(value)
    return str(value)


def text(value: Leaf) -> str:
    """A leaf as the text of a difference: ``true``/``false``, a decimal integer, a text, ``""`` for none."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Point):
        return f"{value.x},{value.y}"
    if isinstance(value, Size):
        return f"{value.w}x{value.h}"
    return str(value)


def leaves_equal(one: Leaf, other: Leaf, tolerances: Tolerances) -> bool:
    if isinstance(one, bool) or isinstance(other, bool):
        return one is other
    if isinstance(one, Point) and isinstance(other, Point):
        return norm.points_equal(one, other, tolerances)
    if isinstance(one, Size) and isinstance(other, Size):
        return norm.sizes_equal(one, other, tolerances)
    if isinstance(one, int) and isinstance(other, int):
        return norm.lengths_equal(one, other, tolerances)
    return one == other


def field_differences(
    kind: str, where: str, one: Mapping[str, Leaf], other: Mapping[str, Leaf], tolerances: Tolerances,
    level: int = LEVEL,
) -> list[Difference]:  # fmt: skip
    """One difference of ``kind`` per dotted path whose leaves differ, located at ``where``."""
    found: list[Difference] = []
    for path in sorted(set(one) | set(other)):
        left, right = one.get(path), other.get(path)
        if not leaves_equal(left, right, tolerances):
            found.append(Difference(level, kind, where, path, text(left), text(right)))
    return found


def _ordered(found: Sequence[Difference]) -> tuple[Difference, ...]:
    return tuple(sorted(found, key=lambda d: (d.where, d.kind, d.field, d.a, d.b)))


def _missing(kind: str, field: str, where: str, on_a: bool) -> Difference:
    return Difference(LEVEL, kind, where, field, where if on_a else "", "" if on_a else where)


def _netclasses(a: Design, b: Design, tolerances: Tolerances) -> tuple[list[Difference], int]:
    found: list[Difference] = []

    def members(design: Design) -> dict[str, set[str]]:
        by_id = {cls.id: cls.name for cls in design.circuit.netclasses}
        held: dict[str, set[str]] = defaultdict(set)
        for net in design.circuit.nets:
            if net.netclass_id is not None and net.netclass_id in by_id:
                held[by_id[net.netclass_id]].add(net.name)
        return held

    classes_a = {cls.name: cls for cls in a.circuit.netclasses}
    classes_b = {cls.name: cls for cls in b.circuit.netclasses}
    members_a, members_b = members(a), members(b)
    compared = 0
    for name in sorted(set(classes_a) | set(classes_b)):
        if name not in classes_a or name not in classes_b:
            found.append(_missing("netclass-missing", "name", name, name in classes_a))
            continue
        compared += 1
        found += field_differences(
            "netclass-field",
            name,
            fields(classes_a[name], skip=("name",)),
            fields(classes_b[name], skip=("name",)),
            tolerances,
        )
        held_a, held_b = members_a.get(name, set()), members_b.get(name, set())
        if held_a != held_b:
            found.append(
                Difference(
                    LEVEL,
                    "netclass-members",
                    name,
                    "nets",
                    ",".join(sorted(held_a)),
                    ",".join(sorted(held_b)),
                )
            )
    return found, compared


def _rules(a: Design, b: Design, tolerances: Tolerances) -> tuple[list[Difference], int]:
    set_a = a.rules if a.rules is not None else RuleSet(id="rst-a")
    set_b = b.rules if b.rules is not None else RuleSet(id="rst-b")
    found: list[Difference] = []
    rules_a = {rule.name: rule for rule in set_a.rules}
    rules_b = {rule.name: rule for rule in set_b.rules}
    compared = 0
    for name in sorted(set(rules_a) | set(rules_b)):
        if name not in rules_a or name not in rules_b:
            found.append(_missing("rule-missing", "name", name, name in rules_a))
            continue
        compared += 1
        found += field_differences(
            "rule-field",
            name,
            fields(rules_a[name], skip=("name",)),
            fields(rules_b[name], skip=("name",)),
            tolerances,
        )
    found += field_differences(
        "ruleset-field", "ruleset", fields(set_a, skip=("rules",)), fields(set_b, skip=("rules",)), tolerances
    )
    return found, compared + 1


def _labelled(layers: Sequence[StackLayer]) -> list[tuple[str, StackLayer]]:
    """The stack-up layers with their labels: the name, and ``<name>#<n>`` for the n-th repeat of a name
    (a dielectric made of several sheets)."""
    seen: dict[str, int] = defaultdict(int)
    out: list[tuple[str, StackLayer]] = []
    for layer in layers:
        seen[layer.name] += 1
        count = seen[layer.name]
        out.append((layer.name if count == 1 else f"{layer.name}#{count}", layer))
    return out


def _stackup(board_a: Board, board_b: Board, tolerances: Tolerances) -> tuple[list[Difference], int]:
    found: list[Difference] = []
    stack_a, stack_b = board_a.stackup, board_b.stackup
    layers_a = _labelled(stack_a.layers) if stack_a is not None else []
    layers_b = _labelled(stack_b.layers) if stack_b is not None else []
    names_a, names_b = [label for label, _ in layers_a], [label for label, _ in layers_b]
    for name in sorted(set(names_a) ^ set(names_b)):
        found.append(_missing("stackup-missing", "layer", name, name in names_a))
    common_a = [name for name in names_a if name in names_b]
    common_b = [name for name in names_b if name in names_a]
    if common_a != common_b:
        found.append(
            Difference(LEVEL, "stackup-missing", "stackup", "layer", ",".join(common_a), ",".join(common_b))
        )
    by_label_b = dict(layers_b)
    compared = 0
    for label, layer in layers_a:
        other = by_label_b.get(label)
        if other is None:
            continue
        compared += 1
        found += field_differences(
            "stackup-field", label, fields(layer, skip=("name",)), fields(other, skip=("name",)), tolerances
        )
    if stack_a is not None or stack_b is not None:
        found += field_differences(
            "stackup-field",
            "stackup",
            fields(stack_a, skip=("layers",)) if stack_a is not None else {},
            fields(stack_b, skip=("layers",)) if stack_b is not None else {},
            tolerances,
        )
    return found, compared


def _layers(board_a: Board, board_b: Board) -> tuple[list[Difference], int]:
    """The board layers matched by name (change c0281): a name on one side only is ``layer-missing``, a
    matched layer of another kind ``layer-field`` (``kind``), and common layers in another relative order
    one ``layer-field`` (``order``). An ordinal is a position in the table, so a layer that one side lacks
    would shift every later one: ordinals are not compared."""
    held_a = {layer.name: layer for layer in board_a.layers}
    held_b = {layer.name: layer for layer in board_b.layers}
    found: list[Difference] = []
    for name in sorted(set(held_a) ^ set(held_b)):
        layer = held_a.get(name) or held_b[name]
        where = f"{layer.kind}:{name}"
        found.append(
            Difference(LEVEL, "layer-missing", where, "layer", name if name in held_a else "",
                       name if name in held_b else "")
        )  # fmt: skip
    common = sorted(set(held_a) & set(held_b))
    for name in common:
        if held_a[name].kind != held_b[name].kind:
            found.append(Difference(LEVEL, "layer-field", name, "kind", held_a[name].kind, held_b[name].kind))

    def order(board: Board, other: Mapping[str, object]) -> list[str]:
        ranked = sorted(enumerate(board.layers), key=lambda pair: (pair[1].ordinal, pair[0]))
        return [layer.name for _, layer in ranked if layer.name in other]

    order_a, order_b = order(board_a, held_b), order(board_b, held_a)
    if order_a != order_b:
        found.append(
            Difference(LEVEL, "layer-field", "layers", "order", ",".join(order_a), ",".join(order_b))
        )
    return found, len(common)


def level_rules(a: Design, b: Design, tolerances: Tolerances = EXACT) -> LevelResult:
    """Level 6: net classes, custom rules, the rule set, the stack-up and the board layers."""
    assert a.board is not None and b.board is not None
    found: list[Difference] = []
    counts: dict[str, int] = {}
    for name, (differences, compared) in (
        ("netclasses", _netclasses(a, b, tolerances)),
        ("rules", _rules(a, b, tolerances)),
        ("stackup", _stackup(a.board, b.board, tolerances)),
        ("layers", _layers(a.board, b.board)),
    ):
        found += differences
        counts[name] = compared
    return LevelResult(LEVEL, sum(counts.values()), _ordered(found), (), counts)


__all__ = ["IDENTITY", "field_differences", "fields", "level_rules", "leaves_equal", "text"]
