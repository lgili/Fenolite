# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Edits made in the CAD tool that survive a rebuild: the three-way merge per property (``docs/lens.md``,
"Three-way merge"; change c0250).

Every merged property is keyed ``<component path>#<property>``. Three sides decide it: the *base* (what the
last build was given, ``code``, and what it wrote, ``out``: ``fenolite-base.json`` in the output folder),
the *code* (the script, with its edit of ``edits.toml``) and the *CAD* file (the board and, for values and
footprints, the schematic). One side changed: it wins. Both changed to one value: fine. Both changed
differently: ``sync.conflict``, which ``fenolite build --take`` resolves.

Every function is pure: the commands read and write the files. Positions are integer nanometres,
rotations integer microdegrees with the side, and other values texts; no float is created.
"""

from __future__ import annotations

import dataclasses
import json
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType
from typing import Literal, Protocol, cast

from fenolite.backends.kicad.embed import PATH_PROPERTY
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.lens.placements import decimal_text, is_component_path, table_name
from fenolite.model.board import FootprintInstance
from fenolite.model.circuit import Component
from fenolite.model.design import Design
from fenolite.model.schematic import SchematicSheet, SymbolInstance

EDITS_SCHEMA = "fenolite.edits.v0"
EDITS_FILE = "edits.toml"
BASE_SCHEMA = "fenolite.base.v0"
BASE_FILE = "fenolite-base.json"
PROPERTIES: tuple[str, ...] = ("position", "rotation", "value", "footprint", "reference")
"""The merged properties, in key order; a user property is named ``property:<name>``."""
TEXTS: tuple[str, ...] = ("value", "footprint", "reference")
"""The merged text properties of every part; the user properties the script names join them."""
USER_PREFIX = "property:"
RESERVED_PREFIXES: tuple[str, ...] = ("fenolite.", "ki_")
"""The prefixes of property names that are no user property (``design-dsl``, "User properties")."""
_RESERVED_NAMES = frozenset({"reference", "value", "footprint", "datasheet", "description"})
CAD_SIDES: tuple[str, ...] = ("board", "schematic")
TAKE_SIDES: tuple[str, ...] = ("code", "cad", "board", "schematic")
REASONS: tuple[str, ...] = ("both-changed", "stale-edit", "cad-locked", "sides-disagree")
HEADER = "# Written by fenolite sync --to-source."
INVALID = "layout.source-invalid"
UNRECORDED_HINT = "run fenolite sync --to-source to record it in edits.toml"
EDIT_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "sync.conflict": "error",
        "edit.take-unused": "warning",
        "edit.legacy-file": "warning",
        "edit.base-invalid": "warning",
        "edit.unrecorded": "info",
        "edit.code-wins": "info",
        "edit.base-missing": "info",
    }
)
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-LENS-KEEP", "H-K-SCH-UPDATE", "H-K-EDIT-SCH-VALUE"))
"""Joins the ``build`` and ``sync`` envelopes when a base record or an edits file was read; stays
``INFERRED``: the merge is Fenolite's own behaviour, proved on token-edited boards and schematics."""

Position = tuple[int, int]
Rotation = tuple[int, str]
Value = Position | Rotation | str
Source = Literal["base", "code", "cad", "board", "schematic", "take"]

_MM = 1_000_000
_DEG = 1_000_000
_FULL_TURN = 360_000_000
_SIDES = ("top", "bottom")


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code, EDIT_ISSUE_CODES[code], message, where=where, hint=hint)


# --- keys -----------------------------------------------------------------------------------------


def check_property(prop: str) -> str:
    """``prop`` when it names a merged property; ``ValueError`` otherwise."""
    if prop in PROPERTIES or (prop.startswith(USER_PREFIX) and len(prop) > len(USER_PREFIX)):
        return prop
    raise ValueError(f"unknown property {prop!r}; use one of: {', '.join(PROPERTIES)}, or property:<name>")


@dataclass(frozen=True, slots=True)
class PropertyKey:
    """``<component path>#<property>``: the key of one merged property of one part."""

    path: str
    prop: str

    def __post_init__(self) -> None:
        check_property(self.prop)

    def __str__(self) -> str:
        return f"{self.path}#{self.prop}"

    def sort_key(self) -> tuple[str, int, str]:
        """Component path, then the order of ``PROPERTIES``, then the user property name."""
        if self.prop.startswith(USER_PREFIX):
            return (self.path, len(PROPERTIES), self.prop[len(USER_PREFIX) :].casefold())
        return (self.path, PROPERTIES.index(self.prop), "")


def describe(value: Value | None) -> str:
    """A value as messages give it: positions in millimetres, rotations in degrees with the side."""
    if value is None:
        return "none"
    if isinstance(value, str):
        return repr(value)
    first, second = value
    if isinstance(second, str):
        return f"({decimal_text(first, _DEG)}°, {second})"
    return f"({decimal_text(first, _MM)} mm, {decimal_text(second, _MM)} mm)"


# --- the base record ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BaseEntry:
    """One property of the base: the code value the last build was given (``None`` without one) and the
    value it wrote."""

    code: Value | None
    out: Value


@dataclass(frozen=True)
class BaseRecord:
    """The base record of an output folder. ``present`` is false when no valid record was read."""

    target: str
    parts: Mapping[str, Mapping[str, BaseEntry]] = field(default_factory=lambda: MappingProxyType({}))
    issues: tuple[Issue, ...] = ()
    present: bool = True

    @classmethod
    def absent(cls, target: str, issues: tuple[Issue, ...] = ()) -> BaseRecord:
        """No record: the output folder holds none, or a foreign or broken one."""
        return cls(target, MappingProxyType({}), issues, present=False)

    def entry(self, path: str, prop: str) -> BaseEntry | None:
        return self.parts.get(path, {}).get(prop)


