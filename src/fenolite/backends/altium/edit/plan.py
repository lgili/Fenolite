# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The edit plan of a PCB edit session and its replay onto a newer save (change c0502).

An operation is held as its ops-file entry (change c0497, D1): ``{"op": <Session method>, "item": <tagged
item>, ...keyword arguments}``, lengths in integer nanometres, angles as exact text with a unit
(``"90deg"``). ``Session.plan()`` records, per operation, the identity of its target and the ``base`` and
``result`` fingerprints of that target (design D2, D3). ``replay(plan, path)`` queues the same operations on
another document, each after a three-way rebase step (design D4): the rule of
``lens.edits.merge_property``, written again here because ``backends`` does not import ``lens``.
"""

# evidence: see edit.session

from __future__ import annotations

import hashlib
import inspect
import json
import types
import typing
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any, Literal, cast

from fenolite.backends.altium.edit import ops
from fenolite.backends.altium.edit.ops import Component, Polygon, Refused
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.pcbrecords import layer_text
from fenolite.backends.altium.read.pcbprims import (
    ArcRecord,
    FillRecord,
    RegionRecord,
    TextRecord,
    TrackRecord,
    ViaRecord,
)
from fenolite.core.errors import FormatError, Issue
from fenolite.core.schema_ids import accepts_schema
from fenolite.core.units import format_angle, parse_angle, parse_length, u_to_nm

SCHEMA = "fenolite.altium-edit-plan.v0"
OPS = frozenset({
    "delete", "move", "rotate", "flip", "set_property", "clone", "remap_layer", "set_rule", "set_outline",
    "add_arc", "add_fill", "add_region", "add_polygon", "declare_connectivity", "add_board_cutout",
    "add_polygon_cutout", "set_via_mask", "draw_board_shape",
})  # fmt: skip
"""The ``Session`` methods an ops-file entry may name (change c0497)."""
PLAN_OPS = OPS | {"add_component", "link", "unpour"}
"""The operations a plan may hold: those of a session, with their source paths relative to the document."""
PATHS = ("from_doc", "project")
"""The arguments that name a file, held relative to the document's folder."""
MADE = frozenset({"add_arc", "add_fill", "add_region", "add_polygon", "clone", "add_component"})
TARGETED = frozenset({"delete", "move", "rotate", "flip", "set_property", "set_outline", "unpour"})
POSITION = frozenset({"start", "end", "centre", "radius", "corner", "opposite", "at", "outline", "x", "y"})
LENGTHS = frozenset({"width", "radius", "diameter", "hole"})
Status = Literal["applied", "already-applied", "conflict", "missing"]


class EntryError(ValueError):
    """An ops-file entry that does not read: ``index`` is its position in the list."""

    def __init__(self, index: int, message: str) -> None:
        super().__init__(f"entry {index}: {message}")
        self.index = index
        self.message = message


# --- entries: Python values to JSON and back ----------------------------------------------------------


def angle(degrees: float) -> str:
    """``degrees`` as exact text in degrees, rounded to the microdegree: a plan holds no float."""
    return format_angle(round(degrees * 1_000_000))


def plain(value: object) -> object:
    """``value`` in the JSON form of an entry: an item as a tagged object, a point as a list."""
    if is_dataclass(value) and not isinstance(value, type):
        held = {f.name: getattr(value, f.name) for f in fields(value)}
        return {
            "kind": type(value).__name__.lower(),
            **{k: plain(v) for k, v in held.items() if v is not None},
        }
    if isinstance(value, Mapping):
        return {str(k): plain(v) for k, v in cast("Mapping[object, object]", value).items()}
    if isinstance(value, tuple | list):
        return [plain(v) for v in cast("Sequence[object]", value)]
    return value


def entry(op: str, **arguments: object) -> dict[str, Any]:
    """The ops-file entry of one queued operation."""
    return {"op": op, **{k: plain(v) for k, v in arguments.items()}}


def _items() -> dict[str, type]:
    return {
        "track": ops.Track, "arc": ops.Arc, "fill": ops.Fill, "via": ops.Via, "vias": ops.Vias,
        "component": ops.Component, "polygon": ops.Polygon, "text": ops.Text, "region": ops.Region,
        "designator": ops.Designator, "comment": ops.Comment,
    }  # fmt: skip


