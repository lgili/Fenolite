# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A minimal reader of ``fenolite.package.v0`` records for the footprint generators (change c0260).

c0259 owns the record envelope (id, version, licence, sources, evidence, reviews, stable uid). Until it
lands, this reader takes the envelope keys it needs (``schema``, ``family`` or c0259's ``generator``,
``name`` or ``id``, ``summary``, ``evidence``, ``sources``), accepts c0259's other header keys as given,
and checks the family keys of design decision 2 exactly: an unknown key, a missing required key or a
wrong type raises ``FormatError`` (``FEN-3004``) naming the file and the key. Lengths are exact
``LengthRange`` values; counts are integers; TOML floats are refused (``parse_float=Decimal``).
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import cast

from fenolite.core.errors import FormatError
from fenolite.core.quantities import LengthRange, parse_length_range

SCHEMA = "fenolite.package.v0"
FAMILIES = ("chip", "molded", "gullwing", "nolead", "grid", "to", "dip", "header", "connector")
DENSITIES = ("nominal",)
RESERVED_DENSITIES = ("compact", "robust")
EVIDENCE_LABELS = (
    "ALTIUM-VERIFIED(kit)",
    "ALTIUM-VERIFIED(author-report)",
    "KICAD-VERIFIED",
    "CORPUS-VERIFIED",
    "INFERRED",
    "UNKNOWN",
    "UNVERIFIED",
)
_NAME = re.compile(r"^[A-Za-z0-9_.+-]+$")

# --- the schema language ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Key:
    """One key of a table: its ``kind``, whether it is required, and its choices or sub-table."""

    kind: str
    """``length``, ``count`` (a positive integer), ``text``, ``texts``, ``counts``, ``table``,
    ``tables`` (an array of tables), ``span`` (``"2..15"``), ``depopulated``, ``lengths`` (a length or a
    table of lengths)."""
    required: bool = False
    choices: tuple[str, ...] = ()
    table: Mapping[str, Key] = field(default_factory=lambda: {})


def _req(kind: str, **more: object) -> Key:
    return Key(kind, True, **more)  # type: ignore[arg-type]


def _opt(kind: str, **more: object) -> Key:
    return Key(kind, False, **more)  # type: ignore[arg-type]


def _body(*, required: tuple[str, ...] = ("length", "width"), offset: bool = False) -> Key:
    keys = {
        "length": Key("length", "length" in required),
        "width": Key("length", "width" in required),
        "height": Key("length", "height" in required),
        "standoff": Key("length"),
    }
    if offset:
        keys["offset"] = Key("length")
    return _req("table", table=keys)


_PAD = _opt("table", table={"length": _req("length"), "width": _req("length")})
_PASTE = _opt("table", table={"grid": _req("counts"), "window": _req("length"), "pitch": _req("length")})
_ROWS_LAND = {
    "source": _req("text"),
    "pad": _PAD,
    "row_spacing": _opt("length"),
    "row_spacing_x": _opt("length"),
    "row_spacing_y": _opt("length"),
}
_THT_LAND = {"source": _req("text"), "drill": _opt("length"), "pad_diameter": _opt("length")}
_POLARITY = _opt("text", choices=("none", "pad1"))
_MOUNT = ("tht", "smd")

