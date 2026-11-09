# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The carrier of KiCad items in an Altium sheet (change c0470, design D4; capability design-conversion,
"Sheet carriers").

``Fenolite.KiCad.Sheet`` (schema ``fenolite.kicad-sheet.v0``) is a hidden document parameter: a root
parameter record (``RECORD=41`` without an owner), as the composition intent of change c0086 is. It holds
what no Altium record holds, in drawn order:

- ``opaques``: each KiCad item that the Altium writer cannot draw (a drawn opaque item without Altium text);
- ``powers``: each KiCad power flag (``PWR_FLAG``), which marks a net for ERC and names none, so no power
  port stands for it;
- ``stand_ins``: for each KiCad global label or power symbol that an Altium power port stands for, the
  ``UNIQUEID`` of that port and the KiCad attributes the port cannot hold (label kind and shape, power
  symbol, field poses, mirror). Field poses are relative to the item, so they move with the port; the net
  name and the position stay those of the port; ``{"pin": <net>}`` marks a port drawn at the end of a hidden
  KiCad power pin, which KiCad joins to the net its name gives and Altium joins by position only;
- ``symbols``: for each symbol, by ``<part>:<unit>``, its KiCad field poses relative to the symbol (an Altium
  component holds no ``Datasheet`` or ``Footprint`` text and no font size of its own) and the lib id of a unit
  drawn with another symbol than its component's, restored while the component keeps the turn and mirror
  it was written with;
- ``junctions``: each junction whose diameter is not the default, by position;
- ``labels``: each KiCad local or hierarchical label, by position (a later pass may rename a local label
  to keep its sheet scope; the written text tells two labels at one position apart): its kind, text, font
  and justification;
- ``sheet_refs``: each sheet symbol, by position: its field poses, custom properties and pin text styles;
- ``origin``: in the copy of a KiCad sheet that several instances show (Altium writes one sheet per
  instance, ``drawn.altium-repeat-flattened``), the key and file of that KiCad sheet and the part name of
  each designator of the copy, by which the way back folds the copies into one sheet again.

Its value is the canonical JSON of the carrier in base64, since a record value cannot hold ``|``
(``ascii.text_problem``) and the JSON of a KiCad item may. A record holds at most 65535 bytes, so a longer
value is cut into parts of ``PART_SIZE`` characters: the first named ``Fenolite.KiCad.Sheet``, the next
``Fenolite.KiCad.Sheet.2``, ``.3`` and so on (``part_name``, ``joined``).
"""

# evidence: see drawn, drawn_read

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, cast

from fenolite.core.coords import Point, Size
from fenolite.core.trig import QUARTER_TURN
from fenolite.model.drawn import (
    DrawnBusAlias,
    DrawnField,
    DrawnFont,
    DrawnJunction,
    DrawnLabel,
    DrawnPower,
    DrawnSheetProperty,
    DrawnSheetRef,
    DrawnSymbol,
)

NAME = "Fenolite.KiCad.Sheet"
POWER_FLAG = "PWR_FLAG"
"""The name of KiCad's power flag symbol, which marks a net for ERC and names none."""
SCHEMA = "fenolite.kicad-sheet.v0"
QUARTER = 90_000_000

Json = dict[str, Any]


def _font(font: DrawnFont | None) -> Json | None:
    if font is None:
        return None
    size = [font.size.w, font.size.h] if font.size is not None else None
    return {
        "size": size,
        "thickness": font.thickness,
        "bold": font.bold,
        "italic": font.italic,
        "face": font.face,
    }


def _font_of(value: Json | None) -> DrawnFont | None:
    if value is None:
        return None
    size = value["size"]
    return DrawnFont(
        Size(int(size[0]), int(size[1])) if size is not None else None,
        value["thickness"],
        value["bold"],
        value["italic"],
        value["face"],
    )


def _pose(item: DrawnField, origin: Point) -> Json:
    return {
        "name": item.name,
        "at": [item.at.x - origin.x, item.at.y - origin.y],
        "rotation": item.rotation,
        "justify": item.justify,
        "hide": item.hide,
        "font": _font(item.font),
    }