def _length(value: object, index: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise EntryError(index, f"{value!r} is not a length: give nanometres or text with a unit")
    if isinstance(value, int):
        return value
    try:
        return parse_length(value.strip())
    except ValueError as error:
        raise EntryError(index, f"{value!r}: {error}") from None


def _convert(value: object, hint: object, index: int) -> object:
    """``value`` read as the type ``hint``: lengths as nanometres, angles from numbers or text with a unit,
    points as tuples, items from objects."""
    origin, args = typing.get_origin(hint), typing.get_args(hint)
    if origin in (typing.Union, types.UnionType):
        if value is None and type(None) in args:
            return None
        if isinstance(value, dict) and any(a in _items().values() for a in args):
            return item(cast("dict[str, Any]", value), index)
        kept = [a for a in args if a is not type(None)]
        given = cast(object, value)
        return _convert(given, kept[0], index) if len(kept) == 1 or int in kept else given
    if hint is int:
        return _length(value, index)
    if hint is float:
        if isinstance(value, str):
            try:
                return parse_angle(value.strip(), default_unit="deg") / 1_000_000
            except ValueError as error:
                raise EntryError(index, f"{value!r}: {error}") from None
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise EntryError(index, f"{value!r} is not a number")
        return float(value)
    if hint is bool:
        if not isinstance(value, bool):
            raise EntryError(index, f"{value!r} is not true or false")
        return value
    if origin is tuple:
        if not isinstance(value, list) or len(cast("list[object]", value)) != len(args):
            raise EntryError(index, f"{value!r} is not a point [x, y]")
        return tuple(_convert(v, a, index) for v, a in zip(cast("list[object]", value), args, strict=True))
    if origin in (list, Sequence) or (
        isinstance(origin, type) and issubclass(origin, Sequence) and origin is not str
    ):
        if not isinstance(value, list):
            raise EntryError(index, f"{value!r} is not a list")
        return [_convert(v, args[0], index) for v in cast("list[object]", value)]
    if isinstance(hint, type) and hint in _items().values():
        if not isinstance(value, dict):
            raise EntryError(index, f"{value!r} is not an item object")
        return item(cast("dict[str, Any]", value), index)
    return value


def item(value: Mapping[str, Any], index: int = 0) -> Any:
    """The item of a tagged object ``{"kind": ..., ...fields}``."""
    kinds = _items()
    kind = value.get("kind")
    if kind not in kinds:
        raise EntryError(index, f"the item kind {kind!r} is not one of {', '.join(sorted(kinds))}")
    cls = kinds[str(kind)]
    hints = typing.get_type_hints(cls)
    given = {k: v for k, v in value.items() if k != "kind"}
    unknown = set(given) - set(hints)
    if unknown:
        raise EntryError(index, f"the item {kind} has no field {', '.join(sorted(unknown))}")
    try:
        return cls(**{k: _convert(v, hints[k], index) for k, v in given.items()})
    except TypeError as error:
        raise EntryError(index, f"the item {kind}: {error}") from None


def queue(session: Any, value: object, index: int, *, allowed: frozenset[str] = OPS) -> None:
    """Queue the entry ``value`` on ``session``; an entry that does not read raises ``EntryError``. A path
    argument is read relative to the session's document folder."""
    if not isinstance(value, dict):
        raise EntryError(index, 'an entry is an object {"op": ..., ...}')
    given = dict(cast("dict[str, Any]", value))
    op = given.pop("op", None)
    if op not in allowed:
        raise EntryError(index, f"the op {op!r} is not one of {', '.join(sorted(allowed))}")
    digest = given.pop("sha256", None) if op == "add_component" else None
    for name in PATHS:
        if isinstance(given.get(name), str):
            given[name] = Path(session.path).parent / given[name]
    if digest is not None and hashlib.sha256(Path(given["from_doc"]).read_bytes()).hexdigest() != digest:
        raise EntryError(index, f"the source {Path(given['from_doc']).name} is not the one the plan read")
    method = getattr(session, str(op))
    hints = typing.get_type_hints(method)
    parameters = list(inspect.signature(method).parameters.values())
    if "item" in given and parameters and parameters[0].name in ("item", "selector"):
        given[parameters[0].name] = given.pop("item")
    names = {p.name for p in parameters}
    loose = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters)
    unknown = set(given) - names
    if unknown and not loose:
        raise EntryError(index, f"{op} takes no argument {', '.join(sorted(unknown))}")
    args: list[object] = []
    kwargs: dict[str, object] = {k: _loose(given[k]) for k in unknown}
    for parameter in parameters:
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            args += list(cast("list[object]", given.get("nets", [])))
            continue
        if parameter.kind is inspect.Parameter.VAR_KEYWORD:
            continue
        if parameter.name not in given:
            if parameter.default is inspect.Parameter.empty:
                raise EntryError(index, f"{op} needs the argument {parameter.name}")
            continue
        kwargs[parameter.name] = _convert(given[parameter.name], hints.get(parameter.name), index)
    try:
        method(*args, **kwargs)
    except TypeError as error:
        raise EntryError(index, f"{op}: {error}") from None


