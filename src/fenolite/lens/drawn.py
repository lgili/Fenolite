# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``schematic.toml``: the drawn schematic file, schema ``fenolite.drawn-schematic.v0`` (capability
``drawn-schematic``, "Drawn schematic file", "Drawn file numbers", "Drawn sheet items" and "Canonical drawn
file"; change c0276; ``docs/drawn-schematic.md``).

``read_drawn`` reads the text into a ``DrawnSchematic``: closed key sets, millimetres read as exact
decimals and stored as integer nanometres, angles in whole degrees. Any unknown key, missing key, wrong
type or bad value raises ``FormatError`` (``FEN-3004``) naming the file and a locator such as
``sheet[0].wire[1].pts``. ``write_drawn`` writes a value in canonical form, so reading and writing a
canonical file gives its bytes. Nothing here reads or writes a file.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Any, cast, get_args

from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError
from fenolite.core.schema_ids import accepts_schema
from fenolite.model._drawn_text import HEADER as HEADER
from fenolite.model._drawn_text import mm as mm
from fenolite.model._drawn_text import write_drawn as write_drawn
from fenolite.model.drawn import (
    FIELD_ROTATIONS,
    JUSTIFY_WORDS,
    MIRRORS,
    ROTATIONS,
    SCHEMA,
    TITLE_FIELDS,
    DrawnBusAlias,
    DrawnBusEntry,
    DrawnField,
    DrawnFont,
    DrawnJunction,
    DrawnLabel,
    DrawnOpaque,
    DrawnPin,
    DrawnPower,
    DrawnSchematic,
    DrawnSheet,
    DrawnSheetProperty,
    DrawnSheetRef,
    DrawnSymbol,
)
from fenolite.model.presentation import PaperSize

FILE_NAME = "schematic.toml"
ROOT_KEYS: tuple[str, ...] = ("schema", "root", "sheet")
SHEET_KEYS: tuple[str, ...] = (
    "key", "paper", "title_block", "generated", "symbol", "power", "wire", "bus", "bus_entry", "junction",
    "no_connect", "label", "bus_alias", "sheet_ref", "opaque",
)  # fmt: skip
SYMBOL_KEYS: tuple[str, ...] = (
    "part",
    "unit",
    "at",
    "rotation",
    "mirror",
    "symbol",
    "empty_footprint",
    "fields",
)
FIELD_KEYS: tuple[str, ...] = ("at", "rotation", "justify", "hide", "font")
SHEET_PROPERTY_KEYS: tuple[str, ...] = ("text", *FIELD_KEYS)
FONT_KEYS: tuple[str, ...] = ("size", "thickness", "bold", "italic", "face")
POWER_KEYS: tuple[str, ...] = ("symbol", "net", "at", "rotation", "mirror", "fields")
POLYLINE_KEYS: tuple[str, ...] = ("pts",)
BUS_ENTRY_KEYS: tuple[str, ...] = ("at", "size")
JUNCTION_KEYS: tuple[str, ...] = ("at", "diameter")
NO_CONNECT_KEYS: tuple[str, ...] = ("at",)
LABEL_KEYS: tuple[str, ...] = (
    "kind",
    "text",
    "at",
    "rotation",
    "shape",
    "font",
    "justify",
    "intersheet_refs",
)
BUS_ALIAS_KEYS: tuple[str, ...] = ("name", "members")
SHEET_REF_KEYS: tuple[str, ...] = (
    "key", "sheet", "module", "name", "file", "at", "size", "page", "fields", "properties", "pin",
)  # fmt: skip
PIN_KEYS: tuple[str, ...] = ("name", "shape", "at", "rotation", "font", "justify")
OPAQUE_KEYS: tuple[str, ...] = ("kicad", "altium")
TITLE_KEYS: tuple[str, ...] = (*TITLE_FIELDS, "params")
CLOSED_KEYS: Mapping[str, tuple[str, ...]] = {
    "root": ROOT_KEYS,
    "sheet": SHEET_KEYS,
    "title_block": TITLE_KEYS,
    "symbol": SYMBOL_KEYS,
    "field": FIELD_KEYS,
    "sheet_property": SHEET_PROPERTY_KEYS,
    "font": FONT_KEYS,
    "power": POWER_KEYS,
    "wire": POLYLINE_KEYS,
    "bus": POLYLINE_KEYS,
    "bus_entry": BUS_ENTRY_KEYS,
    "junction": JUNCTION_KEYS,
    "no_connect": NO_CONNECT_KEYS,
    "label": LABEL_KEYS,
    "bus_alias": BUS_ALIAS_KEYS,
    "sheet_ref": SHEET_REF_KEYS,
    "pin": PIN_KEYS,
    "opaque": OPAQUE_KEYS,
}
"""Every table of the file and its closed key set, in canonical order (``docs/drawn-schematic.md``)."""
SHEET_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")
"""The pattern of a sheet key and of a sheet reference key."""
SHAPES: frozenset[str] = frozenset({"input", "output", "bidirectional", "tri_state", "passive"})
PAPERS: tuple[str, ...] = tuple(p for p in get_args(PaperSize) if p != "custom")
"""The papers of a drawn sheet: the named papers of ``SheetFrameRef``."""
_NM = 1_000_000
_UDEG = 1_000_000

