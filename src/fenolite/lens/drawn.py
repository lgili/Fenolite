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
from fenolite.model.presentation import PaperSize
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
    DrawnJunction,
    DrawnLabel,
    DrawnOpaque,
    DrawnPin,
    DrawnPower,
    DrawnSchematic,
    DrawnSheet,
    DrawnSheetRef,
    DrawnSymbol,
)

FILE_NAME = "schematic.toml"
HEADER = "# Drawn schematic of a Fenolite design (docs/drawn-schematic.md). Code owns the nets."
ROOT_KEYS: tuple[str, ...] = ("schema", "root", "sheet")
SHEET_KEYS: tuple[str, ...] = (
    "key", "paper", "title_block", "generated", "symbol", "power", "wire", "bus", "bus_entry", "junction",
    "no_connect", "label", "bus_alias", "sheet_ref", "opaque",
)  # fmt: skip
SYMBOL_KEYS: tuple[str, ...] = ("part", "unit", "at", "rotation", "mirror", "fields")
FIELD_KEYS: tuple[str, ...] = ("at", "rotation", "justify", "hide")
POWER_KEYS: tuple[str, ...] = ("symbol", "net", "at", "rotation", "fields")
POLYLINE_KEYS: tuple[str, ...] = ("pts",)
BUS_ENTRY_KEYS: tuple[str, ...] = ("at", "size")
JUNCTION_KEYS: tuple[str, ...] = ("at", "diameter")
NO_CONNECT_KEYS: tuple[str, ...] = ("at",)
LABEL_KEYS: tuple[str, ...] = ("kind", "text", "at", "rotation", "shape")
BUS_ALIAS_KEYS: tuple[str, ...] = ("name", "members")
SHEET_REF_KEYS: tuple[str, ...] = ("key", "sheet", "module", "name", "file", "at", "size", "page", "pin")
PIN_KEYS: tuple[str, ...] = ("name", "shape", "at", "rotation")
OPAQUE_KEYS: tuple[str, ...] = ("kicad", "altium")
TITLE_KEYS: tuple[str, ...] = (*TITLE_FIELDS, "params")
CLOSED_KEYS: Mapping[str, tuple[str, ...]] = {
    "root": ROOT_KEYS,
    "sheet": SHEET_KEYS,
    "title_block": TITLE_KEYS,
    "symbol": SYMBOL_KEYS,
    "field": FIELD_KEYS,
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
_NM = Decimal(1_000_000)
_UDEG = 1_000_000
_BARE = re.compile(r"[A-Za-z0-9_-]+")

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
        scaled = Decimal(value) * _NM
        if not scaled.is_finite() or scaled != scaled.to_integral_value():
            raise self.fail(where, f"{value} mm is not a whole number of nanometres")
        return int(scaled)

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

    def fields(self, data: Table, where: str) -> tuple[DrawnField, ...]:
        value = data.get("fields", {})
        if not isinstance(value, dict):
            raise self.fail(f"{where}.fields", "fields is a table of field poses")
        found: list[DrawnField] = []
        for name, raw in cast(dict[str, object], value).items():
            at = f"{where}.fields.{name}"
            pose = self.table(raw, at, "field", ("at",))
            justify = self.text(pose, "justify", at, "")
            if any(word not in JUSTIFY_WORDS for word in justify.split()) or justify != " ".join(
                justify.split()
            ):
                raise self.fail(f"{at}.justify", f"justify {justify!r} is words of {sorted(JUSTIFY_WORDS)}")
            found.append(
                DrawnField(
                    name,
                    self.point(pose["at"], f"{at}.at"),
                    self.angle(pose, "rotation", at, FIELD_ROTATIONS),
                    justify,
                    self.boolean(pose, "hide", at),
                )
            )
        return tuple(found)

    def polyline(self, raw: object, where: str, kind: str) -> tuple[Point, ...]:
        data = self.table(raw, where, kind, ("pts",))
        points = data["pts"]
        if not isinstance(points, list) or len(cast(list[object], points)) < 2:
            raise self.fail(f"{where}.pts", f"a {kind} has two or more points")
        return tuple(self.point(p, f"{where}.pts[{i}]") for i, p in enumerate(cast(list[object], points)))

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
            if not _one_expression(text):
                raise self.fail(f"{at}.kicad", "an opaque item holds one KiCad S-expression")
            opaques.append(DrawnOpaque(text, self.text(table, "altium", at, "")))
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
        )

    def power(self, raw: object, where: str) -> DrawnPower:
        data = self.table(raw, where, "power", ("symbol", "net", "at"))
        symbol, net = self.text(data, "symbol", where), self.text(data, "net", where)
        if not symbol or not net:
            raise self.fail(where, "a power symbol names its library symbol and its net")
        return DrawnPower(
            symbol,
            net,
            self.point(data["at"], f"{where}.at"),
            self.angle(data, "rotation", where, ROTATIONS),
            self.fields(data, where),
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
        return DrawnLabel(
            kind,  # type: ignore[arg-type]
            text,
            self.point(data["at"], f"{where}.at"),
            self.angle(data, "rotation", where, ROTATIONS),
            shape,  # type: ignore[arg-type]
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
    if root["schema"] != SCHEMA:
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


def mm(nm: int) -> str:
    """The shortest exact decimal of ``nm`` nanometres in millimetres."""
    sign = "-" if nm < 0 else ""
    whole, frac = divmod(abs(nm), 1_000_000)
    if not frac:
        return f"{sign}{whole}"
    return f"{sign}{whole}.{f'{frac:06d}'.rstrip('0')}"


def _string(text: str) -> str:
    out = ['"']
    for char in text:
        if char == '"':
            out.append('\\"')
        elif char == "\\":
            out.append("\\\\")
        elif char == "\n":
            out.append("\\n")
        elif char == "\t":
            out.append("\\t")
        elif char == "\r":
            out.append("\\r")
        elif ord(char) < 0x20 or ord(char) == 0x7F:
            out.append(f"\\u{ord(char):04x}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _key(text: str) -> str:
    return text if _BARE.fullmatch(text) else _string(text)


def _point(point: Point) -> str:
    return f"[{mm(point.x)}, {mm(point.y)}]"


def _deg(udeg: int) -> str:
    return str(udeg // _UDEG)


def _fields(fields: Sequence[DrawnField]) -> list[str]:
    lines: list[str] = []
    for found in fields:
        parts = [f"at = {_point(found.at)}", f"rotation = {_deg(found.rotation)}"]
        if found.justify:
            parts.append(f"justify = {_string(found.justify)}")
        if found.hide:
            parts.append("hide = true")
        lines.append(f"fields.{_key(found.name)} = {{ {', '.join(parts)} }}")
    return lines


def _block(header: str, lines: Sequence[str]) -> str:
    return "\n".join((header, *lines))


def _sheet_blocks(sheet: DrawnSheet) -> list[str]:
    head = [f"key = {_string(sheet.key)}", f"paper = {_string(sheet.paper)}"]
    if sheet.generated:
        head.append("generated = true")
    blocks = [_block("[[sheet]]", head)]
    if sheet.title_block:
        texts = [f"{k} = {_string(v)}" for k, v in sheet.title_block if not k.startswith("param.")]
        params = [(k.removeprefix("param."), v) for k, v in sheet.title_block if k.startswith("param.")]
        if params:
            texts.append("params = { " + ", ".join(f"{_key(k)} = {_string(v)}" for k, v in params) + " }")
        blocks.append(_block("[sheet.title_block]", texts))
    for symbol in sheet.symbols:
        lines = [
            f"part = {_string(symbol.part)}",
            f"unit = {symbol.unit}",
            f"at = {_point(symbol.at)}",
            f"rotation = {_deg(symbol.rotation)}",
        ]
        if symbol.mirror:
            lines.append(f"mirror = {_string(symbol.mirror)}")
        blocks.append(_block("[[sheet.symbol]]", [*lines, *_fields(symbol.fields)]))
    for power in sheet.powers:
        lines = [
            f"symbol = {_string(power.symbol)}",
            f"net = {_string(power.net)}",
            f"at = {_point(power.at)}",
            f"rotation = {_deg(power.rotation)}",
        ]
        blocks.append(_block("[[sheet.power]]", [*lines, *_fields(power.fields)]))
    for kind, polylines in (("wire", sheet.wires), ("bus", sheet.buses)):
        for polyline in polylines:
            points = ", ".join(_point(p) for p in polyline)
            blocks.append(_block(f"[[sheet.{kind}]]", [f"pts = [{points}]"]))
    for entry in sheet.bus_entries:
        blocks.append(
            _block("[[sheet.bus_entry]]", [f"at = {_point(entry.at)}", f"size = {_point(entry.size)}"])
        )
    for junction in sheet.junctions:
        lines = [f"at = {_point(junction.at)}"]
        if junction.diameter:
            lines.append(f"diameter = {mm(junction.diameter)}")
        blocks.append(_block("[[sheet.junction]]", lines))
    for flag in sheet.no_connects:
        blocks.append(_block("[[sheet.no_connect]]", [f"at = {_point(flag)}"]))
    for label in sheet.labels:
        lines = [
            f"kind = {_string(label.kind)}",
            f"text = {_string(label.text)}",
            f"at = {_point(label.at)}",
            f"rotation = {_deg(label.rotation)}",
        ]
        if label.shape:
            lines.append(f"shape = {_string(label.shape)}")
        blocks.append(_block("[[sheet.label]]", lines))
    for alias in sheet.bus_aliases:
        members = ", ".join(_string(m) for m in alias.members)
        blocks.append(
            _block("[[sheet.bus_alias]]", [f"name = {_string(alias.name)}", f"members = [{members}]"])
        )
    for ref in sheet.sheet_refs:
        lines = [
            f"key = {_string(ref.key)}",
            f"sheet = {_string(ref.sheet)}",
            f"module = {_string(ref.module)}",
            f"name = {_string(ref.name)}",
        ]
        if ref.file:
            lines.append(f"file = {_string(ref.file)}")
        lines += [
            f"at = {_point(ref.at)}",
            f"size = [{mm(ref.size.w)}, {mm(ref.size.h)}]",
            f"page = {_string(ref.page)}",
        ]
        blocks.append(_block("[[sheet.sheet_ref]]", lines))
        for pin in ref.pins:
            blocks.append(
                _block(
                    "[[sheet.sheet_ref.pin]]",
                    [
                        f"name = {_string(pin.name)}",
                        f"shape = {_string(pin.shape)}",
                        f"at = {_point(pin.at)}",
                        f"rotation = {_deg(pin.rotation)}",
                    ],
                )
            )
    for opaque in sheet.opaques:
        lines = [f"kicad = {_string(opaque.kicad)}"]
        if opaque.altium:
            lines.append(f"altium = {_string(opaque.altium)}")
        blocks.append(_block("[[sheet.opaque]]", lines))
    return blocks


def _page_order(drawn: DrawnSchematic) -> list[DrawnSheet]:
    """The sheets in page order: the root, then each sheet at its first instance, then the sheets that no
    instance reaches in file order."""
    order: list[str] = []
    for _module, key in drawn.instances():
        if key not in order:
            order.append(key)
    order += [sheet.key for sheet in drawn.sheets if sheet.key not in order]
    by_key = {sheet.key: sheet for sheet in drawn.sheets}
    return [by_key[key] for key in order]


def write_drawn(drawn: DrawnSchematic) -> str:
    """The canonical text of ``drawn``: the header comment, the root keys, then the sheets in page order,
    each key in the order of ``CLOSED_KEYS`` and the items in their order; numbers are the shortest exact
    decimals of millimetres and whole degrees. The text ends with a newline."""
    blocks = [_block(HEADER, [f"schema = {_string(SCHEMA)}", f"root = {_string(drawn.root)}"])]
    for sheet in _page_order(drawn):
        blocks += _sheet_blocks(sheet)
    return "\n\n".join(blocks) + "\n"


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
