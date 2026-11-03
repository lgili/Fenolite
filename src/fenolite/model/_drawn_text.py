# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Canonical drawn value text shared by the file lens and the pure importer (c0276)."""

from __future__ import annotations

import re
from collections.abc import Sequence

from fenolite.core.coords import Point
from fenolite.model.drawn import SCHEMA, DrawnField, DrawnFont, DrawnSchematic, DrawnSheet, DrawnSheetProperty

HEADER = "# Drawn schematic of a Fenolite design (docs/drawn-schematic.md). Code owns the nets."
_UDEG = 1_000_000
_BARE = re.compile(r"[A-Za-z0-9_-]+")


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


def _font(font: DrawnFont) -> str:
    parts: list[str] = []
    if font.size is not None:
        parts.append(f"size = [{mm(font.size.w)}, {mm(font.size.h)}]")
    if font.thickness is not None:
        parts.append(f"thickness = {mm(font.thickness)}")
    for name, value in (("bold", font.bold), ("italic", font.italic)):
        if value is not None:
            parts.append(f"{name} = {'true' if value else 'false'}")
    if font.face is not None:
        parts.append(f"face = {_string(font.face)}")
    return "{ " + ", ".join(parts) + " }"


def _field_parts(found: DrawnField) -> list[str]:
    parts = [f"at = {_point(found.at)}", f"rotation = {_deg(found.rotation)}"]
    if found.justify:
        parts.append(f"justify = {_string(found.justify)}")
    if found.hide:
        parts.append("hide = true")
    if found.font is not None:
        parts.append(f"font = {_font(found.font)}")
    return parts


def _fields(fields: Sequence[DrawnField]) -> list[str]:
    return [f"fields.{_key(found.name)} = {{ {', '.join(_field_parts(found))} }}" for found in fields]


def _properties(properties: Sequence[DrawnSheetProperty]) -> list[str]:
    lines: list[str] = []
    for prop in properties:
        parts = [f"text = {_string(prop.text)}", *_field_parts(prop.pose)]
        lines.append(f"properties.{_key(prop.name)} = {{ {', '.join(parts)} }}")
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
        if symbol.symbol:
            lines.append(f"symbol = {_string(symbol.symbol)}")
        blocks.append(_block("[[sheet.symbol]]", [*lines, *_fields(symbol.fields)]))
    for power in sheet.powers:
        lines = [
            f"symbol = {_string(power.symbol)}",
            f"net = {_string(power.net)}",
            f"at = {_point(power.at)}",
            f"rotation = {_deg(power.rotation)}",
        ]
        if power.mirror:
            lines.append(f"mirror = {_string(power.mirror)}")
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
        if label.font is not None:
            lines.append(f"font = {_font(label.font)}")
        if label.justify is not None:
            lines.append(f"justify = {_string(label.justify)}")
        if label.intersheet_refs is not None:
            lines.append("intersheet_refs = { " + ", ".join(_field_parts(label.intersheet_refs)) + " }")
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
        blocks.append(
            _block("[[sheet.sheet_ref]]", [*lines, *_fields(ref.fields), *_properties(ref.properties)])
        )
        for pin in ref.pins:
            lines = [
                f"name = {_string(pin.name)}",
                f"shape = {_string(pin.shape)}",
                f"at = {_point(pin.at)}",
                f"rotation = {_deg(pin.rotation)}",
            ]
            if pin.font is not None:
                lines.append(f"font = {_font(pin.font)}")
            if pin.justify is not None:
                lines.append(f"justify = {_string(pin.justify)}")
            blocks.append(_block("[[sheet.sheet_ref.pin]]", lines))
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