def _value_of(prop: str, raw: object) -> Value | None:
    """The value of ``prop`` from its JSON form, or ``None`` when the form is wrong."""
    if prop == "position":
        if isinstance(raw, list):
            items = cast(list[object], raw)
            if len(items) == 2 and all(isinstance(i, int) and not isinstance(i, bool) for i in items):
                return (cast(int, items[0]), cast(int, items[1]))
        return None
    if prop == "rotation":
        if isinstance(raw, list):
            items = cast(list[object], raw)
            if (
                len(items) == 2
                and isinstance(items[0], int)
                and not isinstance(items[0], bool)
                and items[1] in _SIDES
            ):
                return (items[0], cast(str, items[1]))
        return None
    return raw if isinstance(raw, str) else None


def read_base(text: str, *, target: str, file: str = "") -> BaseRecord:
    """The record of ``text``; a text that is not JSON, of another ``schema`` or ``target``, or with a
    malformed entry, is no record, with one ``edit.base-invalid`` naming ``file``."""
    name = file or BASE_FILE

    def invalid(why: str) -> BaseRecord:
        return BaseRecord.absent(
            target,
            (
                issue(
                    "edit.base-invalid",
                    f"{name}: {why}; it is read as no base record, so the merge falls back to the rule of "
                    "before for every part",
                    name,
                    "rebuild to write it again",
                ),
            ),
        )

    try:
        data = json.loads(text)
    except ValueError as error:
        return invalid(f"not JSON: {error}")
    if not isinstance(data, dict):
        return invalid("not a JSON object")
    record = cast(dict[str, object], data)
    if record.get("schema") != BASE_SCHEMA:
        return invalid(f"schema is {record.get('schema')!r}, not {BASE_SCHEMA!r}")
    if record.get("target") != target:
        return invalid(f"target is {record.get('target')!r}, not {target!r}")
    if set(record) != {"schema", "target", "parts"} or not isinstance(record["parts"], dict):
        return invalid("it holds other keys than schema, target and parts")
    parts: dict[str, Mapping[str, BaseEntry]] = {}
    for path, props in cast(dict[str, object], record["parts"]).items():
        if not is_component_path(path) or not isinstance(props, dict):
            return invalid(f"part {path!r} is not a component path with a table of properties")
        entries: dict[str, BaseEntry] = {}
        for prop, raw in cast(dict[str, object], props).items():
            try:
                check_property(prop)
            except ValueError:
                return invalid(f"{path}#{prop}: unknown property")
            if not isinstance(raw, dict) or set(cast(dict[str, object], raw)) != {"code", "out"}:
                return invalid(f"{path}#{prop}: an entry holds code and out")
            pair = cast(dict[str, object], raw)
            out = _value_of(prop, pair["out"])
            code = None if pair["code"] is None else _value_of(prop, pair["code"])
            if out is None or (pair["code"] is not None and code is None):
                return invalid(f"{path}#{prop}: a value has the wrong form")
            entries[prop] = BaseEntry(code, out)
        parts[path] = MappingProxyType(entries)
    return BaseRecord(target, MappingProxyType(dict(sorted(parts.items()))))


def write_base(record: BaseRecord) -> str:
    """The canonical JSON text of ``record``: sorted keys, two-space indent, no date, one final newline."""
    parts = {
        path: {
            prop: {"code": None if entry.code is None else _json(entry.code), "out": _json(entry.out)}
            for prop, entry in props.items()
        }
        for path, props in record.parts.items()
    }
    data = {"parts": parts, "schema": BASE_SCHEMA, "target": record.target}
    return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def _json(value: Value) -> object:
    return value if isinstance(value, str) else list(value)


def base_record(
    codes: Mapping[str, Mapping[str, Value | None]],
    written: Mapping[str, Mapping[str, Value]],
    *,
    target: str,
) -> BaseRecord:
    """The record a build writes: for each written part and property, its code value and the value
    written. A property without a written value is left out, and so is a user property the code side does
    not name (one added in the CAD tool stays opaque)."""
    parts: dict[str, Mapping[str, BaseEntry]] = {}
    for path in sorted(written):
        held = codes.get(path, {})
        entries = {
            prop: BaseEntry(held.get(prop), out)
            for prop, out in written[path].items()
            if not prop.startswith(USER_PREFIX) or prop in held
        }
        if entries:
            parts[path] = MappingProxyType(dict(sorted(entries.items())))
    return BaseRecord(target, MappingProxyType(parts))


# --- the edits file -------------------------------------------------------------------------------


@dataclass(frozen=True)
class PartEdits:
    """The edits of one part. ``values`` maps each edited property to its value; ``over`` maps it to the
    script's value when the edit was recorded (``None`` for a position or rotation the script did not
    give). ``over`` is ``None`` for a legacy ``placements.toml`` entry, which never goes stale. ``locked``
    is the footprint's lock in KiCad, written with an edited position; it gives the edit no precedence."""

    values: Mapping[str, Value] = field(default_factory=lambda: MappingProxyType({}))
    over: Mapping[str, Value | None] | None = field(default_factory=lambda: MappingProxyType({}))
    locked: bool = False

    def edit(self, prop: str) -> Edit | None:
        if prop not in self.values:
            return None
        if self.over is None:
            return Edit(self.values[prop], None, legacy=True)
        return Edit(self.values[prop], self.over.get(prop))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PartEdits):
            return NotImplemented
        over = None if self.over is None else dict(self.over)
        theirs = None if other.over is None else dict(other.over)
        return (dict(self.values), over, self.locked) == (dict(other.values), theirs, other.locked)

    def __hash__(self) -> int:
        return hash((tuple(sorted(self.values)), self.locked))


@dataclass(frozen=True, slots=True)
class Edit:
    """One edited property: its value, the script's value it was made over, and whether it is legacy."""

    value: Value
    over: Value | None
    legacy: bool = False


