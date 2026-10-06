# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The exact differences between two models (capability verification-loop, "Model difference report").

Entities with a name are matched by it (a component by its reference, a net by its name, a pad by
``REF-NUMBER``); copper and graphics are matched by content. Ids, native ids and provenance never take
part, and a reference by id is replaced by the key of the entity it names, so two designs built from the
same data with different seeds are equal. The report gives no verdict and removes no frame.

``diff_designs`` takes a ``ModelScope`` (capability verification-loop, "Model difference scope"; change
c0044): only the kinds and fields of the scope are compared, and two lengths are equal when they differ by
at most the scope's tolerance. Without a scope every comparison is exact.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from functools import cache
from typing import Any, cast

from fenolite.backends.base import Change, ChangeKind, DiffReport, ModelScope
from fenolite.model.base import Entity
from fenolite.model.board import (
    Arc,
    FootprintInstance,
    Graphic,
    Hole,
    Keepout,
    Layer,
    Pad,
    StackLayer,
    Text,
    Track,
    Via,
    Zone,
)
from fenolite.model.circuit import Component, Interface, Module, Net, NetClass, PinRef
from fenolite.model.design import Design
from fenolite.model.library import Library
from fenolite.model.rules import Rule
from fenolite.model.schematic import SchematicSheet

NEVER = frozenset({"id", "native_ids", "provenance"})
"""Fields of an entity that no comparison reads; ``ext`` joins them unless ``ext=True``."""
KEYED_KINDS = (
    "design", "component", "net", "netclass", "interface", "module", "no_connect", "layer", "footprint",
    "pad", "footprint_def", "symbol_def", "sheet", "symbol", "sheet_ref", "lib_symbol",
)  # fmt: skip
SINGLE_KINDS = frozenset({"design", "sheet"})
"""Kinds with one entity and no key: the values a design or a sheet holds once."""
CONTENT_KINDS = (
    "track", "arc", "via", "zone", "keepout", "text", "graphic", "hole", "rule", "stack_layer",
    "label", "no_connect_flag",
)  # fmt: skip

KIND_CLASSES: Mapping[str, type] = {
    "component": Component, "net": Net, "netclass": NetClass, "interface": Interface, "module": Module,
    "layer": Layer, "footprint": FootprintInstance, "pad": Pad, "track": Track, "arc": Arc, "via": Via,
    "zone": Zone, "keepout": Keepout, "text": Text, "graphic": Graphic, "hole": Hole, "rule": Rule,
    "stack_layer": StackLayer,
}  # fmt: skip
"""The model class of each kind of a design that has one (``design`` and ``no_connect`` have none)."""
_LENGTH_TYPE = re.compile(r"\b(Nm|Point|Size)\b")


@cache
def length_fields(kind: str) -> frozenset[str]:
    """The fields of ``kind`` that hold lengths: those typed ``Nm``, ``Point`` or ``Size``, or a sequence of
    them. Only these take a scope's tolerance."""
    cls = KIND_CLASSES.get(kind)
    if cls is None:
        return frozenset()
    return frozenset(f.name for f in dataclasses.fields(cls) if _LENGTH_TYPE.search(str(f.type)))


def _text(value: Any) -> str:
    """The compact canonical JSON of a compared value."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _segment(key: str) -> str:
    """A key as one path segment, escaped as in a JSON pointer (``~0`` for ``~``, ``~1`` for ``/``)."""
    return key.replace("~", "~0").replace("/", "~1")


def _numbered(keys: Iterable[str]) -> list[str]:
    """``keys`` with ``#<k>`` appended to the k-th further use of one key, so every key is unique."""
    seen: Counter[str] = Counter()
    out: list[str] = []
    for key in keys:
        out.append(key if not seen[key] else f"{key}#{seen[key]}")
        seen[key] += 1
    return out