FAMILY_KEYS: Mapping[str, Mapping[str, Key]] = {
    "chip": {
        "body": _body(),
        "terminal": _req("table", table={"length": _req("length")}),
        "polarity": _POLARITY,
    },
    "molded": {
        "body": _body(),
        "span": _req("length"),
        "lead": _req("table", table={"length": _req("length"), "width": _req("length")}),
        "lead_style": _opt("text", choices=("flat", "inward", "cylinder")),
        "polarity": _POLARITY,
    },
    "gullwing": {
        "pins": _req("count"),
        "pitch": _req("length"),
        "arrangement": _req("text", choices=("dual", "quad", "sides")),
        "body": _body(),
        "span": _opt("length"),
        "span_x": _opt("length"),
        "span_y": _opt("length"),
        "lead": _req(
            "table", table={"length": _req("length"), "width": _req("length"), "thickness": _opt("length")}
        ),
        "side": _opt(
            "tables",
            table={
                "edge": _req("text", choices=("left", "right")),
                "numbers": _req("texts"),
                "positions": _req("counts"),
            },
        ),
        "tab": _opt(
            "table",
            table={
                "number": _req("text"),
                "width": _req("length"),
                "length": _req("length"),
                "edge": _req("text", choices=("left", "right")),
            },
        ),
    },
    "nolead": {
        "pins": _req("count"),
        "pitch": _req("length"),
        "arrangement": _req("text", choices=("dual", "quad")),
        "body": _body(),
        "terminal": _req("table", table={"length": _req("length"), "width": _req("length")}),
        "pull_back": _opt("length"),
        "ep": _opt("table", table={"length": _req("length"), "width": _req("length")}),
        "ep_number": _opt("text"),
        "paste": _PASTE,
    },
    "grid": {
        "rows": _req("count"),
        "columns": _req("count"),
        "pitch": _opt("length"),
        "pitch_x": _opt("length"),
        "pitch_y": _opt("length"),
        "body": _body(),
        "ball": _req("table", table={"diameter": _req("length")}),
        "pad": _opt("text", choices=("nsmd", "smd")),
        "depopulated": _opt("depopulated"),
    },
    "to": {
        "mount": _req("text", choices=_MOUNT),
        "leads": _req("count"),
        "pitch": _req("length"),
        "body": _body(offset=True),
        "span": _opt("length"),
        "lead": _req(
            "table", table={"width": _req("length"), "thickness": _req("length"), "length": _req("length")}
        ),
        "tab": _opt(
            "table",
            table={
                "width": _req("length"),
                "length": _req("length"),
                "hole": _opt("length"),
                "number": _opt("text"),
            },
        ),
    },
    "dip": {
        "pins": _req("count"),
        "pitch": _req("length"),
        "row_spacing": _req("length"),
        "body": _body(),
        "lead": _req(
            "table", table={"width": _req("length"), "thickness": _req("length"), "length": _opt("length")}
        ),
    },
    "header": {
        "rows": _req("count"),
        "columns": _req("count"),
        "pitch": _req("length"),
        "mount": _req("text", choices=_MOUNT),
        "orientation": _req("text", choices=("vertical", "horizontal")),
        "pin": _req(
            "table",
            table={
                "width": _req("length"),
                "thickness": _opt("length"),
                "length_above": _req("length"),
                "length_below": _req("length"),
            },
        ),
        "body": _body(required=("height",), offset=True),
        "numbering": _opt("text", choices=("rows-first", "columns-first")),
    },
    "connector": {
        "series": _req("text"),
        "positions": _req("span"),
        "pitch": _req("length"),
        "name_pattern": _req("text"),
        "body": _req(
            "table",
            table={
                "length": _req("lengths", table={"per_position": _req("length"), "extra": _req("length")}),
                "width": _req("length"),
                "height": _opt("length"),
                "offset": _opt("length"),
            },
        ),
        "pin": _req(
            "table",
            table={
                "width": _req("length"),
                "thickness": _opt("length"),
                "length_above": _opt("length"),
                "length_below": _opt("length"),
            },
        ),
        "mount": _opt("text", choices=("tht",)),
        "orientation": _opt("text", choices=("vertical", "horizontal")),
        "mechanical": _opt(
            "tables",
            table={
                "kind": _req("text", choices=("hole", "pad")),
                "drill": _req("length"),
                "pad_diameter": _opt("length"),
                "beyond": _req("length"),
                "y": _req("length"),
                "number": _opt("text"),
            },
        ),
    },
}
"""The keys after the envelope, per family (design decision 2). ``connector`` holds one series."""

LAND_KEYS: Mapping[str, Mapping[str, Key]] = {
    "chip": _ROWS_LAND,
    "molded": _ROWS_LAND,
    "gullwing": {
        **_ROWS_LAND,
        "tab": _opt("table", table={"length": _req("length"), "width": _req("length"), "at": _req("length")}),
    },
    "nolead": {
        **_ROWS_LAND,
        "ep": _opt("table", table={"length": _req("length"), "width": _req("length")}),
        "paste": _PASTE,
    },
    "grid": {"source": _req("text"), "pad_diameter": _req("length")},
    "to": {
        **_THT_LAND,
        "pad": _PAD,
        "tab": _opt("table", table={"length": _req("length"), "width": _req("length"), "at": _req("length")}),
        "row_spacing": _opt("length"),
    },
    "dip": _THT_LAND,
    "header": {**_THT_LAND, "pad": _PAD, "row_spacing": _opt("length")},
    "connector": _THT_LAND,
}
"""The keys of the manufacturer's ``[land]`` per family (design decision 7)."""