def _loose(value: object) -> object:
    """A ``clone`` change: a point as a tuple, every other value as given."""
    if isinstance(value, list):
        return tuple(cast("list[object]", value))
    return value


# --- fingerprints -------------------------------------------------------------------------------------


def _held(value: object) -> object:
    """A value as the document holds it, with no float: a double as its exact ``repr``."""
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, tuple | list):
        return [_held(v) for v in cast("Sequence[object]", value)]
    return value


def _layer(layer: int) -> str:
    try:
        return layer_text(layer)
    except ValueError:
        return str(layer)


def record_fields(state: State, storage: str, position: int) -> dict[str, object]:
    """Every field of the record that a fingerprint may hold (design D2), as the document holds it."""
    view = ops.View(state)
    if storage == "Components6":
        record = view.components[position]
        keys = {
            "designator": "SOURCEDESIGNATOR",
            "x": "X",
            "y": "Y",
            "rotation": "ROTATION",
            "layer": "LAYER",
        }
        return {name: record.get(key) for name, key in keys.items()}
    if storage == "Polygons6":
        record = state.properties(storage)[position]
        outline = [[x, y, kind] for x, y, kind in ops._outline(record)]  # pyright: ignore[reportPrivateUsage]
        return {"name": ops._polygon_name(record), "layer": record.get("LAYER"),  # pyright: ignore[reportPrivateUsage]
                "net": record.get("NET"), "outline": outline}  # fmt: skip
    p = state.typed(storage)[position]
    net = view.net_name(getattr(getattr(p, "prefix", None), "net", None))
    if isinstance(p, TrackRecord):
        out: dict[str, object] = {"start": [p.x1, p.y1], "end": [p.x2, p.y2], "width": p.width}
    elif isinstance(p, ArcRecord):
        out = {"centre": [p.cx, p.cy], "radius": p.radius, "angles": [p.start_angle, p.end_angle],
               "width": p.width}  # fmt: skip
    elif isinstance(p, FillRecord):
        out = {"corner": [p.x1, p.y1], "opposite": [p.x2, p.y2], "rotation": p.rotation}
    elif isinstance(p, ViaRecord):
        out = {"at": [p.x, p.y], "diameter": p.diameter, "hole": p.hole, "tented": [p.tented_top,
               p.tented_bottom]}  # fmt: skip
    elif isinstance(p, TextRecord):
        out = {"at": [p.x, p.y], "rotation": p.rotation, "text": view.shown(p)}
    elif isinstance(p, RegionRecord):
        out = {"outline": [[v.x, v.y] for v in p.outline]}
    else:
        return {"raw": hashlib.sha256(state.get(storage)[position]).hexdigest()}
    out["layer"] = _layer(p.prefix.layer)
    if not isinstance(p, TextRecord):
        out["net"] = net
    return {k: _held(v) for k, v in out.items()}


def _property(state: State, value: Mapping[str, Any], storage: str, position: int, key: str) -> object:
    """The value the key ``key`` of ``set_property`` reads, as the document holds it."""
    target = item(value["item"])
    if isinstance(target, Component) and key.lower() == "comment":
        view = ops.View(state)
        owned = ops.component_primitives(state, position).get("Texts6", [])
        texts = [t for i in owned if isinstance(t := state.typed("Texts6")[i], TextRecord) and t.is_comment]
        return view.shown(texts[0]) if len(texts) == 1 else None
    if isinstance(target, Component | Polygon):
        records = ops.View(state).components if storage == "Components6" else state.properties(storage)
        return records[position].get(key)
    return record_fields(state, storage, position).get(key.lower())


