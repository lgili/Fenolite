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
import re
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from enum import Enum

from fenolite.checks.equivalence import norm, pairing
from fenolite.checks.equivalence.model import EXACT, Difference, Excluded, LevelResult, Tolerances
from fenolite.core.coords import Point, Size
from fenolite.model.board import Board, Layer, StackLayer
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet

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
    level: int = LEVEL, *, orientation_paths: Collection[str] = (),
) -> list[Difference]:  # fmt: skip
    """One difference per dotted leaf; explicitly typed orientations use the existing cyclic angle metric.

    The empty default preserves generic/level6/sweep semantics and model presence.
    """
    found: list[Difference] = []
    for path in sorted(set(one) | set(other)):
        left, right = one.get(path), other.get(path)
        if path in orientation_paths and type(left) is int and type(right) is int:
            equal = norm.angles_equal(left, right, tolerances)
        else:
            equal = leaves_equal(left, right, tolerances)
        if not equal:
            found.append(Difference(level, kind, where, path, text(left), text(right)))
    return found


def _ordered(found: Sequence[Difference]) -> tuple[Difference, ...]:
    return tuple(sorted(found, key=lambda d: (d.where, d.kind, d.field, d.a, d.b)))


def _missing(kind: str, field: str, where: str, on_a: bool) -> Difference:
    return Difference(LEVEL, kind, where, field, where if on_a else "", "" if on_a else where)


def _netclasses(
    a: Design, b: Design, tolerances: Tolerances, across: bool = False
) -> tuple[list[Difference], int]:
    """Net classes by name. ``across`` (sides of two backends, change c0421): a class on one side only that
    holds no net is not a difference (one backend always declares its default class), and a field that one
    side leaves unset is not compared (one backend states every field, the other leaves them to rules)."""
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
            held = members_a.get(name) if name in classes_a else members_b.get(name)
            if across and not held:
                continue
            found.append(_missing("netclass-missing", "name", name, name in classes_a))
            continue
        compared += 1
        one, other = fields(classes_a[name], skip=("name",)), fields(classes_b[name], skip=("name",))
        if across:
            stated = {path for path in set(one) | set(other) if one.get(path) is not None
                      and other.get(path) is not None}  # fmt: skip
            one = {path: value for path, value in one.items() if path in stated}
            other = {path: value for path, value in other.items() if path in stated}
        found += field_differences("netclass-field", name, one, other, tolerances)
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


WRITTEN = re.compile(r"^fenolite_(\d+)_([a-z0-9_]+)$")
"""A rule name as a conversion writes it, ``fenolite_<priority>_<slug>`` with an optional ``_<k>`` repeat or
``_<layer slug>`` (change c0421)."""
SKIP_WRITTEN = ("name", "priority")
"""What a pair made by the written name does not compare: the name is the written form, and the priority is
the one it states; a rules file read back numbers priorities by file order."""


def slug(text: str) -> str:
    """Lower case, each run outside ``[a-z0-9]`` replaced by ``_``, trimmed; ``rule`` when empty: the slug
    of a written rule name."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "rule"


def _identified(rules: Sequence[Rule]) -> dict[str, Rule]:
    """The rules by identity: ``<name>`` for the first rule of a name, ``<name>:<kind>`` once a name holds
    several kinds, and ``#<n>`` for the n-th repeat of one name and kind."""
    kinds: dict[str, set[str]] = defaultdict(set)
    for rule in rules:
        kinds[rule.name].add(rule.kind)
    seen: dict[tuple[str, str], int] = defaultdict(int)
    out: dict[str, Rule] = {}
    for rule in rules:
        seen[rule.name, rule.kind] += 1
        label = rule.name if len(kinds[rule.name]) == 1 else f"{rule.name}:{rule.kind}"
        count = seen[rule.name, rule.kind]
        out[label if count == 1 else f"{label}#{count}"] = rule
    return out


def _written_match(written: Rule, candidates: Mapping[str, Rule], tolerances: Tolerances) -> str | None:
    """The label of the rule of ``candidates`` that ``written`` (a rule named as a conversion writes it)
    stands for: same kind, the priority its name states and the slug of its name, or a slug followed by a
    repeat or layer suffix; the one whose other fields are all equal first, else the first by label."""
    found = WRITTEN.match(written.name)
    if found is None:
        return None
    priority, text = int(found.group(1)), found.group(2)
    hits = [
        label
        for label, rule in sorted(candidates.items())
        if rule.kind == written.kind
        and rule.priority == priority
        and (text == slug(rule.name) or text.startswith(slug(rule.name) + "_"))
    ]
    if not hits:
        return None
    mine = fields(written, skip=SKIP_WRITTEN)
    for label in hits:
        theirs = fields(candidates[label], skip=SKIP_WRITTEN)
        if not field_differences("rule-field", label, mine, theirs, tolerances):
            return label
    return hits[0]