@dataclass(frozen=True)
class EditsFile:
    """The valid tables of an edits file, in component-path order, and what was wrong with the rest.

    A capture (``capture_edits``) also gives the keys it ``captured``, the code changes that the next
    build writes over an unchanged CAD value (``pending``), the ``conflicts`` that stop it, and the matched
    parts without a base entry (``no_base``), whose values it leaves to the script."""

    parts: Mapping[str, PartEdits]
    issues: tuple[Issue, ...] = ()
    captured: tuple[str, ...] = ()
    pending: tuple[str, ...] = ()
    conflicts: tuple[Conflict, ...] = ()
    no_base: tuple[str, ...] = ()


_TABLE_KEYS = (
    "x",
    "y",
    "rotation",
    "side",
    "locked",
    "value",
    "footprint",
    "reference",
    "properties",
    "over",
)
_OVER_KEYS = ("unplaced", "x", "y", "rotation", "side", "value", "footprint", "reference", "properties")
_TEXTS = ("value", "footprint", "reference")


def _scaled(value: object, unit: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | Decimal):
        return None
    scaled = Decimal(value) * unit
    if not scaled.is_finite() or scaled != scaled.to_integral_value():
        return None
    return int(scaled)


def _values(
    table: Mapping[str, object],
    origin: Point,
    keys: Sequence[str],
    faults: list[tuple[str, str]],
    prefix: str,
) -> dict[str, Value]:
    """The property values of a table or an ``over`` table; each fault is added as (key, what)."""
    found: dict[str, Value] = {}
    for key in table:
        if key not in keys:
            faults.append((f"{prefix}{key}", f"unknown key; a table holds {', '.join(keys)}"))
    if ("x" in table) != ("y" in table):
        faults.append((f"{prefix}{'y' if 'x' in table else 'x'}", "x and y are given together"))
    elif "x" in table:
        lengths: list[int] = []
        for key in ("x", "y"):
            nm = _scaled(table[key], _MM)
            if nm is None:
                faults.append((f"{prefix}{key}", f"{table[key]!r} is not a whole number of nanometres"))
            else:
                lengths.append(nm)
        if len(lengths) == 2:
            found["position"] = (origin.x + lengths[0], origin.y + lengths[1])
    if ("rotation" in table) != ("side" in table):
        faults.append(
            (f"{prefix}{'side' if 'rotation' in table else 'rotation'}", "rotation and side together")
        )
    elif "rotation" in table:
        rotation = _scaled(table["rotation"], _DEG)
        side = table["side"]
        if rotation is None or not 0 <= rotation < _FULL_TURN:
            faults.append(
                (f"{prefix}rotation", f"{table['rotation']!r} is not whole microdegrees in [0, 360)")
            )
        elif side not in _SIDES:
            faults.append((f"{prefix}side", f"{side!r} is not 'top' or 'bottom'"))
        else:
            found["rotation"] = (rotation, cast(str, side))
    for key in _TEXTS:
        if key in table:
            if isinstance(table[key], str):
                found[key] = cast(str, table[key])
            else:
                faults.append((f"{prefix}{key}", f"{table[key]!r} is not a string"))
    if "properties" in table:
        props = table["properties"]
        if not isinstance(props, dict) or not all(
            isinstance(v, str) for v in cast(dict[str, object], props).values()
        ):
            faults.append((f"{prefix}properties", "is not an inline table of strings"))
        else:
            for name, text in sorted(cast(dict[str, str], props).items()):
                found[USER_PREFIX + name] = text
    return found


def _part_edits(table: Mapping[str, object], origin: Point) -> tuple[PartEdits | None, list[tuple[str, str]]]:
    faults: list[tuple[str, str]] = []
    values = _values(table, origin, _TABLE_KEYS, faults, "")
    locked = table.get("locked", False)
    if not isinstance(locked, bool):
        faults.append(("locked", f"{locked!r} is not true or false"))
        locked = False
    elif "locked" in table and "x" not in table:
        faults.append(("locked", "locked is given with x and y"))
    raw_over = table.get("over", {})
    over: dict[str, Value | None] = {}
    if not isinstance(raw_over, dict):
        faults.append(("over", "is not a table"))
    else:
        held = cast(dict[str, object], raw_over)
        over.update(_values(held, origin, _OVER_KEYS, faults, "over."))
        unplaced = held.get("unplaced")
        if unplaced is not None:
            if unplaced is not True:
                faults.append(("over.unplaced", "unplaced is true or left out"))
            elif any(key in held for key in ("x", "y", "rotation", "side")):
                faults.append(("over.unplaced", "unplaced is given instead of x, y, rotation and side"))
            elif not any(key in table for key in ("x", "y", "rotation", "side")):
                faults.append(("over.unplaced", "the table edits no position or rotation"))
            else:
                for prop in ("position", "rotation"):
                    if prop in values:
                        over[prop] = None
    over_keys = {"position": "x", "rotation": "rotation"}
    for prop in values:
        if prop not in over:
            key = over_keys.get(prop, prop)
            if prop.startswith(USER_PREFIX):
                key = f'properties."{prop[len(USER_PREFIX) :]}"'
            faults.append((f"over.{key}", "the edit has no script value in its over table"))
    for prop in over:
        if prop not in values:
            key = over_keys.get(prop, prop)
            if prop.startswith(USER_PREFIX):
                key = f'properties."{prop[len(USER_PREFIX) :]}"'
            faults.append((f"over.{key}", "a script value without its edit"))
    if faults:
        return None, faults
    return PartEdits(MappingProxyType(values), MappingProxyType(over), locked), []