def _pose_of(value: Json, origin: Point) -> DrawnField:
    at = cast(list[int], value["at"])
    return DrawnField(
        str(value["name"]),
        Point(origin.x + int(at[0]), origin.y + int(at[1])),
        int(value["rotation"]),
        str(value["justify"]),
        bool(value["hide"]),
        _font_of(value["font"]),
    )


KICAD_SLASH = "{slash}"
"""How a KiCad sheet stores a ``/`` of a label, sheet pin or net text (``H-K-SCH-SLASH``)."""


def altium_text(text: str) -> str:
    """A KiCad label, sheet pin or power text as an Altium record writes it: a stored ``{slash}`` is ``/``.
    The carrier keeps the KiCad text."""
    return text.replace(KICAD_SLASH, "/")


def label_value(label: DrawnLabel) -> Json:
    """The attributes of ``label`` that a power port does not hold."""
    refs = _pose(label.intersheet_refs, label.at) if label.intersheet_refs is not None else None
    return {
        "kind": label.kind,
        "rotation": label.rotation,
        "shape": label.shape,
        "font": _font(label.font),
        "justify": label.justify,
        "intersheet_refs": refs,
    }


def power_value(power: DrawnPower) -> Json:
    """The attributes of ``power`` that a power port does not hold."""
    return {
        "symbol": power.symbol,
        "rotation": power.rotation,
        "mirror": power.mirror,
        "fields": [_pose(item, power.at) for item in power.fields],
    }


def _rotation(carried: int, read: int) -> int:
    """The carried rotation while the port keeps the quarter turn it was written with, else the read one."""
    return carried if carried // QUARTER % 4 == read // QUARTER % 4 else read


def label_of(value: Json, text: str, at: Point, rotation: int) -> DrawnLabel:
    """The KiCad label that a power port of net ``text`` at ``at`` and ``rotation`` stands for."""
    refs = value["intersheet_refs"]
    return DrawnLabel(
        value["kind"],
        str(value.get("text", text)),
        at,
        _rotation(int(value["rotation"]), rotation),
        value["shape"],
        _font_of(value["font"]),
        value["justify"],
        _pose_of(refs, at) if refs is not None else None,
    )


def power_of(value: Json, net: str, at: Point, rotation: int) -> DrawnPower:
    """The KiCad power symbol that a power port of net ``net`` at ``at`` and ``rotation`` stands for."""
    fields = tuple(_pose_of(item, at) for item in cast(list[Json], value["fields"]))
    return DrawnPower(
        str(value["symbol"]),
        str(value.get("net", net)),
        at,
        _rotation(int(value["rotation"]), rotation),
        fields,
        str(value["mirror"]),
    )


def flag_value(power: DrawnPower) -> Json:
    """A power flag, carried whole: its net name and position too."""
    return {**power_value(power), "net": power.net, "at": [power.at.x, power.at.y]}


def flag_of(value: Json) -> DrawnPower:
    at = cast(list[int], value["at"])
    point = Point(int(at[0]), int(at[1]))
    return replace(power_of(value, str(value["net"]), point, int(value["rotation"])), at=point)