class _Names:
    """What the ids of one model name: components by reference, nets and classes by key."""

    def __init__(self, design: Design | None, *, ext: bool) -> None:
        self.ext = ext
        self.refs: dict[str, str] = {}
        self.nets: dict[str, str] = {}
        self.classes: dict[str, str] = {}
        self.modules: dict[str, str] = {}
        if design is None:
            return
        circuit = design.circuit
        self.refs = {c.id: c.ref for c in circuit.components}
        self.classes = {c.id: c.name for c in circuit.netclasses}
        self.modules = {m.id: m.path for m in circuit.modules}
        self.nets = {n.id: n.name or ",".join(self.members(n.members)) for n in circuit.nets}

    def pin(self, ref: PinRef) -> str:
        return f"{self.refs.get(ref.component_id, ref.component_id)}-{ref.pin}"

    def members(self, members: Iterable[PinRef]) -> list[str]:
        return sorted(self.pin(m) for m in members)

    def value(self, value: Any, field: str = "", *, ordered: bool = True) -> Any:
        """The compared form of ``value``: plain JSON without ids, with names in place of references."""
        if isinstance(value, PinRef):
            return self.pin(value)
        if isinstance(value, str):
            names = {
                "net_id": self.nets,
                "netclass_id": self.classes,
                "component_id": self.refs,
                "parent": self.modules,
            }.get(field)
            return value if names is None else names.get(value, value)
        if value is None or isinstance(value, (bool, int)):
            return value
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            return self.fields(value, defaults=False)
        if isinstance(value, Mapping):
            mapping = cast(Mapping[Any, Any], value)
            if field == "ext":
                return hashlib.sha256(_text(self._ext(mapping)).encode("utf-8")).hexdigest()
            inner = "net_id" if field == "members" else ""  # an interface maps its roles to nets
            return {str(k): self.value(v, inner) for k, v in mapping.items()}
        if isinstance(value, (tuple, list)):
            sequence = cast(Sequence[Any], value)
            if field == "component_ids":
                return sorted(self.refs.get(str(i), str(i)) for i in sequence)
            items = [self.value(item) for item in sequence]
            unordered = not ordered and all(isinstance(i, (Entity, PinRef)) for i in sequence)
            return sorted(items, key=_text) if unordered else items
        raise TypeError(f"cannot compare a value of type {type(value).__name__}")

    def _ext(self, bags: Mapping[Any, Any]) -> Any:
        return {
            str(name): {"min_version": bag.min_version, "payload": [list(pair) for pair in bag.payload]}
            for name, bag in bags.items()
        }

    def fields(self, obj: Any, *, defaults: bool, skip: frozenset[str] = frozenset()) -> dict[str, Any]:
        """The compared fields of a dataclass; a nested value leaves its default fields out."""
        out: dict[str, Any] = {}
        entity = isinstance(obj, Entity)
        for f in dataclasses.fields(obj):
            if f.name in skip or (entity and f.name in NEVER):
                continue
            if entity and f.name == "ext" and not self.ext:
                continue
            item = getattr(obj, f.name)
            if not defaults and _is_default(f, item):
                continue
            out[f.name] = self.value(item, f.name, ordered=bool(f.metadata.get("ordered", False)))
        return out


def _is_default(f: dataclasses.Field[Any], value: Any) -> bool:
    if f.default is not dataclasses.MISSING:
        return bool(value == f.default)
    if f.default_factory is not dataclasses.MISSING:
        return bool(value == f.default_factory())
    return False


Keyed = dict[str, dict[str, dict[str, Any]]]
"""kind → key → field → compared value."""
Content = dict[str, list[dict[str, Any]]]
"""kind → the compared values of its entities."""


def _pad_keys(owner: str, pads: Sequence[Pad]) -> list[str]:
    return _numbered(f"{owner}-{pad.number}" for pad in pads)