GENERATE_KEYS: Mapping[str, Key] = {
    "lands": _opt("count"),
    "drawing": Key("drawing", True),
    "density": _opt("text"),
}
ENVELOPE_KEYS = (
    "schema",
    "family",
    "generator",
    "name",
    "id",
    "summary",
    "evidence",
    "sources",
    "version",
    "category",
    "licence",
    "origin",
    "reviewed_by",
    "replaces",
    "deprecated",
    "generate",
    "land",
)
"""The keys a record may hold besides its family keys; c0259 checks the ones kept as given."""

# --- the parsed record ----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Keys:
    """A parsed table: typed getters by key; a missing optional key gives ``None``."""

    values: Mapping[str, object]
    path: str = ""

    def has(self, key: str) -> bool:
        return key in self.values

    def length(self, key: str) -> LengthRange | None:
        return cast("LengthRange | None", self.values.get(key))

    def count(self, key: str) -> int | None:
        return cast("int | None", self.values.get(key))

    def text(self, key: str) -> str | None:
        return cast("str | None", self.values.get(key))

    def texts(self, key: str) -> tuple[str, ...]:
        return cast("tuple[str, ...]", self.values.get(key, ()))

    def counts(self, key: str) -> tuple[int, ...]:
        return cast("tuple[int, ...]", self.values.get(key, ()))

    def table(self, key: str) -> Keys | None:
        return cast("Keys | None", self.values.get(key))

    def tables(self, key: str) -> tuple[Keys, ...]:
        return cast("tuple[Keys, ...]", self.values.get(key, ()))

    def raw(self, key: str) -> object:
        return self.values.get(key)


@dataclass(frozen=True, slots=True)
class Package:
    """One package record: its envelope, its family keys, ``[generate]`` and the optional ``[land]``."""

    family: str
    name: str
    namespace: str
    keys: Keys
    drawing: int
    lands: int | None = None
    density: str = "nominal"
    land: Keys | None = None
    summary: str = ""
    evidence: str = "INFERRED"
    sources: tuple[str, ...] = ()
    file: str = ""


# --- reading ----------------------------------------------------------------------------------------------


def _fail(message: str, file: str, locator: str) -> FormatError:
    return FormatError(message, file=file, locator=locator)


def _path(prefix: str, key: str) -> str:
    return f"{prefix}.{key}" if prefix else key