def read_edits(text: str, *, origin: Point, file: str = "") -> EditsFile:
    """The tables of an edits file. ``origin`` is the written position of ``place(0, 0)``.

    A text that is not TOML, or whose ``schema`` is not ``EDITS_SCHEMA``, raises ``FormatError`` naming
    ``file``. A wrong table or key gives ``layout.source-invalid`` and leaves its table out.
    """
    try:
        data = tomllib.loads(text, parse_float=Decimal)
    except tomllib.TOMLDecodeError as error:
        raise FormatError(f"not TOML: {error}", file=file) from error
    if data.get("schema") != EDITS_SCHEMA:
        raise FormatError(
            f"schema is {data.get('schema')!r}, not {EDITS_SCHEMA!r}; fenolite sync --to-source writes the "
            "file",
            file=file,
        )
    issues: list[Issue] = []

    def invalid(where: str, message: str) -> None:
        issues.append(Issue(INVALID, "error", f"{file or EDITS_FILE}: {message}", where=where))

    for key in data:
        if key not in ("schema", "part"):
            invalid(key, f"unknown key {key!r}; the file holds schema and the part tables")
    parts = data.get("part", {})
    found: dict[str, PartEdits] = {}
    if not isinstance(parts, dict):
        invalid("part", "part is not a table of component paths")
        parts = {}
    for path, table in cast(dict[str, object], parts).items():
        name = table_name(path)
        if not is_component_path(path):
            invalid(name, f"[{name}]: {path!r} is not a component path")
            continue
        if not isinstance(table, dict):
            invalid(name, f"[{name}] is not a table")
            continue
        edits, faults = _part_edits(cast(dict[str, object], table), origin)
        for key, what in faults:
            invalid(f"{name}.{key}", f"[{name}] {key}: {what}")
        if edits is not None:
            found[path] = edits
    return EditsFile(MappingProxyType(dict(sorted(found.items()))), tuple(issues))


def _quote(text: str) -> str:
    """``text`` as a TOML basic string."""
    out: list[str] = []
    for char in text:
        if char == "\\":
            out.append("\\\\")
        elif char == '"':
            out.append('\\"')
        elif char in "\b\t\n\f\r":
            out.append({"\b": "\\b", "\t": "\\t", "\n": "\\n", "\f": "\\f", "\r": "\\r"}[char])
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\u{ord(char):04X}")
        else:
            out.append(char)
    return '"' + "".join(out) + '"'


def _lines(values: Mapping[str, Value | None], origin: Point, *, locked: bool = False) -> list[str]:
    lines: list[str] = []
    position = values.get("position")
    if position is not None:
        assert isinstance(position, tuple) and isinstance(position[1], int)
        lines.append(f"x = {decimal_text(position[0] - origin.x, _MM)}")
        lines.append(f"y = {decimal_text(position[1] - origin.y, _MM)}")
    rotation = values.get("rotation")
    if rotation is not None:
        assert isinstance(rotation, tuple) and isinstance(rotation[1], str)
        lines.append(f"rotation = {decimal_text(rotation[0], _DEG)}")
        lines.append(f"side = {_quote(rotation[1])}")
    if locked:
        lines.append("locked = true")
    for key in _TEXTS:
        text = values.get(key)
        if text is not None:
            assert isinstance(text, str)
            lines.append(f"{key} = {_quote(text)}")
    props = sorted(
        (prop[len(USER_PREFIX) :], text)
        for prop, text in values.items()
        if prop.startswith(USER_PREFIX) and isinstance(text, str)
    )
    if props:
        inner = ", ".join(f"{_quote(name)} = {_quote(text)}" for name, text in props)
        lines.append(f"properties = {{ {inner} }}")
    return lines


def write_edits(parts: Mapping[str, PartEdits], *, origin: Point) -> str:
    """The text of an edits file: the comment, the schema, then per part in component-path order its
    table and its ``over`` table. ``read_edits`` gives the edits back; nothing depends on the clock."""
    tables: list[str] = []
    for path, edits in sorted(parts.items()):
        if not is_component_path(path):
            raise ValueError(f"{path!r} is not a component path")
        if edits.over is None or set(edits.over) != set(edits.values):
            raise ValueError(f"{path}: every edit needs its script value in over")
        if edits.locked and "position" not in edits.values:
            raise ValueError(f"{path}: locked is written with a position")
        name = table_name(path)
        body = _lines(edits.values, origin, locked=edits.locked)
        tables.append("\n".join([f"[{name}]", *body]) + "\n")
        unplaced = [p for p in ("position", "rotation") if p in edits.over and edits.over[p] is None]
        if unplaced and len(unplaced) != sum(1 for p in ("position", "rotation") if p in edits.over):
            raise ValueError(f"{path}: unplaced covers both the position and the rotation edit")
        over_lines = (["unplaced = true"] if unplaced else []) + _lines(edits.over, origin)
        tables.append("\n".join([f"[{name}.over]", *over_lines]) + "\n")
    return "\n".join([f'{HEADER}\nschema = "{EDITS_SCHEMA}"\n', *tables])


# --- takes ----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, order=True)
class Take:
    """A ``--take SIDE[:TARGET]``: ``target`` is empty (every conflict), a component path (every conflict
    of that part) or a key text (that property)."""

    target: str
    side: str

    def __str__(self) -> str:
        return f"{self.side}:{self.target}" if self.target else self.side

    def rank(self, key: PropertyKey) -> int:
        """How specifically this take names ``key``: 3 its key, 2 its path, 1 every conflict, 0 not."""
        if not self.target:
            return 1
        if self.target == key.path:
            return 2
        return 3 if self.target == str(key) else 0