def _rules(a: Design, b: Design, tolerances: Tolerances) -> tuple[list[Difference], int]:
    """Rules match by identity (``_identified``); a rule left over on one side whose name is written as a
    conversion writes it then matches a left-over rule of the other side it stands for (change c0421)."""
    set_a = a.rules if a.rules is not None else RuleSet(id="rst-a")
    set_b = b.rules if b.rules is not None else RuleSet(id="rst-b")
    found: list[Difference] = []
    rules_a = _identified(set_a.rules)
    rules_b = _identified(set_b.rules)
    pairs: list[tuple[str, Rule, Rule, tuple[str, ...]]] = []
    for label in sorted(set(rules_a) & set(rules_b)):
        pairs.append((label, rules_a[label], rules_b[label], ("name",)))
    left_a = {label: rule for label, rule in rules_a.items() if label not in rules_b}
    left_b = {label: rule for label, rule in rules_b.items() if label not in rules_a}
    for written, mine, theirs, first in ((left_b, left_b, left_a, False), (left_a, left_a, left_b, True)):
        for label in sorted(written):
            if label not in mine:
                continue
            other = _written_match(mine[label], theirs, tolerances)
            if other is None:
                continue
            if first:
                pairs.append((label, mine.pop(label), theirs.pop(other), SKIP_WRITTEN))
            else:
                pairs.append((other, theirs.pop(other), mine.pop(label), SKIP_WRITTEN))
    for label in sorted(left_a):
        found.append(_missing("rule-missing", "name", label, True))
    for label in sorted(left_b):
        found.append(_missing("rule-missing", "name", label, False))
    for label, one, other, skip in pairs:
        found += field_differences(
            "rule-field", label, fields(one, skip=skip), fields(other, skip=skip), tolerances
        )
    found += field_differences(
        "ruleset-field", "ruleset", fields(set_a, skip=("rules",)), fields(set_b, skip=("rules",)), tolerances
    )
    return found, len(pairs) + 1


def _labelled(layers: Sequence[StackLayer], fold: bool = False) -> list[tuple[str, StackLayer]]:
    """The stack-up layers with their labels: the name (case-folded with ``fold``), and ``<name>#<n>`` for
    the n-th repeat of a name (a dielectric made of several sheets)."""
    seen: dict[str, int] = defaultdict(int)
    out: list[tuple[str, StackLayer]] = []
    for layer in layers:
        name = layer.name.casefold() if fold else layer.name
        seen[name] += 1
        count = seen[name]
        out.append((name if count == 1 else f"{name}#{count}", layer))
    return out


UNSTATED_KINDS = frozenset({"silkscreen", "solderpaste", "soldermask"})
"""Stack-up kinds one backend leaves out of its stack-up: across backends compared only when both sides
state one (c0421)."""


def _stated(layers: Sequence[StackLayer], other: Sequence[StackLayer]) -> list[StackLayer]:
    """``layers`` without those of a kind of ``UNSTATED_KINDS`` that ``other`` holds no layer of."""
    held = {layer.kind for layer in other}
    return [layer for layer in layers if layer.kind not in UNSTATED_KINDS or layer.kind in held]


def _stackup(
    board_a: Board, board_b: Board, tolerances: Tolerances, across: bool = False
) -> tuple[list[Difference], int]:
    """The stack-up layers by label; ``across`` (sides of two backends) leaves out a layer of a kind of
    ``UNSTATED_KINDS`` that the other side's stack-up does not state, and labels names without letter case
    (one backend writes ``Dielectric 1``, the other ``dielectric 1``)."""
    found: list[Difference] = []
    stack_a, stack_b = board_a.stackup, board_b.stackup
    all_a = list(stack_a.layers) if stack_a is not None else []
    all_b = list(stack_b.layers) if stack_b is not None else []
    if across:
        all_a, all_b = _stated(all_a, all_b), _stated(all_b, all_a)
    layers_a = _labelled(all_a, across) if stack_a is not None else []
    layers_b = _labelled(all_b, across) if stack_b is not None else []
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


DRAWING_KINDS = frozenset({"mechanical", "user"})
"""Layer kinds that name no function: one backend's mechanical layer is another's user layer (c0421)."""