Table = Mapping[str, Any]


class _Reader:
    def __init__(self, file: str) -> None:
        self.file = file

    def fail(self, where: str, message: str) -> FormatError:
        return FormatError(message, file=self.file or FILE_NAME, locator=where)

    def table(self, value: object, where: str, kind: str, required: Sequence[str]) -> Table:
        if not isinstance(value, dict):
            raise self.fail(where, f"{kind} is a table")
        data = cast(dict[str, Any], value)
        allowed = CLOSED_KEYS[kind]
        for key in data:
            if key not in allowed:
                raise self.fail(f"{where}.{key}" if where else key, f"unknown key {key!r} of {kind}")
        for key in required:
            if key not in data:
                raise self.fail(f"{where}.{key}" if where else key, f"{kind} needs the key {key!r}")
        return data

    def text(self, data: Table, key: str, where: str, default: str | None = None) -> str:
        value = data.get(key, default)
        if not isinstance(value, str):
            raise self.fail(f"{where}.{key}", f"{key} is a text, not {value!r}")
        return value

    def boolean(self, data: Table, key: str, where: str) -> bool:
        value = data.get(key, False)
        if not isinstance(value, bool):
            raise self.fail(f"{where}.{key}", f"{key} is true or false, not {value!r}")
        return value

    def length(self, value: object, where: str) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
            raise self.fail(where, f"a length is a number of millimetres, not {value!r}")
        number = Decimal(value)
        if not number.is_finite():
            raise self.fail(where, f"{value} mm is not a whole number of nanometres")
        numerator, denominator = number.as_integer_ratio()
        whole, remainder = divmod(numerator * _NM, denominator)
        if remainder:
            raise self.fail(where, f"{value} mm is not a whole number of nanometres")
        return whole

    def point(self, value: object, where: str) -> Point:
        if not isinstance(value, list) or len(cast(list[object], value)) != 2:
            raise self.fail(where, f"a point is [x, y] in millimetres, not {value!r}")
        pair = cast(list[object], value)
        return Point(self.length(pair[0], where), self.length(pair[1], where))

    def angle(self, data: Table, key: str, where: str, allowed: frozenset[int]) -> int:
        value = data.get(key, 0)
        if isinstance(value, Decimal) and value == value.to_integral_value():
            value = int(value)
        if isinstance(value, bool) or not isinstance(value, int) or value * _UDEG not in allowed:
            shown = ", ".join(str(a // _UDEG) for a in sorted(allowed))
            raise self.fail(f"{where}.{key}", f"{key} is one of {shown} degrees, not {value!r}")
        return value * _UDEG

    def items(self, data: Table, key: str, where: str) -> list[tuple[str, object]]:
        value = data.get(key, [])
        if not isinstance(value, list):
            raise self.fail(f"{where}.{key}", f"{key} is an array of tables")
        return [(f"{where}.{key}[{i}]", item) for i, item in enumerate(cast(list[object], value))]

    def justify(self, data: Table, where: str) -> str:
        value = self.text(data, "justify", where, "")
        if any(word not in JUSTIFY_WORDS for word in value.split()) or value != " ".join(value.split()):
            raise self.fail(f"{where}.justify", f"justify {value!r} is words of {sorted(JUSTIFY_WORDS)}")
        return value

    def font(self, data: Table, where: str) -> DrawnFont | None:
        if "font" not in data:
            return None
        at = f"{where}.font"
        font = self.table(data["font"], at, "font", ())
        if not font:
            raise self.fail(at, "an empty font is absent; leave out the font key")
        size = None
        if "size" in font:
            pair = self.point(font["size"], f"{at}.size")
            if pair.x <= 0 or pair.y <= 0:
                raise self.fail(f"{at}.size", "font width and height must be positive")
            size = Size(pair.x, pair.y)
        thickness = self.length(font["thickness"], f"{at}.thickness") if "thickness" in font else None
        if thickness is not None and thickness < 0:
            raise self.fail(f"{at}.thickness", "font thickness cannot be negative")
        face = self.text(font, "face", at) if "face" in font else None
        try:
            return DrawnFont(
                size,
                thickness,
                self.boolean(font, "bold", at) if "bold" in font else None,
                self.boolean(font, "italic", at) if "italic" in font else None,
                face,
            )
        except ValueError as error:
            raise self.fail(f"{at}.face" if face is not None else at, str(error)) from error

    def fields(
        self, data: Table, where: str, *, names: frozenset[str] | None = None
    ) -> tuple[DrawnField, ...]:
        value = data.get("fields", {})
        if not isinstance(value, dict):
            raise self.fail(f"{where}.fields", "fields is a table of field poses")
        found: list[DrawnField] = []
        for name, raw in cast(dict[str, object], value).items():
            at = f"{where}.fields.{name}"
            if names is not None and name not in names:
                raise self.fail(at, f"sheet property is one of {sorted(names)}, not {name!r}")
            pose = self.table(raw, at, "field", ("at",))
            found.append(
                DrawnField(
                    name,
                    self.point(pose["at"], f"{at}.at"),
                    self.angle(pose, "rotation", at, FIELD_ROTATIONS),
                    self.justify(pose, at),
                    self.boolean(pose, "hide", at),
                    self.font(pose, at),
                )
            )
        return tuple(found)

    def polyline(self, raw: object, where: str, kind: str) -> tuple[Point, ...]:
        data = self.table(raw, where, kind, ("pts",))
        points = data["pts"]
        if not isinstance(points, list) or len(cast(list[object], points)) < 2:
            raise self.fail(f"{where}.pts", f"a {kind} has two or more points")
        return tuple(self.point(p, f"{where}.pts[{i}]") for i, p in enumerate(cast(list[object], points)))

    def properties(self, data: Table, where: str) -> tuple[DrawnSheetProperty, ...]:
        value = data.get("properties", {})
        if not isinstance(value, dict):
            raise self.fail(f"{where}.properties", "properties is a table of custom sheet properties")
        found: list[DrawnSheetProperty] = []
        for name, raw in cast(dict[str, object], value).items():
            at = f"{where}.properties.{name}"
            prop = self.table(raw, at, "sheet_property", ("text", "at"))
            try:
                found.append(
                    DrawnSheetProperty(
                        name,
                        self.text(prop, "text", at),
                        self.point(prop["at"], f"{at}.at"),
                        self.angle(prop, "rotation", at, FIELD_ROTATIONS),
                        self.justify(prop, at),
                        self.boolean(prop, "hide", at),
                        self.font(prop, at),
                    )
                )
            except (TypeError, ValueError) as error:
                raise self.fail(at, str(error)) from error
        return tuple(found)

    def shape(self, data: Table, where: str, *, required: bool) -> str:
        value = self.text(data, "shape", where, "")
        if (required or value) and value not in SHAPES:
            raise self.fail(f"{where}.shape", f"shape is one of {sorted(SHAPES)}, not {value!r}")
        return value

    def sheet(self, raw: object, where: str) -> DrawnSheet:
        data = self.table(raw, where, "sheet", ("key", "paper"))
        key = self.text(data, "key", where)
        if not SHEET_KEY.fullmatch(key):
            raise self.fail(f"{where}.key", f"sheet key {key!r} does not match {SHEET_KEY.pattern}")
        block: tuple[tuple[str, str], ...] = ()
        if "title_block" in data:
            at = f"{where}.title_block"
            table = self.table(data["title_block"], at, "title_block", ())
            pairs = [(name, self.text(table, name, at)) for name in TITLE_FIELDS if name in table]
            params = table.get("params", {})
            if not isinstance(params, dict):
                raise self.fail(f"{at}.params", "params is a table of texts")
            for name, value in sorted(cast(dict[str, object], params).items()):
                if not isinstance(value, str):
                    raise self.fail(f"{at}.params.{name}", f"a parameter is a text, not {value!r}")
                pairs.append((f"param.{name}", value))
            block = tuple(pairs)
        paper = self.text(data, "paper", where)
        if paper not in PAPERS:
            raise self.fail(f"{where}.paper", f"paper is one of {', '.join(PAPERS)}, not {paper!r}")
        symbols = [self.symbol(item, at) for at, item in self.items(data, "symbol", where)]
        powers = [self.power(item, at) for at, item in self.items(data, "power", where)]
        wires = [self.polyline(item, at, "wire") for at, item in self.items(data, "wire", where)]
        buses = [self.polyline(item, at, "bus") for at, item in self.items(data, "bus", where)]
        entries: list[DrawnBusEntry] = []
        for at, item in self.items(data, "bus_entry", where):
            table = self.table(item, at, "bus_entry", ("at", "size"))
            entries.append(
                DrawnBusEntry(self.point(table["at"], f"{at}.at"), self.point(table["size"], f"{at}.size"))
            )
        junctions: list[DrawnJunction] = []
        for at, item in self.items(data, "junction", where):
            table = self.table(item, at, "junction", ("at",))
            diameter = self.length(table.get("diameter", 0), f"{at}.diameter")
            if diameter < 0:
                raise self.fail(f"{at}.diameter", "a junction diameter cannot be negative")
            junctions.append(DrawnJunction(self.point(table["at"], f"{at}.at"), diameter))
        flags: list[Point] = []
        for at, item in self.items(data, "no_connect", where):
            table = self.table(item, at, "no_connect", ("at",))
            flags.append(self.point(table["at"], f"{at}.at"))
        labels = [self.label(item, at) for at, item in self.items(data, "label", where)]
        aliases: list[DrawnBusAlias] = []
        for at, item in self.items(data, "bus_alias", where):
            table = self.table(item, at, "bus_alias", ("name", "members"))
            members = table["members"]
            if not isinstance(members, list) or not all(
                isinstance(m, str) for m in cast(list[object], members)
            ):
                raise self.fail(f"{at}.members", "members is an array of texts")
            aliases.append(DrawnBusAlias(self.text(table, "name", at), tuple(cast(list[str], members))))
        refs = [self.sheet_ref(item, at) for at, item in self.items(data, "sheet_ref", where)]
        opaques: list[DrawnOpaque] = []
        for at, item in self.items(data, "opaque", where):
            table = self.table(item, at, "opaque", ("kicad",))
            text = self.text(table, "kicad", at)
            altium = self.text(table, "altium", at, "")
            # an Altium record that KiCad cannot draw has no KiCad text: the KiCad build carries it in the
            # sheet carrier (change c0470, design D4)
            if not (text == "" and altium) and not _one_expression(text):
                raise self.fail(f"{at}.kicad", "an opaque item holds one KiCad S-expression")
            opaques.append(DrawnOpaque(text, altium))
        generated = self.boolean(data, "generated", where)
        sheet = DrawnSheet(
            key,
            self.text(data, "paper", where),
            block,
            generated,
            tuple(symbols),
            tuple(powers),
            tuple(wires),
            tuple(buses),
            tuple(entries),
            tuple(junctions),
            tuple(flags),
            tuple(labels),
            tuple(aliases),
            tuple(refs),
            tuple(opaques),
        )
        if generated and any(
            (symbols, powers, wires, buses, entries, junctions, flags, labels, aliases, refs, opaques)
        ):
            raise self.fail(where, f"sheet {key} is generated and holds items of its own")
        return sheet

    def symbol(self, raw: object, where: str) -> DrawnSymbol:
        data = self.table(raw, where, "symbol", ("part", "at"))
        part = self.text(data, "part", where)
        unit = data.get("unit", 1)
        if isinstance(unit, bool) or not isinstance(unit, int) or unit < 1:
            raise self.fail(f"{where}.unit", f"unit is a whole number from 1, not {unit!r}")
        mirror = self.text(data, "mirror", where, "")
        if mirror not in MIRRORS:
            raise self.fail(f"{where}.mirror", f"mirror is '', 'x' or 'y', not {mirror!r}")
        if not part:
            raise self.fail(f"{where}.part", "a symbol names its part")
        return DrawnSymbol(
            part,
            unit,
            self.point(data["at"], f"{where}.at"),
            self.angle(data, "rotation", where, ROTATIONS),
            mirror,
            self.fields(data, where),
            self.text(data, "symbol", where, ""),
            self.boolean(data, "empty_footprint", where),
        )

    def power(self, raw: object, where: str) -> DrawnPower:
        data = self.table(raw, where, "power", ("symbol", "net", "at"))
        symbol, net = self.text(data, "symbol", where), self.text(data, "net", where)
        if not symbol or not net:
            raise self.fail(where, "a power symbol names its library symbol and its net")
        mirror = self.text(data, "mirror", where, "")
        if mirror not in MIRRORS:
            raise self.fail(f"{where}.mirror", f"mirror is '', 'x' or 'y', not {mirror!r}")
        return DrawnPower(
            symbol,
            net,
            self.point(data["at"], f"{where}.at"),
            self.angle(data, "rotation", where, ROTATIONS),
            self.fields(data, where),
            mirror,
        )

    def label(self, raw: object, where: str) -> DrawnLabel:
        data = self.table(raw, where, "label", ("kind", "text", "at"))
        kind = self.text(data, "kind", where)
        if kind not in ("local", "global", "hierarchical"):
            raise self.fail(f"{where}.kind", f"kind is local, global or hierarchical, not {kind!r}")
        text = self.text(data, "text", where)
        if not text:
            raise self.fail(f"{where}.text", "a label has a text")
        shape = self.shape(data, where, required=False)
        if kind == "local" and shape:
            raise self.fail(f"{where}.shape", "a local label has no shape")
        reference = None
        if "intersheet_refs" in data:
            if kind != "global":
                raise self.fail(f"{where}.intersheet_refs", "intersheet_refs belongs to a global label only")
            reference = self.fields({"fields": {"Intersheetrefs": data["intersheet_refs"]}}, where)[0]
        return DrawnLabel(
            kind,  # type: ignore[arg-type]
            text,
            self.point(data["at"], f"{where}.at"),
            self.angle(data, "rotation", where, ROTATIONS),
            shape,  # type: ignore[arg-type]
            self.font(data, where),
            self.justify(data, where) if "justify" in data else None,
            reference,
        )

    def sheet_ref(self, raw: object, where: str) -> DrawnSheetRef:
        data = self.table(raw, where, "sheet_ref", ("key", "sheet", "module", "name", "at", "size", "page"))
        key = self.text(data, "key", where)
        if not SHEET_KEY.fullmatch(key):
            raise self.fail(f"{where}.key", f"reference key {key!r} does not match {SHEET_KEY.pattern}")
        size = self.point(data["size"], f"{where}.size")
        if size.x <= 0 or size.y <= 0:
            raise self.fail(f"{where}.size", "a sheet reference has a positive size")
        module = self.text(data, "module", where)
        if module.startswith("/") or module.endswith("/") or "//" in module:
            raise self.fail(f"{where}.module", f"module {module!r} is a relative module path")
        name = self.text(data, "name", where)
        if not name:
            raise self.fail(f"{where}.name", "a sheet reference has a name")
        pins: list[DrawnPin] = []
        for at, item in self.items(data, "pin", where):
            table = self.table(item, at, "pin", ("name", "shape", "at"))
            pin_name = self.text(table, "name", at)
            if not pin_name:
                raise self.fail(f"{at}.name", "a sheet pin has a name")
            pins.append(
                DrawnPin(
                    pin_name,
                    self.shape(table, at, required=True),  # type: ignore[arg-type]
                    self.point(table["at"], f"{at}.at"),
                    self.angle(table, "rotation", at, ROTATIONS),
                    self.font(table, at),
                    self.justify(table, at) if "justify" in table else None,
                )
            )
        return DrawnSheetRef(
            key,
            self.text(data, "sheet", where),
            module,
            name,
            self.point(data["at"], f"{where}.at"),
            Size(size.x, size.y),
            self.text(data, "page", where),
            self.text(data, "file", where, ""),
            tuple(pins),
            self.fields(data, where, names=frozenset({"Sheetname", "Sheetfile"})),
            self.properties(data, where),
        )


def _one_expression(text: str) -> bool:
    """Whether ``text`` is one balanced S-expression ``( ... )`` with nothing but blanks around it."""
    stripped = text.strip()
    if not stripped.startswith("(") or not stripped.endswith(")"):
        return False
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(stripped):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and index != len(stripped) - 1:
                return False
            if depth < 0:
                return False
    return depth == 0 and not in_string


def read_drawn(text: str, *, file: str = "") -> DrawnSchematic:
    """The drawn schematic of a ``schematic.toml`` text; ``FormatError`` for anything outside the schema."""
    reader = _Reader(file)
    try:
        data = tomllib.loads(text, parse_float=Decimal)
    except tomllib.TOMLDecodeError as error:
        raise reader.fail("", f"not valid TOML: {error}") from error
    root = reader.table(data, "", "root", ("schema", "root", "sheet"))
    if not accepts_schema(root["schema"], SCHEMA):
        raise reader.fail("schema", f"schema is {SCHEMA!r}, not {root['schema']!r}")
    root_key = reader.text(root, "root", "")
    raw_sheets = root["sheet"]
    if not isinstance(raw_sheets, list) or not raw_sheets:
        raise reader.fail("sheet", "a drawn schematic holds one or more [[sheet]] tables")
    sheets: list[DrawnSheet] = []
    for index, raw in enumerate(cast(list[object], raw_sheets)):
        sheet = reader.sheet(raw, f"sheet[{index}]")
        if any(known.key == sheet.key for known in sheets):
            raise reader.fail(f"sheet[{index}].key", f"the sheet key {sheet.key!r} is used twice")
        sheets.append(sheet)
    if not any(sheet.key == root_key for sheet in sheets):
        raise reader.fail("root", f"root names {root_key!r}, which is no sheet of the file")
    return DrawnSchematic(root_key, tuple(sheets))


# --- writing ---------------------------------------------------------------------------------------


Writer = Callable[[DrawnSchematic], str]

__all__ = [
    "CLOSED_KEYS",
    "FILE_NAME",
    "HEADER",
    "SHAPES",
    "SHEET_KEY",
    "mm",
    "read_drawn",
    "write_drawn",
]