def _design_parts(design: Design, *, ext: bool) -> tuple[Keyed, Content]:
    names = _Names(design, ext=ext)
    circuit = design.circuit
    keyed: Keyed = {kind: {} for kind in KEYED_KINDS}
    content: Content = {kind: [] for kind in CONTENT_KINDS}

    def put(kind: str, keys: Sequence[str], items: Sequence[Any], skip: frozenset[str] = frozenset()) -> None:
        for key, item in zip(_numbered(keys), items, strict=True):
            keyed[kind][key] = names.fields(item, defaults=True, skip=skip)

    put("component", [c.ref for c in circuit.components], circuit.components)
    put("net", [names.nets[n.id] for n in circuit.nets], circuit.nets)
    put("netclass", [c.name for c in circuit.netclasses], circuit.netclasses)
    put("interface", [i.name for i in circuit.interfaces], circuit.interfaces)
    put("module", [m.path for m in circuit.modules], circuit.modules)
    for key in _numbered(sorted(names.pin(mark) for mark in circuit.no_connects)):
        keyed["no_connect"][key] = {}
    single: dict[str, Any] = {}
    board = design.board
    if board is not None:
        put("layer", [layer.name for layer in board.layers], board.layers)
        owners = _numbered(names.refs.get(fp.component_id, fp.component_id) for fp in board.footprints)
        for owner, footprint in zip(owners, board.footprints, strict=True):
            keyed["footprint"][owner] = names.fields(footprint, defaults=True, skip=frozenset({"pads"}))
            for key, pad in zip(_pad_keys(owner, footprint.pads), footprint.pads, strict=True):
                keyed["pad"][key] = names.fields(pad, defaults=True)
        for kind, items in (
            ("track", board.tracks), ("arc", board.arcs), ("via", board.vias), ("zone", board.zones),
            ("keepout", board.keepouts), ("text", board.texts), ("graphic", board.graphics),
            ("hole", board.holes),
        ):  # fmt: skip
            content[kind] = [names.fields(item, defaults=False) for item in items]
        if board.stackup is not None:
            content["stack_layer"] = [names.fields(i, defaults=False) for i in board.stackup.layers]
        single = {
            "outline": names.value(board.outline),
            "finish": board.stackup.finish if board.stackup is not None else "",
            "sheet": names.value(board.sheet),
            "title_block": names.value(board.title_block),
        }
        if ext:
            single["ext"] = names.value(board.ext, "ext")
    if design.rules is not None:
        content["rule"] = [names.fields(rule, defaults=False) for rule in design.rules.rules]
    keyed["design"][""] = single
    return keyed, content


def _library_parts(library: Library, *, ext: bool) -> tuple[Keyed, Content]:
    names = _Names(None, ext=ext)
    keyed: Keyed = {kind: {} for kind in KEYED_KINDS}
    owners = _numbered(fp.lib_id for fp in library.footprints)
    for owner, footprint in zip(owners, library.footprints, strict=True):
        keyed["footprint_def"][owner] = names.fields(footprint, defaults=True, skip=frozenset({"pads"}))
        for key, pad in zip(_pad_keys(owner, footprint.pads), footprint.pads, strict=True):
            keyed["pad"][key] = names.fields(pad, defaults=True)
    for key, symbol in zip(_numbered(s.lib_id for s in library.symbols), library.symbols, strict=True):
        keyed["symbol_def"][key] = names.fields(symbol, defaults=True)
    return keyed, {}


def _sheet_parts(sheet: SchematicSheet, *, ext: bool) -> tuple[Keyed, Content]:
    names = _Names(None, ext=ext)
    keyed: Keyed = {kind: {} for kind in KEYED_KINDS}
    content: Content = {kind: [] for kind in CONTENT_KINDS}
    for key, symbol in zip(_numbered(f"{s.ref}#{s.unit}" for s in sheet.symbols), sheet.symbols, strict=True):
        keyed["symbol"][key] = names.fields(symbol, defaults=True)
    for key, ref in zip(_numbered(r.name for r in sheet.sheets), sheet.sheets, strict=True):
        keyed["sheet_ref"][key] = names.fields(ref, defaults=True)
    for key, symbol in zip(_numbered(s.lib_id for s in sheet.lib_symbols), sheet.lib_symbols, strict=True):
        keyed["lib_symbol"][key] = names.fields(symbol, defaults=True)
    content["label"] = [names.fields(label, defaults=False) for label in sheet.labels]
    content["no_connect_flag"] = [names.fields(flag, defaults=False) for flag in sheet.no_connects]
    single: dict[str, Any] = {
        "paper": names.value(sheet.paper),
        "title_block": names.value(sheet.title_block),
        "pages": names.value(sheet.pages),
    }
    if ext:
        single["ext"] = names.value(sheet.ext, "ext")
    keyed["sheet"][""] = single
    return keyed, content


