# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Level S: two drawn schematics compared item by item (capability design-equivalence, "Level S compares
drawn schematics"; changes c0276 and c0278; ``docs/equivalence.md``).

The inputs are two ``DrawnSchematic`` values (``fenolite.model.drawn``), each with the pin points of its
drawn items, as ``backends.kicad.drawn.extract_with_pins`` gives them. Sheet instances match by their key
path; the sheets of a matched pair are compared once, at the first instance (in page order) where they
meet. Symbols match by component path (of that instance) and unit; wires and buses are turned into their
maximal collinear segments first, so a wire split differently is the same drawing; every other item
matches as a multiset by kind, position and attributes, an opaque item by the SHA-256 of its fragment.
Both drawings are then resolved (``drawn_connect.resolve``) and the first pin, in sorted order, whose group
of common pins differs gives ``drawn-net``.

``where`` is the instance path (``/`` for the root, ``/a/b`` below it), followed for an item by ``:`` and
the symbol (``component:unit``) or the item kind and its first point in nanometres (``junction@x,y``).
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from math import gcd

from fenolite.checks.equivalence.model import (
    EXACT,
    KINDS,
    SCHEMATIC_LEVEL,
    Difference,
    LevelResult,
    Tolerances,
)
from fenolite.checks.equivalence.norm import angles_equal, points_equal
from fenolite.core.coords import Point
from fenolite.model.drawn import DrawnField, DrawnInstance, DrawnSchematic, DrawnSheet, DrawnSymbol
from fenolite.model.drawn_connect import DrawnNetlist, Element, PinKey, PinPoint, natural, resolve

_FIELD = {kind: name for level, kind, name in KINDS if level == SCHEMATIC_LEVEL}
Item = tuple[str, tuple[Point, ...], tuple[tuple[str, str], ...]]
"""One drawn item: its kind, its points (none for a bus alias or an opaque item) and its named attributes as
exact strings; an opaque item's only attribute is the SHA-256 of its fragment."""


def _difference(kind: str, where: str, a: str, b: str, field: str = "") -> Difference:
    return Difference(SCHEMATIC_LEVEL, kind, where, field or _FIELD[kind], a, b)


def _point(point: Point) -> str:
    return f"{point.x},{point.y}"


def _path(instance: DrawnInstance) -> str:
    return "/" + instance.path


# --- wires and buses -----------------------------------------------------------------------------------


def merged(segments: Sequence[tuple[Point, Point]]) -> tuple[tuple[Point, Point], ...]:
    """The maximal collinear segments of ``segments``: segments on one line that overlap or touch become
    one, each from its lower to its higher end (``x``, then ``y``), sorted."""
    lines: dict[tuple[int, int, int], list[tuple[int, int, Point, Point]]] = defaultdict(list)
    for start, end in segments:
        if start == end:
            continue
        first, last = sorted((start, end), key=lambda p: (p.x, p.y))
        dx, dy = last.x - first.x, last.y - first.y
        step = gcd(dx, dy)
        dx, dy = dx // step, dy // step
        offset = dx * first.y - dy * first.x
        key = (dx, dy, offset)
        lines[key].append((first.x * dx + first.y * dy, last.x * dx + last.y * dy, first, last))
    out: list[tuple[Point, Point]] = []
    for pieces in lines.values():
        pieces.sort(key=lambda piece: (piece[0], piece[1]))
        _, high, start, end = pieces[0]
        for t0, t1, s, e in pieces[1:]:
            if t0 <= high:
                if t1 > high:
                    high, end = t1, e
            else:
                out.append((start, end))
                high, start, end = t1, s, e
        out.append((start, end))
    return tuple(sorted(out, key=lambda seg: (seg[0].x, seg[0].y, seg[1].x, seg[1].y)))


# --- items ---------------------------------------------------------------------------------------------