def _value(spec: Key, raw: object, file: str, where: str) -> object:
    kind = spec.kind
    if kind == "length":
        return parse_length_range(raw, file=file, locator=where)
    if kind in ("count", "drawing"):
        if not isinstance(raw, int) or isinstance(raw, bool) or raw < (0 if kind == "drawing" else 1):
            low = "a whole number from 0" if kind == "drawing" else "a positive whole number"
            raise _fail(f"{where} must be {low}", file, where)
        return raw
    if kind == "text":
        if not isinstance(raw, str) or not raw:
            raise _fail(f"{where} must be a text", file, where)
        if spec.choices and raw not in spec.choices:
            raise _fail(f"{where} is {raw!r}; expected one of {', '.join(spec.choices)}", file, where)
        return raw
    if kind in ("texts", "counts"):
        items = cast("list[object]", raw) if isinstance(raw, list) else None
        if not items:
            raise _fail(f"{where} must be a non-empty array", file, where)
        want = str if kind == "texts" else int
        if any(not isinstance(item, want) or isinstance(item, bool) for item in items):
            raise _fail(f"{where} must hold {'texts' if kind == 'texts' else 'whole numbers'}", file, where)
        if kind == "counts" and any(cast("int", item) < 0 for item in items):
            raise _fail(f"{where} must hold whole numbers from 0", file, where)
        return tuple(items)
    if kind == "table":
        if not isinstance(raw, dict):
            raise _fail(f"{where} must be a table", file, where)
        return _table(spec.table, cast("dict[str, object]", raw), file, where)
    if kind == "tables":
        items = cast("list[object]", raw) if isinstance(raw, list) else None
        if not items or any(not isinstance(item, dict) for item in items):
            raise _fail(f"{where} must be an array of tables", file, where)
        return tuple(
            _table(spec.table, cast("dict[str, object]", item), file, f"{where}[{i}]")
            for i, item in enumerate(items)
        )
    if kind == "lengths":
        if isinstance(raw, dict) and set(cast("dict[str, object]", raw)) <= set(spec.table):
            return _table(spec.table, cast("dict[str, object]", raw), file, where)
        return parse_length_range(cast("object", raw), file=file, locator=where)
    if kind == "span":
        match = re.fullmatch(r"\s*(\d+)\s*\.\.\s*(\d+)\s*", raw) if isinstance(raw, str) else None
        if match is None or not 1 <= int(match.group(1)) <= int(match.group(2)):
            raise _fail(f"{where} must be a text 'first..last' of whole numbers", file, where)
        return (int(match.group(1)), int(match.group(2)))
    if kind == "depopulated":
        if isinstance(raw, list):
            names = cast("list[object]", raw)
            if not names or any(not isinstance(n, str) for n in names):
                raise _fail(f"{where} must be ball names or a table {{center = 'RxC'}}", file, where)
            return tuple(cast("list[str]", names))
        if isinstance(raw, dict) and set(cast("dict[str, object]", raw)) == {"center"}:
            center = cast("dict[str, object]", raw)["center"]
            match = re.fullmatch(r"(\d+)x(\d+)", center) if isinstance(center, str) else None
            if match is None:
                raise _fail(f"{where}.center must be a text 'RxC'", file, f"{where}.center")
            return (int(match.group(1)), int(match.group(2)))
        raise _fail(f"{where} must be ball names or a table {{center = 'RxC'}}", file, where)
    raise AssertionError(kind)  # pragma: no cover - the schema names only the kinds above


def _table(schema: Mapping[str, Key], raw: Mapping[str, object], file: str, prefix: str) -> Keys:
    for key in sorted(raw):
        if key not in schema:
            raise _fail(f"unknown key {_path(prefix, key)!r}", file, _path(prefix, key))
    values: dict[str, object] = {}
    for key, spec in schema.items():
        where = _path(prefix, key)
        if key not in raw:
            if spec.required:
                raise _fail(f"missing required key {where!r}", file, where)
            continue
        values[key] = _value(spec, raw[key], file, where)
    return Keys(values, prefix)


def _no_floats(value: object, file: str, where: str) -> None:
    if isinstance(value, Decimal):
        raise _fail(f"{where} is a bare number; write a length with its unit, as a text", file, where)
    if isinstance(value, dict):
        for key, item in cast("dict[str, object]", value).items():
            _no_floats(item, file, _path(where, key))
    elif isinstance(value, list):
        for i, item in enumerate(cast("list[object]", value)):
            _no_floats(item, file, f"{where}[{i}]")


def read_package(text: str, *, file: str = "") -> Package:
    """The package record in ``text``; ``FormatError`` (``FEN-3004``) naming ``file`` and the key."""
    try:
        raw: dict[str, object] = tomllib.loads(text, parse_float=Decimal)
    except tomllib.TOMLDecodeError as exc:
        raise _fail(f"not a TOML record: {exc}", file, "") from None
    return package_from(raw, file=file)