@dataclass(frozen=True, slots=True)
class KiCadSheet:
    """The KiCad items of one sheet that no Altium record holds (module docstring)."""

    opaques: tuple[str, ...] = ()
    powers: tuple[Json, ...] = ()
    stand_ins: Mapping[str, Json] = field(default_factory=lambda: {})
    symbols: Mapping[str, Json] = field(default_factory=lambda: {})
    junctions: tuple[Json, ...] = ()
    labels: tuple[Json, ...] = ()
    sheet_refs: tuple[Json, ...] = ()
    origin: Json | None = None
    exact: tuple[tuple[int, int], ...] = ()
    """Each written Altium coordinate (fraction units, measured from the top for Y) that a KiCad length off
    the 127/50 nm step was rounded to, and that length in nm."""
    generated: Json | None = None
    """The items of the harness blocks the writer drew for KiCad bus groups (``drawn_harness``), in nm:
    ``wires`` and ``lines`` by their points, ``labels`` by text and point, ``connectors`` by their corner.
    The reader drops them."""
    definitions: Mapping[str, str] = field(default_factory=lambda: {})
    """The KiCad library text (``.kicad_sym``) of each carried opaque symbol's definition, by its lib id:
    the sheet's ``lib_symbols`` entry, which no Altium record holds."""
    bus_aliases: tuple[DrawnBusAlias, ...] = ()

    def text(self) -> str:
        """The canonical JSON of the carrier: sorted keys, no spaces, UTF-8 kept."""
        value = {
            "schema": SCHEMA,
            "opaques": [{"kicad": text} for text in self.opaques],
            "powers": list(self.powers),
            "stand_ins": dict(sorted(self.stand_ins.items())),
            "symbols": dict(sorted(self.symbols.items())),
            "junctions": list(self.junctions),
            "labels": list(self.labels),
            "sheet_refs": list(self.sheet_refs),
        }
        if self.origin is not None:
            value["origin"] = self.origin
        if self.generated:
            value["generated"] = self.generated
        if self.definitions:
            value["definitions"] = [{"lib_id": k, "text": v} for k, v in sorted(self.definitions.items())]
        if self.exact:
            value["exact"] = [{"at": at, "nm": nm} for at, nm in self.exact]
        if self.bus_aliases:
            value["bus_aliases"] = [{"name": a.name, "members": list(a.members)} for a in self.bus_aliases]
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def value(self) -> str:
        """The parameter value: the canonical JSON in base64."""
        return base64.b64encode(self.text().encode("utf-8")).decode("ascii")

    @classmethod
    def parse(cls, value: str) -> KiCadSheet:
        """The carrier of the parameter ``value``; ``ValueError`` when it is not one of this schema."""
        try:
            loaded: object = json.loads(base64.b64decode(value.encode("ascii"), validate=True))
        except (binascii.Error, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"not a {SCHEMA} carrier: {error}") from None
        if not isinstance(loaded, dict) or cast(Json, loaded).get("schema") != SCHEMA:
            raise ValueError(f"not a {SCHEMA} carrier")
        found = cast(Json, loaded)
        items = cast(list[Json], found["opaques"])
        return cls(
            tuple(str(item["kicad"]) for item in items),
            tuple(cast(list[Json], found["powers"])),
            dict(cast(Json, found["stand_ins"])),
            dict(cast(Json, found.get("symbols", {}))),
            tuple(cast(list[Json], found.get("junctions", []))),
            tuple(cast(list[Json], found.get("labels", []))),
            tuple(cast(list[Json], found.get("sheet_refs", []))),
            cast("Json | None", found.get("origin")),
            tuple((int(pair["at"]), int(pair["nm"])) for pair in cast(list[Json], found.get("exact", []))),
            cast("Json | None", found.get("generated")),
            {str(d["lib_id"]): str(d["text"]) for d in cast(list[Json], found.get("definitions", []))},
            tuple(
                DrawnBusAlias(str(a["name"]), tuple(str(m) for m in cast(list[object], a["members"])))
                for a in cast(list[Json], found.get("bus_aliases", []))
            ),
        )


def carrier(
    opaques: Sequence[str],
    powers: Sequence[Json] = (),
    stand_ins: Mapping[str, Json] | None = None,
    symbols: Mapping[str, Json] | None = None,
    junctions: Sequence[Json] = (),
    labels: Sequence[Json] = (),
    sheet_refs: Sequence[Json] = (),
    origin: Json | None = None,
    exact: Mapping[int, int] | None = None,
    generated: Json | None = None,
    definitions: Mapping[str, str] | None = None,
    bus_aliases: Sequence[DrawnBusAlias] = (),
) -> KiCadSheet | None:
    """The carrier of a sheet's KiCad items, or ``None`` when there is none."""
    if not (
        opaques
        or powers
        or stand_ins
        or symbols
        or junctions
        or labels
        or sheet_refs
        or origin
        or exact
        or generated
        or definitions
        or bus_aliases
    ):
        return None
    return KiCadSheet(
        tuple(opaques),
        tuple(powers),
        dict(stand_ins or {}),
        dict(symbols or {}),
        tuple(junctions),
        tuple(labels),
        tuple(sheet_refs),
        origin,
        tuple(sorted((exact or {}).items())),
        generated or None,
        dict(definitions or {}),
        tuple(bus_aliases),
    )