def fingerprint(state: State, value: Mapping[str, Any], storage: str, position: int) -> dict[str, object]:
    """The fields of the target at ``position`` of ``storage`` that the entry ``value`` reads or writes
    (design D2), with the storage."""
    op = value["op"]
    if op == "set_rule":
        record = state.properties("Rules6")[position]
        paired = ops.PAIRED_RULE_KEYS.get(value["key"])
        held = {value["key"]: record.get(value["key"])}
        if paired is not None and record.get(paired) is not None:
            held[paired] = record.get(paired)
        return {"storage": "Rules6", **held}
    if op == "set_property":
        return {
            "storage": storage,
            value["key"]: _held(_property(state, value, storage, position, value["key"])),
        }
    every = record_fields(state, storage, position)
    if op == "move":
        keep = POSITION | {"layer", "net"} | set(cast("Mapping[str, object]", value.get("expect") or {}))
    elif op in ("rotate", "flip"):
        keep = POSITION | {"rotation", "layer"}
    elif op in ("set_outline", "unpour"):
        keep = {"outline", "layer", "net"}
    elif storage in ("Components6", "Polygons6") and op != "add_component":
        keep = set(every) - {"designator", "name"}  # the unique id names it (design D2)
    else:
        keep = set(every)
    return {"storage": storage, **{k: v for k, v in every.items() if k in keep}}


# --- identity -------------------------------------------------------------------------------------------


def _unique_id(state: State, storage: str, position: int) -> str | None:
    if storage not in ("Components6", "Polygons6"):
        return None
    return state.properties(storage)[position].get("UNIQUEID")


def _rule(state: State, name: str) -> int | None:
    found = [i for i, r in enumerate(state.properties("Rules6")) if r.get("NAME") == name]
    return found[0] if len(found) == 1 else None


def locate(state: State, value: dict[str, Any], target: Mapping[str, Any] | None) -> tuple[str, int] | None:
    """The storage and position of the entry's target: by ``UNIQUEID`` first, then by its content key; the
    entry's item is renamed to the record found by its unique id (design D2)."""
    if value["op"] == "set_rule":
        position = _rule(state, value["name"])
        return None if position is None else ("Rules6", position)
    unique = None if target is None else target.get("unique_id")
    stated = item(value["item"])
    if unique is not None and isinstance(stated, Component | Polygon):
        storage = "Components6" if isinstance(stated, Component) else "Polygons6"
        for position, record in enumerate(state.properties(storage)):
            if record.get("UNIQUEID") == unique:
                if isinstance(stated, Component):
                    value["item"] = plain(Component(record.get("SOURCEDESIGNATOR") or stated.designator))
                else:
                    value["item"] = plain(Polygon(ops._polygon_name(record)))  # pyright: ignore[reportPrivateUsage]
                return storage, position
    try:
        return ops.View(state).find(stated)
    except Refused:
        return None


def _made(state: State, lengths: Mapping[str, int]) -> tuple[str, int] | None:
    """The record an operation appended: the first storage that grew, its last record."""
    for storage in ("Components6", "Polygons6", "Tracks6", "Arcs6", "Fills6", "Vias6", "Texts6", "Regions6"):
        if state.has(storage) and len(state.get(storage)) > lengths.get(storage, 0):
            return storage, len(state.get(storage)) - 1
    return None


def _lengths(state: State) -> dict[str, int]:
    names = ("Components6", "Polygons6", "Tracks6", "Arcs6", "Fills6", "Vias6", "Texts6", "Regions6")
    return {s: len(state.get(s)) for s in names if state.has(s)}


def _held_anywhere(state: State, value: Mapping[str, Any], result: Mapping[str, object]) -> bool:
    storage = str(result["storage"])
    if not state.has(storage):
        return False
    return any(fingerprint(state, value, storage, i) == result for i in range(len(state.get(storage))))