def _envelope_text(raw: Mapping[str, object], key: str, file: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise _fail(f"{key} must be a text", file, key)
    return value


def package_from(raw: Mapping[str, object], *, file: str = "") -> Package:
    """The package of an already parsed TOML table (see ``read_package``)."""
    _no_floats(dict(raw), file, "")
    schema = raw.get("schema")
    if schema != SCHEMA:
        raise _fail(f"schema must be {SCHEMA!r}, not {schema!r}", file, "schema")
    family = _envelope_text(raw, "family", file)
    generator = _envelope_text(raw, "generator", file)
    if family is None and generator is None:
        raise _fail("missing required key 'family'", file, "family")
    if family is not None and generator is not None and family != generator:
        raise _fail(f"family {family!r} and generator {generator!r} disagree", file, "family")
    family = cast("str", family or generator)
    if family not in FAMILIES:
        raise _fail(f"family is {family!r}; expected one of {', '.join(FAMILIES)}", file, "family")
    name, namespace = _name(raw, file)
    schema_keys = FAMILY_KEYS[family]
    for key in sorted(raw):
        if key not in ENVELOPE_KEYS and key not in schema_keys:
            raise _fail(f"unknown key {key!r} for family {family!r}", file, key)
    body = {key: value for key, value in raw.items() if key in schema_keys}
    keys = _table(schema_keys, body, file, "")
    land = None
    if "land" in raw:
        land_raw = raw["land"]
        if not isinstance(land_raw, dict):
            raise _fail("land must be a table", file, "land")
        land = _table(LAND_KEYS[family], cast("dict[str, object]", land_raw), file, "land")
    gen_raw = raw.get("generate")
    if not isinstance(gen_raw, dict):
        raise _fail("missing required table 'generate' (with the key 'drawing')", file, "generate")
    generate = _table(GENERATE_KEYS, cast("dict[str, object]", gen_raw), file, "generate")
    density = generate.text("density") or "nominal"
    check_density(density, file=file, locator="generate.density")
    lands = generate.count("lands")
    if land is None and lands is None:
        raise _fail(
            "the record has no [land], so the calculator draws it and needs 'lands' "
            "(the constant table version)",
            file,
            "generate.lands",
        )
    evidence = _envelope_text(raw, "evidence", file) or "INFERRED"
    if evidence not in EVIDENCE_LABELS and not re.fullmatch(r"ORACLE-VERIFIED\([^()]+\)", evidence):
        raise _fail(f"evidence {evidence!r} is not an evidence label", file, "evidence")
    sources = raw.get("sources", [])
    if not isinstance(sources, list) or any(not isinstance(s, str) for s in cast("list[object]", sources)):
        raise _fail("sources must be an array of texts", file, "sources")
    return Package(
        family=family,
        name=name,
        namespace=namespace,
        keys=keys,
        drawing=cast("int", generate.count("drawing")),
        lands=lands,
        density=density,
        land=land,
        summary=_envelope_text(raw, "summary", file) or "",
        evidence=evidence,
        sources=tuple(cast("list[str]", sources)),
        file=file,
    )


def _name(raw: Mapping[str, object], file: str) -> tuple[str, str]:
    name = _envelope_text(raw, "name", file)
    ident = _envelope_text(raw, "id", file)
    namespace = ""
    if ident is not None:
        namespace, colon, id_name = ident.partition(":")
        if not colon or not _NAME.match(namespace) or not _NAME.match(id_name):
            raise _fail(f"id {ident!r} must be '<namespace>:<name>'", file, "id")
        if name is not None and name != id_name:
            raise _fail(f"name {name!r} and id {ident!r} disagree", file, "name")
        name = id_name
    if name is None:
        if raw.get("family") == "connector" or raw.get("generator") == "connector":
            return "", namespace  # a series: each position gets its name from name_pattern
        raise _fail("missing required key 'name' (or 'id')", file, "name")
    if not _NAME.match(name):
        raise _fail(f"name {name!r} holds a character outside [A-Za-z0-9_.+-]", file, "name")
    return name, namespace


def check_density(density: str, *, file: str = "", locator: str = "density") -> None:
    """``FormatError`` unless ``density`` is shipped; ``compact`` and ``robust`` are named as reserved."""
    if density in DENSITIES:
        return
    if density in RESERVED_DENSITIES:
        raise _fail(
            f"density {density!r} is reserved and not shipped; only 'nominal' is (open question 1)",
            file,
            locator,
        )
    raise _fail(f"density {density!r} is not known; only 'nominal' is shipped", file, locator)


def lengths_of(keys: Keys, names: Sequence[str]) -> dict[str, LengthRange]:
    """The length ranges of ``names`` that ``keys`` gives."""
    found: dict[str, LengthRange] = {}
    for name in names:
        value = keys.length(name)
        if value is not None:
            found[name] = value
    return found


__all__ = [
    "DENSITIES",
    "ENVELOPE_KEYS",
    "FAMILIES",
    "FAMILY_KEYS",
    "GENERATE_KEYS",
    "LAND_KEYS",
    "RESERVED_DENSITIES",
    "SCHEMA",
    "Key",
    "Keys",
    "Package",
    "check_density",
    "package_from",
    "read_package",
]