def _layers(
    board_a: Board,
    board_b: Board,
    aliases: Mapping[str, str] | None = None,
    across: bool = False,
    keepout_layers: tuple[Collection[str], Collection[str]] = ((), ()),
) -> tuple[list[Difference], int]:
    """The board layers matched by name (change c0281): a name on one side only is ``layer-missing``, a
    matched layer of another kind ``layer-field`` (``kind``), and common layers in another relative order
    one ``layer-field`` (``order``). An ordinal is a position in the table, so a layer that one side lacks
    would shift every later one: ordinals are not compared. ``aliases`` maps side ``b``'s name of a layer
    paired by user name to side ``a``'s (change c0421). ``across`` (sides of two backends): a non-copper
    layer on one side only that no item of that side uses (pads counted on copper) is not a difference, a
    mechanical and a user layer are of one kind, and only the copper layers' order is compared: the order
    of the others is each backend's table order. A layer of ``keepout_layers`` on its side only is not a
    difference: level 7 compares its drawings with the other side's rule areas."""
    renamed = aliases or {}
    held_a = {layer.name: layer for layer in board_a.layers}
    held_b = {renamed.get(layer.name, layer.name): layer for layer in board_b.layers}
    used_a: set[str] = pairing.used_layers(board_a, pad_masks=False) if across else set()
    used_b: set[str] = pairing.used_layers(board_b, pad_masks=False) if across else set()
    found: list[Difference] = []
    for name in sorted(set(held_a) ^ set(held_b)):
        layer = held_a.get(name) or held_b[name]
        if layer.name in (keepout_layers[0] if name in held_a else keepout_layers[1]):
            continue
        used = name in used_a if name in held_a else layer.name in used_b
        if across and layer.kind != "copper" and not used:
            continue
        where = f"{layer.kind}:{name}"
        found.append(
            Difference(LEVEL, "layer-missing", where, "layer", name if name in held_a else "",
                       layer.name if name in held_b else "")
        )  # fmt: skip
    common = sorted(set(held_a) & set(held_b))
    for name in common:
        kinds = {held_a[name].kind, held_b[name].kind}
        if across and kinds <= DRAWING_KINDS:
            continue
        if held_a[name].kind != held_b[name].kind:
            found.append(Difference(LEVEL, "layer-field", name, "kind", held_a[name].kind, held_b[name].kind))

    def order(layers: Sequence[tuple[str, Layer]], other: Mapping[str, object]) -> list[str]:
        ranked = sorted(enumerate(layers), key=lambda pair: (pair[1][1].ordinal, pair[0]))
        return [
            name for _, (name, layer) in ranked if name in other and (not across or layer.kind == "copper")
        ]

    listed_a = [(layer.name, layer) for layer in board_a.layers]
    listed_b = [(renamed.get(layer.name, layer.name), layer) for layer in board_b.layers]
    order_a, order_b = order(listed_a, held_b), order(listed_b, held_a)
    if order_a != order_b:
        found.append(
            Difference(LEVEL, "layer-field", "layers", "order", ",".join(order_a), ",".join(order_b))
        )
    return found, len(common)


KEPT_RECORD = "kept_record"
"""The ext pair key a conversion sets on a rule it read from a record the target format cannot hold and
keeps for a later write of the source format (change c0424): a declared format limit."""
DECLARED_LIMIT = "declared-limit"
DECLARED_REASON = "a rule the other format cannot hold, kept by the conversion as a declared format limit"


def _kept(rule: Rule) -> bool:
    return any(key == KEPT_RECORD and value == "1" for bag in rule.ext.values() for key, value in bag.payload)


def _declared_limits(
    found: Sequence[Difference], a: Design, b: Design
) -> tuple[list[Difference], list[Excluded]]:
    """``found`` without each ``rule-missing`` whose rule its side marks kept (``KEPT_RECORD``), and those as
    excluded under ``DECLARED_LIMIT`` (change c0421, task 2.3): a declared limit stays in the output and fails
    nothing. A kept rule that the other side holds is compared as any rule."""
    rules_a = _identified(a.rules.rules) if a.rules is not None else {}
    rules_b = _identified(b.rules.rules) if b.rules is not None else {}
    kept: list[Difference] = []
    excluded: list[Excluded] = []
    for difference in found:
        held = rules_a.get(difference.a) if difference.a else rules_b.get(difference.b)
        if difference.kind == "rule-missing" and held is not None and _kept(held):
            excluded.append(Excluded(difference, DECLARED_LIMIT, DECLARED_REASON))
        else:
            kept.append(difference)
    return kept, excluded


def level_rules(
    a: Design,
    b: Design,
    tolerances: Tolerances = EXACT,
    *,
    aliases: Mapping[str, str] | None = None,
    across: bool = False,
    keepout_layers: tuple[Collection[str], Collection[str]] = ((), ()),
) -> LevelResult:
    """Level 6: net classes, custom rules, the rule set, the stack-up and the board layers; ``aliases``,
    ``across`` and ``keepout_layers`` as ``_layers`` and ``_netclasses`` take them."""
    assert a.board is not None and b.board is not None
    found: list[Difference] = []
    counts: dict[str, int] = {}
    for name, (differences, compared) in (
        ("netclasses", _netclasses(a, b, tolerances, across)),
        ("rules", _rules(a, b, tolerances)),
        ("stackup", _stackup(a.board, b.board, tolerances, across)),
        ("layers", _layers(a.board, b.board, aliases, across, keepout_layers)),
    ):
        found += differences
        counts[name] = compared
    if a.board.max_curve_error is not None or b.board.max_curve_error is not None:
        found += field_differences(
            "rule-field",
            "board",
            {"max_curve_error": a.board.max_curve_error},
            {"max_curve_error": b.board.max_curve_error},
            EXACT,
        )
        counts["project_geometry"] = 1
    found, excluded = _declared_limits(found, a, b)
    summary: dict[str, object] = dict(counts)
    if aliases:
        summary["layers_aliased"] = len(aliases)
    return LevelResult(LEVEL, sum(counts.values()), _ordered(found), tuple(excluded), summary)


__all__ = ["IDENTITY", "field_differences", "fields", "level_rules", "leaves_equal", "text"]