def items(sheet: DrawnSheet) -> list[Item]:
    """The items of ``sheet`` that level S matches as a multiset (every item but its symbols)."""
    found: list[Item] = []
    for start, end in merged(sheet.segments()):
        found.append(("wire", (start, end), ()))
    for start, end in merged(sheet.bus_segments()):
        found.append(("bus", (start, end), ()))
    for junction in sheet.junctions:
        found.append(("junction", (junction.at,), (("diameter", str(junction.diameter)),)))
    for point in sheet.no_connects:
        found.append(("no_connect", (point,), ()))
    for label in sheet.labels:
        found.append(
            (
                f"label.{label.kind}",
                (label.at,),
                (("text", label.text), ("rotation", str(label.rotation)), ("shape", label.shape)),
            )
        )
    for power in sheet.powers:
        found.append(
            (
                "power",
                (power.at,),
                (
                    ("symbol", power.symbol),
                    ("net", power.net),
                    ("rotation", str(power.rotation)),
                    *_field_attributes(power.fields),
                ),
            )  # fmt: skip
        )
    for entry in sheet.bus_entries:
        found.append(("bus_entry", (entry.at,), (("size", _point(entry.size)),)))
    for ref in sheet.sheet_refs:
        pins = ";".join(f"{p.name}/{p.shape}@{_point(p.at)}/{p.rotation}" for p in ref.pins)
        found.append(
            (
                "sheet_ref",
                (ref.at,),
                (
                    ("name", ref.name),
                    ("size", f"{ref.size.w},{ref.size.h}"),
                    ("pins", pins),
                ),
            )  # fmt: skip
        )
    for alias in sheet.bus_aliases:
        found.append(("bus_alias", (), (("name", alias.name), ("members", " ".join(alias.members)))))
    for opaque in sheet.opaques:
        digest = hashlib.sha256(opaque.kicad.encode("utf-8")).hexdigest()
        found.append(("opaque", (), (("sha256", digest),)))
    return found


def _field_attributes(fields: Sequence[DrawnField]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (f"fields.{f.name}", f"{_point(f.at)}/{f.rotation}/{f.justify}/{'hide' if f.hide else 'show'}")
        for f in fields
    )


def _shown(item: Item) -> str:
    kind, points, attributes = item
    parts = [" ".join(_point(p) for p in points)] if points else []
    parts += [f"{name}={value}" for name, value in attributes]
    return f"{kind} " + " ".join(parts) if parts else kind


def _item_where(path: str, item: Item) -> str:
    kind, points, attributes = item
    if points:
        return f"{path}:{kind}@{_point(points[0])}"
    return f"{path}:{kind}:{attributes[0][1]}"


def _close(a: Item, b: Item, tolerances: Tolerances) -> bool:
    return len(a[1]) == len(b[1]) and all(
        points_equal(p, q, tolerances) for p, q in zip(a[1], b[1], strict=True)
    )


def _take(left: list[Item], right: list[Item], same: Callable[[Item, Item], bool]) -> list[tuple[Item, Item]]:
    """Pair items of ``left`` and ``right`` for which ``same`` holds, in order, removing them from both."""
    pairs: list[tuple[Item, Item]] = []
    for item in list(left):
        match = next((other for other in right if same(item, other)), None)
        if match is not None:
            left.remove(item)
            right.remove(match)
            pairs.append((item, match))
    return pairs