# --- the plan -------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PlannedOperation:
    """One operation of a plan: its ops-file entry, gate and label, its target's identity, and the target's
    fingerprint before (``base``) and after (``result``) it (design D3)."""

    entry: dict[str, Any]
    gate: str
    label: str
    target: dict[str, Any] | None = None
    base: dict[str, Any] | None = None
    result: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class EditPlan:
    """The queued operations of a PCB edit session as data (``fenolite.altium-edit-plan.v0``)."""

    document: str
    base_sha256: str
    declared_nets: tuple[str, ...] = ()
    operations: tuple[PlannedOperation, ...] = ()
    schema: Literal["fenolite.altium-edit-plan.v0"] = "fenolite.altium-edit-plan.v0"

    def data(self) -> dict[str, Any]:
        return {
            "schema": self.schema, "document": self.document, "base_sha256": self.base_sha256,
            "declared_nets": list(self.declared_nets),
            "operations": [
                {"entry": o.entry, "gate": o.gate, "label": o.label, "target": o.target, "base": o.base,
                 "result": o.result}
                for o in self.operations
            ],
        }  # fmt: skip

    def text(self) -> str:
        """Canonical JSON: sorted keys, two-space indent, one final newline."""
        return json.dumps(self.data(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"

    @staticmethod
    def read(text: str | bytes, *, file: str = "") -> EditPlan:
        try:
            raw = json.loads(text)
        except ValueError as error:
            raise FormatError(f"an edit plan is JSON: {error}", file=file) from None
        return EditPlan.of(raw, file=file)

    @staticmethod
    def of(raw: object, *, file: str = "") -> EditPlan:
        """The plan of the parsed JSON ``raw``; ``FormatError`` names what does not read."""

        def fail(message: str, locator: str = "") -> FormatError:
            return FormatError(message, file=file, locator=locator)

        if not isinstance(raw, dict) or not accepts_schema(cast("dict[str, Any]", raw).get("schema"), SCHEMA):
            raise fail(f"an edit plan is an object of schema {SCHEMA}", "/schema")
        data = cast("dict[str, Any]", raw)
        unknown = set(data) - {"schema", "document", "base_sha256", "declared_nets", "operations"}
        if unknown:
            raise fail(f"unknown key(s) {', '.join(sorted(unknown))}")
        if not isinstance(data.get("document"), str) or not isinstance(data.get("base_sha256"), str):
            raise fail("`document` and `base_sha256` are texts")
        nets, rows = data.get("declared_nets", []), data.get("operations")
        if not isinstance(nets, list) or not all(isinstance(n, str) for n in cast("list[object]", nets)):
            raise fail("`declared_nets` is a list of net names", "/declared_nets")
        if not isinstance(rows, list):
            raise fail("`operations` is a list", "/operations")
        out: list[PlannedOperation] = []
        for index, row in enumerate(cast("list[object]", rows)):
            where = f"/operations/{index}"
            if not isinstance(row, dict):
                raise fail("an operation is an object", where)
            held = cast("dict[str, Any]", row)
            value = held.get("entry")
            if not isinstance(value, dict) or cast("dict[str, Any]", value).get("op") not in PLAN_OPS:
                raise fail(f"the entry names no operation of {', '.join(sorted(PLAN_OPS))}", f"{where}/entry")
            if not isinstance(held.get("gate"), str) or not isinstance(held.get("label"), str):
                raise fail("`gate` and `label` are texts", where)
            for key in ("target", "base", "result"):
                if held.get(key) is not None and not isinstance(held.get(key), dict):
                    raise fail(f"`{key}` is an object or null", f"{where}/{key}")
            if _has_float(held):
                raise fail("a plan holds no float: lengths in nanometres, angles as text", where)
            parts = (held.get("target"), held.get("base"), held.get("result"))
            out.append(PlannedOperation(cast("dict[str, Any]", value), held["gate"], held["label"], *parts))
        return EditPlan(data["document"], data["base_sha256"], tuple(cast("list[str]", nets)), tuple(out))


def _has_float(value: object) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_has_float(v) for v in cast("dict[str, object]", value).values())
    if isinstance(value, list):
        return any(_has_float(v) for v in cast("list[object]", value))
    return False


def make_plan(session: Any) -> EditPlan:
    """The plan of ``session``'s queue: each operation run in order on a copy of the base, whatever the
    gates; nothing is written. An operation with no entry, given source bytes, holding a float or refused
    on the base raises ``ValueError`` naming it."""
    for queued in session.queued:
        if queued.entry is None:
            raise ValueError(
                f"{queued.label}: the operation reads source bytes or a file outside the "
                "document's folder, which a plan cannot name"
            )
        if _has_float(queued.entry):
            raise ValueError(f"{queued.label}: a plan holds no float: give lengths in nanometres")
    state = State.of(session.data, file=session.path.name)
    rows: list[PlannedOperation] = []
    for queued in session.queued:
        value = dict(queued.entry)
        op = value["op"]
        found = locate(state, value, None) if op in TARGETED or op in ("set_rule", "clone") else None
        target = base = result = None
        if found is not None:
            storage, position = found
            key = {"rule": value["name"]} if op == "set_rule" else value["item"]
            target = {"unique_id": _unique_id(state, storage, position), "key": key}
            base = fingerprint(state, value, storage, position)
        lengths = _lengths(state)
        try:
            queued.run(state)
        except Refused as refusal:
            raise ValueError(f"{queued.label}: {refusal.message}") from None
        if op in MADE:
            made = _made(state, lengths)
            result = None if made is None else fingerprint(state, value, *made)
        elif found is not None and op != "delete":
            result = fingerprint(state, value, *found)
        rows.append(PlannedOperation(value, queued.gate, queued.label, target, base, result))
    return EditPlan(
        session.path.name,
        hashlib.sha256(session.data).hexdigest(),
        tuple(sorted(session.declared_nets)),
        tuple(rows),
    )


# --- replay and rebase ----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Rebased:
    """The rebase step of one operation: its status and, for a conflict, each field's base and current
    value."""

    label: str
    status: Status
    fields: tuple[tuple[str, object, object], ...] = ()


def shown(name: str, value: object) -> str:
    """A fingerprint value for a message: a length in millimetres."""
    if name in LENGTHS and isinstance(value, int) and not isinstance(value, bool):
        return f"{round(u_to_nm(value) / 1e6, 4):g} mm"  # a unit is 2.54 nm: 0.1 µm shows it
    return json.dumps(value, ensure_ascii=False)


def rebase(state: State, planned: PlannedOperation, value: dict[str, Any]) -> Rebased:
    """The three-way step of design D4 on ``state``: ``base`` → applied, ``result`` → already applied,
    anything else a conflict; no target is missing unless the plan's result is held."""
    op = value["op"]
    label = planned.label
    if op in MADE and planned.result is not None and _held_anywhere(state, value, planned.result):
        return Rebased(label, "already-applied")
    if planned.base is None:
        return Rebased(label, "applied")
    found = locate(state, value, planned.target)
    if found is None:
        if op == "delete" or (planned.result is not None and _held_anywhere(state, value, planned.result)):
            return Rebased(label, "already-applied")
        return Rebased(label, "missing")
    now = fingerprint(state, value, *found)
    if now == planned.base:
        return Rebased(label, "applied")
    if now == planned.result:
        return Rebased(label, "already-applied")
    changed = tuple(
        (name, planned.base.get(name), now.get(name))
        for name in sorted(set(now) | set(planned.base))
        if now.get(name) != planned.base.get(name)
    )
    return Rebased(label, "conflict", changed)


def replay(plan: EditPlan, path: str | Path, *, gates: Mapping[str, bool] | None = None) -> Any:
    """A session on the document at ``path`` holding ``plan``'s operations, each after its rebase step on
    the state the earlier operations left (design D4). Conflicts and missing targets are error issues of
    ``session.rebase``, which refuse the commit; ``session.rebased`` holds each step."""
    from fenolite.backends.altium.edit.session import open_document

    session = open_document(path, gates=gates)
    session.declare_connectivity(*plan.declared_nets)
    state = State.of(session.data, file=session.path.name)
    for index, planned in enumerate(plan.operations):
        value = dict(planned.entry)
        step = rebase(state, planned, value)
        session.rebased.append(step)
        if step.status == "applied":
            try:
                queue(session, value, index, allowed=PLAN_OPS)
            except EntryError as error:
                raise FormatError(str(error), locator=f"/operations/{index}/entry") from None
            try:
                session.queued[-1].run(state)
            except Refused:
                pass  # the commit refuses it with its own assertion
            continue
        session.rebase.append(_rebase_issue(step))
    return session


def _rebase_issue(step: Rebased) -> Issue:
    if step.status == "already-applied":
        return Issue("altium.edit.rebase-applied", "info",
                     f"{step.label}: the document already holds its result; skipped")  # fmt: skip
    if step.status == "missing":
        return Issue("altium.edit.rebase-missing", "error",
                     f"{step.label}: the document no longer holds its target",
                     hint="delete the operation from the plan file, or make a new plan")  # fmt: skip
    changes = "; ".join(f"{name}: {shown(name, base)} in the plan's base, {shown(name, now)} now"
                        for name, base, now in step.fields)  # fmt: skip
    return Issue("altium.edit.rebase-conflict", "error",
                 f"{step.label}: the target changed since the plan was made: {changes}",
                 hint="delete the operation from the plan file, or edit it to the current value")  # fmt: skip


__all__ = [
    "SCHEMA",
    "EditPlan",
    "EntryError",
    "PlannedOperation",
    "Rebased",
    "fingerprint",
    "make_plan",
    "queue",
    "rebase",
    "replay",
]