def parse_takes(values: Sequence[str]) -> tuple[Take, ...]:
    """The takes of ``--take`` values, sorted; a malformed value or two sides of one target raise
    ``ValueError`` naming them (a usage error of the command)."""
    found: dict[str, Take] = {}
    for value in values:
        side, _, target = value.partition(":")
        if side not in TAKE_SIDES or (":" in value and not target):
            raise ValueError(f"--take {value!r}: give SIDE[:TARGET] with SIDE one of {', '.join(TAKE_SIDES)}")
        if target:
            path, hash_mark, prop = target.partition("#")
            valid = is_component_path(path)
            if valid and hash_mark:
                try:
                    check_property(prop)
                except ValueError:
                    valid = False
            if not valid:
                raise ValueError(
                    f"--take {value!r}: {target!r} is not a component path or a key PATH#PROPERTY"
                )
        take = Take(target, side)
        held = found.get(target)
        if held is not None and held.side != side:
            raise ValueError(f"--take {held} and --take {take} contradict each other")
        found[target] = take
    return tuple(sorted(found.values()))


def _take(takes: Sequence[Take], key: PropertyKey) -> Take | None:
    ranked = sorted(((take.rank(key), take) for take in takes if take.rank(key)), reverse=True)
    return ranked[0][1] if ranked else None


# --- the rule -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Conflict:
    """A property both sides changed differently since the base. ``cad`` holds the value of each side
    involved (``board``, ``schematic``, or ``edits`` for a stale edit), ``sides`` their names."""

    key: PropertyKey
    base: Value | None
    code: Value | None
    cad: Mapping[str, Value]
    sides: tuple[str, ...]
    reason: str

    def record(self) -> dict[str, object]:
        """The conflict as the replies of ``build`` and ``sync`` give it."""
        return {
            "key": str(self.key),
            "reason": self.reason,
            "base": None if self.base is None else _json(self.base),
            "code": None if self.code is None else _json(self.code),
            "cad": {side: _json(value) for side, value in sorted(self.cad.items())},
        }

    def finding(self, *, cad_file: str = "the CAD file") -> Issue:
        """The ``sync.conflict`` of this conflict, its hint naming the takes that resolve it."""
        held = ", ".join(
            f"{_side_name(side, cad_file)} {describe(value)}" for side, value in sorted(self.cad.items())
        )
        key = str(self.key)
        sides = ("board", "schematic") if self.reason == "sides-disagree" else ("code", "cad")
        return issue(
            "sync.conflict",
            f"{key}: base {describe(self.base)}, script {describe(self.code)}, {held} ({self.reason})",
            key,
            "   or   ".join(f"fenolite build ... --take {side}:{key}" for side in sides),
        )


def _side_name(side: str, cad_file: str) -> str:
    if side == "edits":
        return EDITS_FILE
    if side == "board" and cad_file != "the CAD file":
        return f"board {cad_file}"
    return side


@dataclass(frozen=True)
class Decision:
    """How one property was decided: its ``value``, where it came from (``source``), the conflict when the
    sides disagree and no take resolved it, the take that did, the code value (``code``, the script's
    with its edit) and whether that code value is an edit of the edits file (``edited``)."""

    key: PropertyKey
    value: Value | None
    source: Source
    conflict: Conflict | None = None
    take: Take | None = None
    code: Value | None = None
    edited: bool = False
    wins: bool = False
    """The code changed and was written over an unchanged CAD value (``edit.code-wins``)."""
    was: Value | None = None
    """The CAD value a winning code value replaced."""

    @property
    def unrecorded(self) -> bool:
        """A CAD value kept that the code side (the edits file included) does not hold."""
        return (
            self.conflict is None
            and self.source != "code"
            and self.code is not None
            and self.value is not None
            and self.value != self.code
        )


def _kind_of(prop: str) -> Literal["layout", "text"]:
    return "layout" if prop in ("position", "rotation") else "text"


def merge_property(
    key: PropertyKey,
    *,
    base: BaseEntry | None,
    code: Value | None,
    cad: Mapping[str, Value],
    takes: Sequence[Take] = (),
    edit: Edit | None = None,
    locked: bool = False,
    cad_locked: bool = False,
) -> Decision:
    """Decide one property (``docs/lens.md``, "Three-way merge").

    ``code`` is the script's value (``None``: the script gives none), ``edit`` its edit of the edits file,
    ``cad`` the value of each CAD side present (``board``, ``schematic``) and ``base`` the part's base entry
    (``None``: no base, the rule of before). ``locked`` is a locked script request, which always wins;
    ``cad_locked`` a footprint locked in KiCad, which a code change over an unchanged CAD value may not
    move silently. A take applies to a conflict only."""
    take = _take(takes, key)
    script = code
    edited = False
    effective = script
    if edit is not None:
        if edit.legacy or edit.over == script or edit.value == script:
            effective, edited = edit.value, True
        else:
            stale = Conflict(key, edit.over, script, {"edits": edit.value}, ("edits",), "stale-edit")
            if take is None:
                held = cad.get("board", next(iter(cad.values()), script))
                return Decision(key, held, "cad" if cad else "code", stale, None, script)
            if take.side == "code":
                effective = script
            else:
                effective, edited = edit.value, True
    if locked and effective is not None:
        return Decision(key, effective, "code", None, None, effective, edited)
    if not cad:
        return Decision(key, effective, "code", None, None, effective, edited)
    board = cad.get("board")
    if base is None:
        if _kind_of(key.prop) == "layout" or effective is None:
            value = board if board is not None else next(iter(cad.values()))
            return Decision(key, value, "cad", None, None, effective, edited)
        return Decision(key, effective, "code", None, None, effective, edited)
    code_changed = effective is not None and effective != base.code
    changed = {side: value for side, value in cad.items() if value != base.out}

    def resolve(conflict: Conflict, options: Mapping[str, Value | None]) -> Decision:
        if take is not None and options.get(take.side) is not None:
            return Decision(key, options[take.side], "take", None, take, effective, edited)
        held = board if board is not None else next(iter(cad.values()))
        return Decision(key, held, "cad", conflict, None, effective, edited)

    if len(set(changed.values())) > 1:
        conflict = Conflict(key, base.out, effective, dict(changed), tuple(sorted(changed)), "sides-disagree")
        return resolve(conflict, {"code": effective if code_changed else None, **changed})
    if changed:
        cad_value = next(iter(changed.values()))
        source: Source = "schematic" if set(changed) == {"schematic"} else "cad"
    else:
        cad_value = board if board is not None else next(iter(cad.values()))
        source = "base"
    if not code_changed:
        return Decision(key, cad_value, source, None, None, effective, edited)
    if not changed:
        if effective == cad_value:
            # the code now holds what the CAD file holds (an edit recorded by sync): nothing is written over
            return Decision(key, effective, "code", None, None, effective, edited)
        if cad_locked:
            conflict = Conflict(key, base.out, effective, {"board": cad_value}, ("board",), "cad-locked")
            return resolve(conflict, {"code": effective, "cad": cad_value, "board": cad_value})
        return Decision(key, effective, "code", None, None, effective, edited, wins=True, was=cad_value)
    if cad_value == effective:
        return Decision(key, effective, "code", None, None, effective, edited)
    conflict = Conflict(key, base.out, effective, dict(changed), tuple(sorted(changed)), "both-changed")
    return resolve(conflict, {"code": effective, "cad": cad_value, **changed})