def _close(a: Any, b: Any, tolerance: int) -> bool:
    """Whether two compared length values are equal within ``tolerance`` nanometres, part by part."""
    if type(a) is int and type(b) is int:
        return abs(a - b) <= tolerance
    if isinstance(a, dict) and isinstance(b, dict):
        left, right = cast(dict[str, Any], a), cast(dict[str, Any], b)
        return left.keys() == right.keys() and all(_close(left[k], right[k], tolerance) for k in left)
    if isinstance(a, list) and isinstance(b, list):
        one, other = cast(list[Any], a), cast(list[Any], b)
        return len(one) == len(other) and all(
            _close(x, y, tolerance) for x, y in zip(one, other, strict=True)
        )
    return bool(a == b)


class _Rule:
    """How two values of one field compare: exactly, or within the tolerance for a length field."""

    def __init__(self, tolerance: int = 0) -> None:
        self.tolerance = tolerance

    def lengths(self, kind: str) -> frozenset[str]:
        return length_fields(kind) if self.tolerance else frozenset()

    def same(self, kind: str, field: str, one: Any, other: Any) -> bool:
        if one == other:
            return True
        return field in self.lengths(kind) and _close(one, other, self.tolerance)


def _keyed_changes(
    kind: str, a: dict[str, dict[str, Any]], b: dict[str, dict[str, Any]], rule: _Rule
) -> list[Change]:
    changes: list[Change] = []
    single = kind in SINGLE_KINDS
    for key in sorted(set(a) | set(b)):
        base = f"/{kind}" if single else f"/{kind}/{_segment(key)}"
        if key not in b:
            changes.append(Change(base, "removed", _text(a[key]), ""))
        elif key not in a:
            changes.append(Change(base, "added", "", _text(b[key])))
        else:
            left, right = a[key], b[key]
            for field in sorted(set(left) | set(right)):
                one, other = left.get(field), right.get(field)
                if not rule.same(kind, field, one, other):
                    changes.append(Change(f"{base}/{field}", "changed", _text(one), _text(other)))
    return changes


def _unmatched(
    kind: str, a: list[dict[str, Any]], b: list[dict[str, Any]], rule: _Rule
) -> tuple[list[str], list[str]]:
    """The compact canonical JSON of the entities of each side that match no entity of the other, in
    canonical order. Without a tolerance two entities match when their texts are equal. With one, each
    entity of ``a`` takes, in canonical order, the first unmatched entity of ``b`` that is equal under it."""
    lengths = rule.lengths(kind)
    if not lengths:
        left, right = Counter(_text(i) for i in a), Counter(_text(i) for i in b)
        return sorted((left - right).elements()), sorted((right - left).elements())

    def exact(item: dict[str, Any]) -> str:
        return _text({name: value for name, value in item.items() if name not in lengths})

    ordered_a = sorted(a, key=_text)
    ordered_b = sorted(b, key=_text)
    buckets: dict[str, list[int]] = {}
    for index, item in enumerate(ordered_b):
        buckets.setdefault(exact(item), []).append(index)
    taken: set[int] = set()
    removed: list[str] = []
    for item in ordered_a:
        for index in buckets.get(exact(item), ()):
            other = ordered_b[index]
            if index not in taken and all(rule.same(kind, n, item.get(n), other.get(n)) for n in lengths):
                taken.add(index)
                break
        else:
            removed.append(_text(item))
    added = [_text(item) for index, item in enumerate(ordered_b) if index not in taken]
    return removed, added