def compare_items(path: str, a: list[Item], b: list[Item], tolerances: Tolerances) -> list[Difference]:
    """The differences of two multisets of items: exact matches first, then matches within the tolerance,
    then ``item-field`` for an item of the same kind and position whose attributes differ, and
    ``item-missing`` for the rest."""
    count_a, count_b = Counter(a), Counter(b)
    left = sorted((count_a - count_b).elements(), key=repr)
    right = sorted((count_b - count_a).elements(), key=repr)
    _take(left, right, lambda x, y: x[0] == y[0] and x[2] == y[2] and _close(x, y, tolerances))
    found: list[Difference] = []
    for x, y in _take(left, right, lambda x, y: x[0] == y[0] and bool(x[1]) and _close(x, y, tolerances)):
        attributes_a, attributes_b = dict(x[2]), dict(y[2])
        for name in sorted(attributes_a.keys() | attributes_b.keys()):
            value_a, value_b = attributes_a.get(name, ""), attributes_b.get(name, "")
            if value_a != value_b:
                found.append(
                    _difference("item-field", _item_where(path, x), value_a, value_b, f"{x[0]}.{name}")
                )
    found += [_difference("item-missing", _item_where(path, x), _shown(x), "", x[0]) for x in left]
    found += [_difference("item-missing", _item_where(path, y), "", _shown(y), y[0]) for y in right]
    return found


# --- symbols -------------------------------------------------------------------------------------------


def _symbols(instance: DrawnInstance, sheet: DrawnSheet) -> dict[str, DrawnSymbol]:
    found: dict[str, DrawnSymbol] = {}
    for symbol in sheet.symbols:
        key = f"{instance.component(symbol.part)}:{symbol.unit}"
        found.setdefault(key, symbol)
    return found


def compare_symbols(
    path: str, a: Mapping[str, DrawnSymbol], b: Mapping[str, DrawnSymbol], tolerances: Tolerances
) -> list[Difference]:
    """``symbol-missing``, ``symbol-pose`` (``at``, ``rotation``, ``mirror``) and ``symbol-field``
    (``fields.<name>`` and its ``at``, ``rotation``, ``justify`` and ``hide``) of two sheets' symbols."""
    found: list[Difference] = []
    for key in sorted(a.keys() | b.keys(), key=natural):
        where = f"{path}:{key}"
        x, y = a.get(key), b.get(key)
        if x is None or y is None:
            found.append(_difference("symbol-missing", where, key if x else "", key if y else ""))
            continue
        if not points_equal(x.at, y.at, tolerances):
            found.append(_difference("symbol-pose", where, _point(x.at), _point(y.at), "at"))
        if not angles_equal(x.rotation, y.rotation, tolerances):
            found.append(_difference("symbol-pose", where, str(x.rotation), str(y.rotation), "rotation"))
        if x.mirror != y.mirror:
            found.append(_difference("symbol-pose", where, x.mirror, y.mirror, "mirror"))
        fields_a = {f.name: f for f in x.fields}
        fields_b = {f.name: f for f in y.fields}
        for name in sorted(fields_a.keys() | fields_b.keys()):
            fa, fb = fields_a.get(name), fields_b.get(name)
            if fa is None or fb is None:
                found.append(
                    _difference(
                        "symbol-field", where, name if fa else "", name if fb else "", f"fields.{name}"
                    )
                )
                continue
            if not points_equal(fa.at, fb.at, tolerances):
                found.append(
                    _difference("symbol-field", where, _point(fa.at), _point(fb.at), f"fields.{name}.at")
                )
            for attribute in ("rotation", "justify", "hide"):
                va, vb = getattr(fa, attribute), getattr(fb, attribute)
                if va != vb:
                    found.append(
                        _difference("symbol-field", where, str(va), str(vb), f"fields.{name}.{attribute}")
                    )
    return found


def _sheet_fields(path: str, a: DrawnSheet, b: DrawnSheet) -> list[Difference]:
    found: list[Difference] = []
    if a.paper != b.paper:
        found.append(_difference("item-field", f"{path}:sheet", a.paper, b.paper, "sheet.paper"))
    block_a, block_b = dict(a.title_block), dict(b.title_block)
    for name in sorted(block_a.keys() | block_b.keys()):
        if block_a.get(name, "") != block_b.get(name, ""):
            found.append(
                _difference(
                    "item-field",
                    f"{path}:sheet",
                    block_a.get(name, ""),
                    block_b.get(name, ""),
                    f"sheet.title_block.{name}",
                )  # fmt: skip
            )
    return found