# --- the merge of values and footprints -----------------------------------------------------------


@dataclass(frozen=True)
class PropertyMerge:
    """The design with the decided values and footprints, every decision, the base record this build
    writes (its ``out`` values as decided; the build writes the values it wrote) and the issues."""

    design: Design
    decisions: tuple[Decision, ...]
    base: BaseRecord
    issues: tuple[Issue, ...] = ()
    missing: tuple[str, ...] = ()
    used_takes: frozenset[Take] = frozenset()


def _symbols(sheets: Sequence[SchematicSheet] | None) -> dict[str, list[tuple[int, SymbolInstance]]]:
    """Component path → ``(unit, symbol)`` of each of its symbols, by unit."""
    found: dict[str, list[tuple[int, SymbolInstance]]] = {}
    for sheet in sheets or ():
        for symbol in sheet.symbols:
            path = symbol.properties.get(PATH_PROPERTY)
            if path:
                found.setdefault(path, []).append((symbol.unit, symbol))
    return {path: sorted(units, key=lambda unit: unit[0]) for path, units in found.items()}


def user_names(component: Component) -> tuple[str, ...]:
    """The user properties ``component`` names (the script's ``properties=``, and a device's), in
    code-point order: its properties without ``fenolite.`` and ``ki_`` names and the fields of KiCad."""
    return tuple(
        sorted(
            name
            for name in component.properties
            if not name.startswith(RESERVED_PREFIXES) and name.casefold() not in _RESERVED_NAMES
        )
    )


def _symbol_text(symbol: SymbolInstance, prop: str) -> str:
    """The text of ``prop`` in a symbol; a user property the symbol lacks is the empty text."""
    if prop == "value":
        return symbol.properties.get("Value", symbol.value)
    if prop == "footprint":
        return symbol.footprint
    if prop == "reference":
        return symbol.properties.get("Reference", symbol.ref)
    return symbol.properties.get(prop[len(USER_PREFIX) :], "")


def _board_text(read: Component | None, fp: FootprintInstance | None, prop: str) -> str | None:
    """The text of ``prop`` on the board: ``None`` without a footprint, or for a value or reference of a
    footprint without its Value or Reference field (a board of an older Fenolite); a user property the
    footprint lacks is the empty text."""
    if prop == "footprint":
        return fp.lib_ref if fp is not None else None
    if read is None:
        return None
    if prop == "value":
        return read.properties.get("Value")
    if prop == "reference":
        return read.properties.get("Reference")
    return read.properties.get(prop[len(USER_PREFIX) :], "")


def code_texts(component: Component) -> dict[str, Value | None]:
    """The code side of the text properties of ``component``: value, footprint (``None`` when the part
    names none and takes its symbol's), reference and each user property it names."""
    texts: dict[str, Value | None] = {
        "value": component.value,
        "footprint": component.lib_footprint_ref or None,
        "reference": component.ref,
    }
    for name in user_names(component):
        texts[USER_PREFIX + name] = component.properties[name]
    return texts


def _with_texts(component: Component, changes: Mapping[str, str]) -> Component:
    """``component`` with the decided texts of ``changes``."""
    properties = dict(component.properties)
    for prop, text in changes.items():
        if prop.startswith(USER_PREFIX):
            properties[prop[len(USER_PREFIX) :]] = text
    return dataclasses.replace(
        component,
        value=changes.get("value", component.value),
        lib_footprint_ref=changes.get("footprint", component.lib_footprint_ref),
        ref=changes.get("reference", component.ref),
        properties=properties,
    )