def origin_value(sheet: str, file: str, parts: Mapping[str, str]) -> Json:
    """The KiCad sheet ``sheet`` (in ``file``) that more than one instance shows, of which this Altium sheet
    is one instance's copy, and the part name of each of its designators there."""
    return {"sheet": sheet, "file": file, "parts": dict(sorted(parts.items()))}


def written_label(label: DrawnLabel, other: Point | None = None) -> Json:
    """A label written as a net label or a port: its position, the text written (``altium_text``), the
    other hot end of a port (``other``) and the label itself."""
    value: Json = {
        "at": [label.at.x, label.at.y],
        "written": altium_text(label.text),
        "label": {**label_value(label)},
    }
    value["label"]["text"] = label.text
    if other is not None:
        value["other"] = [other.x, other.y]
    return value


def labels_of(values: Sequence[Json], labels: Sequence[DrawnLabel]) -> list[DrawnLabel]:
    """``labels`` with the carried label restored at each position that holds one (its own, or the other
    hot end of the port it was written as); where several are, the one written with the text read, then
    the one carried at that position with the rotation read. Each carried label is restored once."""
    by_place: dict[tuple[int, int], list[int]] = {}
    for index, value in enumerate(values):
        for key in ("at", "other"):
            if key in value:
                by_place.setdefault((int(value[key][0]), int(value[key][1])), []).append(index)
    used: set[int] = set()
    out: list[DrawnLabel] = []
    for label in labels:
        found = by_place.get((label.at.x, label.at.y), [])
        if len(found) > 1:
            found = [i for i in found if str(values[i]["written"]) == label.text]
        found = [i for i in found if i not in used]
        if len(found) > 1:
            found = [i for i in found if _carried_at(values[i], label)] or found
        if len(found) != 1:
            out.append(label)
            continue
        used.add(found[0])
        chosen = values[found[0]]
        value = cast(Json, chosen["label"])
        at = Point(int(chosen["at"][0]), int(chosen["at"][1]))
        out.append(label_of(value, str(value["text"]), at, int(value["rotation"])))
    return out


def _carried_at(value: Json, label: DrawnLabel) -> bool:
    """Whether ``value`` was carried at the position of ``label`` with the rotation it is read with."""
    at = cast(list[Any], value["at"])
    carried = cast(Json, value["label"])
    return (int(at[0]), int(at[1])) == (label.at.x, label.at.y) and int(carried["rotation"]) == label.rotation


PART_SIZE = 60_000
"""The characters of the carrier value in one parameter record, under the 65535 bytes of a record."""


def part_name(index: int) -> str:
    """The parameter name of part ``index`` (from 0) of a carrier value."""
    return NAME if index == 0 else f"{NAME}.{index + 1}"


def part_index(name: str) -> int | None:
    """The index of the carrier part named ``name``, or ``None`` when it names none."""
    if name == NAME:
        return 0
    head, dot, number = name.rpartition(".")
    if head == NAME and dot and number.isdigit() and int(number) >= 2 and number == str(int(number)):
        return int(number) - 1
    return None


def parts(value: str) -> list[str]:
    """``value`` cut into parts of ``PART_SIZE`` characters."""
    return [value[i : i + PART_SIZE] for i in range(0, len(value), PART_SIZE)] or [""]


def joined(found: Mapping[int, str]) -> str:
    """The carrier value of the parts ``found`` by index; ``ValueError`` when one is missing."""
    if sorted(found) != list(range(len(found))):
        raise ValueError(f"the parts of {NAME} are not numbered 1 to {len(found)}")
    return "".join(found[index] for index in range(len(found)))


def _property(item: DrawnSheetProperty, origin: Point) -> Json:
    pose = DrawnField(item.name, item.at, item.rotation, item.justify, item.hide, item.font)
    return {**_pose(pose, origin), "text": item.text}


def _property_of(value: Json, origin: Point) -> DrawnSheetProperty:
    pose = _pose_of(value, origin)
    return DrawnSheetProperty(
        pose.name, str(value["text"]), pose.at, pose.rotation, pose.justify, pose.hide, pose.font
    )