# --- nets ----------------------------------------------------------------------------------------------


def _groups(netlist: DrawnNetlist) -> dict[Element, frozenset[Element]]:
    found: dict[Element, frozenset[Element]] = {}
    for net in netlist.nets:
        members = frozenset(net.members)
        for element in net.members:
            found[element] = members
    return found


def _members(group: frozenset[Element], common: frozenset[Element]) -> str:
    kept = sorted(group & common, key=lambda e: (natural(e[0]), natural(e[1])))
    return " ".join(f"{path}-{pin}" for path, pin in kept)


def compare_nets(a: DrawnNetlist, b: DrawnNetlist) -> tuple[list[Difference], int]:
    """``drawn-net`` for the first pin of both drawings, in sorted order, whose group of common pins differs,
    and the count of common pins."""
    common = frozenset(a.pins) & frozenset(b.pins)
    groups_a, groups_b = _groups(a), _groups(b)
    for element in sorted(common, key=lambda e: (natural(e[0]), natural(e[1]))):
        group_a = groups_a.get(element, frozenset({element})) & common
        group_b = groups_b.get(element, frozenset({element})) & common
        if group_a != group_b:
            where = f"{element[0]}-{element[1]}"
            return [
                _difference("drawn-net", where, _members(group_a, common), _members(group_b, common))
            ], len(common)
    return [], len(common)


# --- the level -----------------------------------------------------------------------------------------


def compare_drawn(
    a: DrawnSchematic,
    b: DrawnSchematic,
    *,
    tolerances: Tolerances = EXACT,
    pins_a: Mapping[PinKey, Sequence[PinPoint]],
    pins_b: Mapping[PinKey, Sequence[PinPoint]],
) -> LevelResult:
    """Level S of ``a`` against ``b`` (module docstring): the located differences in ``(where, kind, field)``
    order, and the counts of instances, symbols, items and common pins compared."""
    walked_a, walked_b = a.walk()[0], b.walk()[0]
    by_path_a = {_path(i): i for i in walked_a}
    by_path_b = {_path(i): i for i in walked_b}
    found: list[Difference] = []
    for path in sorted(by_path_a.keys() ^ by_path_b.keys(), key=natural):
        x, y = by_path_a.get(path), by_path_b.get(path)
        found.append(_difference("sheet-missing", path, x.sheet if x else "", y.sheet if y else ""))
    seen: set[tuple[str, str]] = set()
    symbols = 0
    item_count = 0
    for instance in walked_a:
        path = _path(instance)
        other = by_path_b.get(path)
        if other is None or (instance.sheet, other.sheet) in seen:
            continue
        seen.add((instance.sheet, other.sheet))
        sheet_a, sheet_b = a.sheet(instance.sheet), b.sheet(other.sheet)
        if sheet_a is None or sheet_b is None:
            continue
        found += _sheet_fields(path, sheet_a, sheet_b)
        symbols_a, symbols_b = _symbols(instance, sheet_a), _symbols(other, sheet_b)
        symbols += len(symbols_a.keys() | symbols_b.keys())
        found += compare_symbols(path, symbols_a, symbols_b, tolerances)
        items_a, items_b = items(sheet_a), items(sheet_b)
        item_count += max(len(items_a), len(items_b))
        found += compare_items(path, items_a, items_b, tolerances)
    nets, pins = compare_nets(resolve(a, pins_a), resolve(b, pins_b))
    found += nets
    ordered = tuple(sorted(found, key=lambda d: (d.where, d.kind, d.field, d.a, d.b)))
    instances = len(by_path_a.keys() | by_path_b.keys())
    summary = {"instances": instances, "symbols": symbols, "items": item_count, "pins": pins}
    return LevelResult(SCHEMATIC_LEVEL, instances + symbols + item_count + pins, ordered, summary=summary)


__all__ = ["compare_drawn", "compare_items", "compare_nets", "compare_symbols", "items", "merged"]