def merge_properties(
    design: Design,
    *,
    board: Design | None,
    sheets: Sequence[SchematicSheet] | None,
    match: Mapping[str, FootprintInstance],
    base: BaseRecord | None,
    edits: Mapping[str, PartEdits],
    takes: Sequence[Take] = (),
    aliases: Mapping[str, str] | None = None,
    target: str = "kicad",
) -> PropertyMerge:
    """Decide ``value``, ``footprint``, ``reference`` and the user properties the script names of every
    part before the build (change c0250).

    ``match`` maps component paths to their matched footprints of ``board``; ``sheets`` are the sheets of
    the existing schematic. ``aliases`` (new path → old) let a part matched through ``moved()`` take the
    base entry of its old path. The code side of ``reference`` is the ref the part is lowered with (its
    explicit ref, or the one of the design lock); a user property a CAD side lacks counts as ``""``."""
    on_board = {c.id: c for c in board.circuit.components} if board is not None else {}
    symbols = _symbols(sheets)
    decisions: list[Decision] = []
    issues: list[Issue] = []
    missing: list[str] = []
    used: set[Take] = set()
    codes: dict[str, dict[str, Value | None]] = {}
    outs: dict[str, dict[str, Value]] = {}
    replaced: dict[str, Component] = {}
    for component in design.circuit.components:
        path = component.properties.get(PATH_PROPERTY)
        if path is None:
            continue
        part_edits = edits.get(path)
        fp = match.get(path)
        read = on_board.get(fp.component_id) if fp is not None else None
        units = symbols.get(path, [])
        old = (aliases or {}).get(path)
        held_base = None
        if base is not None and base.present:
            held_base = base.parts.get(path) or (base.parts.get(old) if old else None)
        has_cad = fp is not None or bool(units)
        if base is not None and has_cad and held_base is None:
            missing.append(path)
        changes: dict[str, str] = {}
        # a part without its own footprint takes its symbol's: the script gives no value, as an unplaced
        # part gives no position
        for prop, script in code_texts(component).items():
            board_value = _board_text(read, fp, prop)
            unit_texts = [(unit, _symbol_text(symbol, prop)) for unit, symbol in units]
            key = PropertyKey(path, prop)
            cad: dict[str, Value] = {}
            if board_value is not None:
                cad["board"] = board_value
            if unit_texts:
                if len({text for _, text in unit_texts}) > 1:
                    conflict = Conflict(
                        key,
                        None,
                        script,
                        {f"schematic unit {unit}": text for unit, text in unit_texts},
                        tuple(f"schematic unit {unit}" for unit, _ in unit_texts),
                        "sides-disagree",
                    )
                    decisions.append(Decision(key, script, "code", conflict, None, script))
                    issues.append(conflict.finding())
                    continue
                cad["schematic"] = unit_texts[0][1]
            entry = held_base.get(prop) if held_base is not None else None
            decision = merge_property(
                key,
                base=entry,
                code=script,
                cad=cad,
                takes=takes,
                edit=_text_edit(part_edits, prop),
            )
            if entry is not None or decision.conflict is not None or decision.take is not None:
                decisions.append(decision)
            if decision.take is not None:
                used.add(decision.take)
            if decision.conflict is not None:
                issues.append(decision.conflict.finding())
                continue
            codes.setdefault(path, {})[prop] = decision.code
            if decision.value is not None:
                outs.setdefault(path, {})[prop] = decision.value
            unchanged = decision.code is None and (decision.source == "base" or entry is None)
            if isinstance(decision.value, str) and decision.value != (script or "") and not unchanged:
                changes[prop] = decision.value
        if changes:
            replaced[component.id] = _with_texts(component, changes)
    merged = design
    if replaced:
        circuit = dataclasses.replace(
            design.circuit, components=tuple(replaced.get(c.id, c) for c in design.circuit.components)
        )
        merged = dataclasses.replace(design, circuit=circuit)
    record = base_record(codes, outs, target=target)
    return PropertyMerge(merged, tuple(decisions), record, tuple(issues), tuple(missing), frozenset(used))


def missing_issue(paths: Sequence[str]) -> Issue:
    """The one ``edit.base-missing`` of a build: parts merged by the rule of before."""
    shown = ", ".join(sorted(paths)[:5]) + (", ..." if len(paths) > 5 else "")
    return issue(
        "edit.base-missing",
        f"{len(paths)} part(s) have no entry in {BASE_FILE} ({shown}): the board wins for their positions "
        "and the script for their values, as before; this build writes the record",
        BASE_FILE,
    )


def decision_issues(decisions: Sequence[Decision], *, cad_file: str = "the CAD file") -> list[Issue]:
    """The info issues of decided properties: ``edit.unrecorded`` for each CAD value kept that the edits
    file does not hold, and ``edit.code-wins`` for each script change written over an unchanged CAD
    value. Conflicts are reported where they are found."""
    found: list[Issue] = []
    for decision in sorted(decisions, key=lambda d: d.key.sort_key()):
        key = str(decision.key)
        if decision.unrecorded:
            found.append(
                issue(
                    "edit.unrecorded",
                    f"{key}: {describe(decision.value)} of {cad_file} is kept over the script's "
                    f"{describe(decision.code)}",
                    key,
                    UNRECORDED_HINT,
                )
            )
        elif decision.wins:
            found.append(
                issue(
                    "edit.code-wins",
                    f"{key}: the script's {describe(decision.value)} is written over the unchanged "
                    f"{describe(decision.was)} of {cad_file}",
                    key,
                )
            )
    return found


def edits_summary(decisions: Sequence[Decision]) -> dict[str, object]:
    """``result.preserved.edits``: sorted key texts of the kept CAD values, the code values written over
    an unchanged CAD value, the taken conflicts and the unrecorded CAD values, and the conflicts."""
    ordered = sorted(decisions, key=lambda d: d.key.sort_key())
    return {
        "kept": [
            str(d.key) for d in ordered if d.conflict is None and d.source in ("cad", "schematic", "board")
        ],
        "code": [str(d.key) for d in ordered if d.wins],
        "taken": [str(d.key) for d in ordered if d.take is not None],
        "unrecorded": [str(d.key) for d in ordered if d.unrecorded],
        "conflicts": [d.conflict.record() for d in ordered if d.conflict is not None],
    }


def _text_edit(edits: PartEdits | None, prop: str) -> Edit | None:
    """The edit of a text property; an empty ``over`` footprint is "the script names none"."""
    edit = edits.edit(prop) if edits is not None else None
    if edit is not None and prop == "footprint" and edit.over == "":
        return Edit(edit.value, None, edit.legacy)
    return edit


class RequestLike(Protocol):
    """A requested placement, read by attribute (the twin of ``lens.preserve.PlacementLike``)."""

    @property
    def at(self) -> Point: ...

    @property
    def rotation(self) -> int: ...

    @property
    def side(self) -> str: ...

    @property
    def locked(self) -> bool: ...