def sheet_ref_value(ref: DrawnSheetRef) -> Json:
    """The attributes of a sheet symbol that its Altium records do not hold."""
    return {
        "at": [ref.at.x, ref.at.y],
        "fields": [_pose(item, ref.at) for item in ref.fields],
        "properties": [_property(item, ref.at) for item in ref.properties],
        "pins": [
            {"font": _font(pin.font), "justify": pin.justify, "shape": pin.shape, "name": pin.name}
            for pin in ref.pins
        ],
    }


def sheet_refs_of(values: Sequence[Json], refs: Sequence[DrawnSheetRef]) -> list[DrawnSheetRef]:
    """``refs`` with the carried attributes of each sheet symbol still at its position."""
    by_place = {(int(v["at"][0]), int(v["at"][1])): v for v in values}
    out: list[DrawnSheetRef] = []
    for ref in refs:
        value = by_place.get((ref.at.x, ref.at.y))
        if value is None:
            out.append(ref)
            continue
        styles = cast(list[Json], value["pins"])
        pins = tuple(
            replace(
                pin,
                font=_font_of(styles[i]["font"]),
                justify=styles[i]["justify"],
                shape=styles[i].get("shape", pin.shape),
                name=str(styles[i].get("name", pin.name)),
            )
            if i < len(styles)
            else pin
            for i, pin in enumerate(ref.pins)
        )
        fields = tuple(_pose_of(item, ref.at) for item in cast(list[Json], value["fields"]))
        properties = tuple(_property_of(item, ref.at) for item in cast(list[Json], value["properties"]))
        out.append(replace(ref, fields=fields, properties=properties, pins=pins))
    return out


def symbol_key(symbol: DrawnSymbol) -> str:
    return f"{symbol.part.rpartition('/')[2]}:{symbol.unit}"


def symbol_value(symbol: DrawnSymbol) -> Json:
    """The field poses of ``symbol``, relative to it, with the turn and mirror it is written with."""
    value: Json = {
        "rotation": symbol.rotation,
        "mirror": symbol.mirror,
        "fields": [_pose(item, symbol.at) for item in symbol.fields],
    }
    if symbol.symbol:
        value["symbol"] = symbol.symbol  # the lib id of a unit drawn with another symbol than its component's
    return value


def symbol_of(value: Json, symbol: DrawnSymbol) -> DrawnSymbol:
    """``symbol`` with the carried field poses, while it keeps the turn and mirror they were written with."""
    rotation, mirror = int(value["rotation"]), str(value["mirror"])
    if _turn(rotation, mirror) != _turn(symbol.rotation, symbol.mirror):
        return symbol
    fields = tuple(_pose_of(item, symbol.at) for item in cast(list[Json], value["fields"]))
    alias = str(value.get("symbol", symbol.symbol))
    return replace(symbol, rotation=rotation, mirror=mirror, fields=fields, symbol=alias)


def _turn(rotation: int, mirror: str) -> tuple[int, str]:
    """A mirror about X is the mirror about Y and a half turn (Altium writes one flag, ``ISMIRRORED``)."""
    full = 4 * QUARTER_TURN
    if mirror == "x":
        return (rotation + 2 * QUARTER_TURN) % full, "y"
    return rotation % full, mirror


def junction_value(junction: DrawnJunction) -> Json:
    return {"at": [junction.at.x, junction.at.y], "diameter": junction.diameter}


def junctions_of(values: Sequence[Json], junctions: Sequence[DrawnJunction]) -> list[DrawnJunction]:
    """``junctions`` with the carried diameter of each one still at its position."""
    sizes = {(int(v["at"][0]), int(v["at"][1])): int(v["diameter"]) for v in values}
    return [
        replace(j, diameter=sizes[(j.at.x, j.at.y)]) if (j.at.x, j.at.y) in sizes else j for j in junctions
    ]


__all__ = [
    "NAME",
    "POWER_FLAG",
    "SCHEMA",
    "KICAD_SLASH",
    "KiCadSheet",
    "carrier",
    "altium_text",
    "flag_of",
    "flag_value",
    "junction_value",
    "joined",
    "junctions_of",
    "labels_of",
    "part_index",
    "part_name",
    "origin_value",
    "parts",
    "sheet_ref_value",
    "sheet_refs_of",
    "written_label",
    "label_of",
    "label_value",
    "power_of",
    "power_value",
    "symbol_key",
    "symbol_of",
    "symbol_value",
]