def _content_changes(
    kind: str, a: list[dict[str, Any]], b: list[dict[str, Any]], rule: _Rule
) -> list[Change]:
    """Entities match when their compared values are equal, each at most once; the others are numbered
    per side in the order of their compact canonical JSON."""
    removed, added = _unmatched(kind, a, b, rule)
    return [
        *(Change(f"/{kind}/{n}", "removed", text, "") for n, text in enumerate(removed)),
        *(Change(f"/{kind}/{n}", "added", "", text) for n, text in enumerate(added)),
    ]


def _report(a: tuple[Keyed, Content], b: tuple[Keyed, Content], rule: _Rule | None = None) -> DiffReport:
    how = rule if rule is not None else _Rule()
    changes: list[Change] = []
    for kind in KEYED_KINDS:
        changes += _keyed_changes(kind, a[0].get(kind, {}), b[0].get(kind, {}), how)
    for kind in CONTENT_KINDS:
        changes += _content_changes(kind, a[1].get(kind, []), b[1].get(kind, []), how)
    changes.sort(key=lambda change: (change.path, change.change))
    summary: dict[str, dict[str, int]] = {}
    for change in changes:
        kind = change.path.split("/")[1]
        counts = summary.setdefault(kind, {"added": 0, "removed": 0, "changed": 0})
        counts[change.change] += 1
    return DiffReport(not changes, tuple(changes), dict(sorted(summary.items())))


def _scoped(parts: tuple[Keyed, Content], scope: ModelScope) -> tuple[Keyed, Content]:
    """``parts`` cut to the kinds and the fields of ``scope``."""
    keyed, content = parts
    cut_keyed: Keyed = {}
    cut_content: Content = {}
    for kind, fields in scope.fields.items():
        wanted = set(fields)
        if kind in keyed:
            cut_keyed[kind] = {
                key: {name: value for name, value in entity.items() if name in wanted}
                for key, entity in keyed[kind].items()
            }
        if kind in content:
            cut_content[kind] = [
                {name: value for name, value in entity.items() if name in wanted} for entity in content[kind]
            ]
    return cut_keyed, cut_content


def diff_designs(a: Design, b: Design, *, scope: ModelScope | None = None, ext: bool = False) -> DiffReport:
    """Every difference between two designs. ``ext=True`` also compares the extension bags, as hashes.

    With a ``scope`` only its kinds and, for each, its fields are compared, and two lengths are equal when
    they differ by at most ``scope.length_tolerance``; a kind's ``a`` and ``b`` texts then hold the scoped
    fields only."""
    left, right = _design_parts(a, ext=ext), _design_parts(b, ext=ext)
    if scope is None:
        return _report(left, right)
    return _report(_scoped(left, scope), _scoped(right, scope), _Rule(scope.length_tolerance))


def diff_libraries(a: Library, b: Library, *, ext: bool = False) -> DiffReport:
    """Every difference between two libraries: definitions by ``<library>:<name>``, pads by number."""
    return _report(_library_parts(a, ext=ext), _library_parts(b, ext=ext))


def diff_sheets(a: SchematicSheet, b: SchematicSheet, *, ext: bool = False) -> DiffReport:
    """Every difference between two schematic sheets: symbols by ``<ref>#<unit>``, sheet references by
    name, embedded symbols by their name, labels and no-connect flags by content. The paper, the title
    block and the pages are ``/sheet/<field>``; the sheet's name is not compared. Wires, junctions and
    buses are not modelled: ``ext=True`` compares them with the rest of the opaque content, as a hash."""
    return _report(_sheet_parts(a, ext=ext), _sheet_parts(b, ext=ext))


__all__ = [
    "CONTENT_KINDS",
    "KEYED_KINDS",
    "KIND_CLASSES",
    "Change",
    "ChangeKind",
    "DiffReport",
    "diff_designs",
    "diff_libraries",
    "diff_sheets",
    "length_fields",
]