def capture_edits(
    design: Design,
    *,
    board: Design,
    sheets: Sequence[SchematicSheet] | None,
    match: Mapping[str, FootprintInstance],
    base: BaseRecord | None,
    edits: Mapping[str, PartEdits],
    origin: Point,
    requests: Mapping[str, RequestLike] | None = None,
    off_board: frozenset[str] = frozenset(),
    aliases: Mapping[str, str] | None = None,
) -> EditsFile:
    """The edits that ``fenolite sync --to-source`` writes (``docs/lens.md``, "edits.toml").

    For each matched part and merged property: the value the next build without ``--take`` writes,
    recorded over the script's value when the two differ, and nothing otherwise. ``requests`` are the
    script's ``place()`` requests, ``off_board`` the matched parts whose footprint lies off the board (they
    are staged again and get no position). A part without a base entry has its position and rotation
    captured from the board, never its value or footprint (``no_base``). The tables of ``edits`` for parts
    the board does not hold are kept unchanged. A conflict gives ``sync.conflict`` and no edit at all.
    ``origin`` is the frame of the file, for the messages."""
    del origin
    on_board = {c.id: c for c in board.circuit.components}
    symbols = _symbols(sheets)
    parts: dict[str, PartEdits] = {}
    conflicts: list[Conflict] = []
    pending: list[str] = []
    captured: list[str] = []
    no_base: list[str] = []
    for component in design.circuit.components:
        path = component.properties.get(PATH_PROPERTY)
        if path is None:
            continue
        held = edits.get(path)
        fp = match.get(path)
        units = symbols.get(path, [])
        if fp is None and not units:
            if held is not None:
                parts[path] = held
            continue
        old = (aliases or {}).get(path)
        entry = None
        if base is not None and base.present:
            entry = base.parts.get(path) or (base.parts.get(old) if old else None)
        if entry is None:
            no_base.append(path)
        request = (requests or {}).get(path)
        values: dict[str, Value] = {}
        over: dict[str, Value | None] = {}
        decided: list[tuple[str, Decision, Value | None]] = []
        if fp is not None and path not in off_board:
            script_pos: Value | None = (request.at.x, request.at.y) if request is not None else None
            script_rot: Value | None = (request.rotation, request.side) if request is not None else None
            layout: tuple[tuple[str, Value | None, Value], ...] = (
                ("position", script_pos, (fp.position.x, fp.position.y)),
                ("rotation", script_rot, (fp.rotation, fp.side)),
            )
            for prop, script, held_value in layout:
                decision = merge_property(
                    PropertyKey(path, prop),
                    base=entry.get(prop) if entry is not None else None,
                    code=script,
                    cad={"board": held_value},
                    edit=held.edit(prop) if held is not None else None,
                    locked=request is not None and request.locked,
                    cad_locked=fp.locked,
                )
                decided.append((prop, decision, script))
        if entry is not None:
            read = on_board.get(fp.component_id) if fp is not None else None
            for prop, script in code_texts(component).items():
                board_value = _board_text(read, fp, prop)
                cad: dict[str, Value] = {}
                if board_value is not None:
                    cad["board"] = board_value
                texts = [_symbol_text(symbol, prop) for _, symbol in units]
                if len(set(texts)) > 1:
                    key = PropertyKey(path, prop)
                    conflicts.append(
                        Conflict(
                            key,
                            None,
                            script,
                            {
                                f"schematic unit {unit[0]}": text
                                for unit, text in zip(units, texts, strict=True)
                            },
                            tuple(f"schematic unit {unit[0]}" for unit in units),
                            "sides-disagree",
                        )
                    )
                    continue
                if texts:
                    cad["schematic"] = texts[0]
                decision = merge_property(
                    PropertyKey(path, prop),
                    base=entry.get(prop),
                    code=script,
                    cad=cad,
                    edit=_text_edit(held, prop),
                )
                decided.append((prop, decision, script))
        for prop, decision, script in decided:
            if decision.conflict is not None:
                conflicts.append(decision.conflict)
                continue
            if decision.wins:
                pending.append(str(decision.key))
            value = decision.value
            if value is None or value == script:
                continue
            if prop == "footprint" and script is None and decision.source == "base":
                continue  # the symbol's footprint, unchanged
            values[prop] = value
            over[prop] = "" if prop == "footprint" and script is None else script
            captured.append(str(decision.key))
        if values:
            locked = fp is not None and "position" in values and fp.locked
            parts[path] = PartEdits(
                MappingProxyType(dict(sorted(values.items()))),
                MappingProxyType(dict(sorted(over.items()))),
                locked,
            )
    if conflicts:
        ordered = sorted(conflicts, key=lambda c: c.key.sort_key())
        return EditsFile(
            MappingProxyType({}),
            tuple(c.finding() for c in ordered),
            (),
            tuple(sorted(set(pending))),
            tuple(ordered),
            tuple(no_base),
        )
    return EditsFile(
        MappingProxyType(dict(sorted(parts.items()))),
        (),
        tuple(sorted(captured, key=lambda k: _key_order(k))),
        tuple(sorted(set(pending), key=lambda k: _key_order(k))),
        (),
        tuple(no_base),
    )


def _key_order(text: str) -> tuple[str, int, str]:
    path, _, prop = text.partition("#")
    return PropertyKey(path, prop).sort_key()


__all__ = [
    "BASE_FILE",
    "BASE_SCHEMA",
    "EDITS_FILE",
    "EDITS_SCHEMA",
    "EDIT_ISSUE_CODES",
    "EVIDENCE",
    "PROPERTIES",
    "BaseEntry",
    "BaseRecord",
    "Conflict",
    "Decision",
    "EditsFile",
    "PartEdits",
    "PropertyKey",
    "PropertyMerge",
    "Take",
    "capture_edits",
    "merge_properties",
    "merge_property",
    "parse_takes",
    "read_base",
    "read_edits",
    "write_base",
    "write_edits",
]
