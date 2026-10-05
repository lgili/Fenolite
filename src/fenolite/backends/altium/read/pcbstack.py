# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board record of a PCB document (``Board6/Data``) or library (``Library/Data``) and its layer stack
(``docs/formats/altium/pcb-read.md``, "Keys"; change c0041).

Two stack views are given and not merged: the numbered keys ``LAYER<i>…`` with the copper chain that
``LAYER<i>NEXT`` links from layer 1, and the physical list ``V9_STACK_LAYER<i>_…``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType

from fenolite.backends.altium.read.pcbprops import (
    PropertyRecord,
    issue,
    parse_angle,
    parse_bool,
    parse_int,
    parse_mil,
)
from fenolite.core.errors import Issue


def _layer_names() -> dict[int, str]:
    names: dict[int, str] = {1: "Top Layer"}
    names.update({i: f"Mid-Layer {i - 1}" for i in range(2, 32)})
    names[32] = "Bottom Layer"
    for i, name in enumerate(
        ("Top Overlay", "Bottom Overlay", "Top Paste", "Bottom Paste", "Top Solder"), 33
    ):
        names[i] = name
    names[38] = "Bottom Solder"
    names.update({i: f"Internal Plane {i - 38}" for i in range(39, 55)})
    names.update({55: "Drill Guide", 56: "Keep-Out Layer"})
    names.update({i: f"Mechanical {i - 56}" for i in range(57, 73)})
    names.update({73: "Drill Drawing", 74: "Multi-Layer"})
    return names


LAYER_NAMES: Mapping[int, str] = MappingProxyType(_layer_names())
"""Layer id → name for the ids 1 to 74 (``pcb-records.md``, "Layers")."""
TOP, BOTTOM, FIRST_PLANE, LAST_PLANE = 1, 32, 39, 54
NO_NET = "(No Net)"
_LONG_KINDS = {0x0100: "signal", 0x0101: "plane", 0x0102: "mechanical", 0x0103: "other", 0x0104: "dielectric"}
_BOTTOM_LONG = 0x0100FFFF
_STACK_KEY = re.compile(r"V9_STACK_LAYER(\d+)_(.*)", re.IGNORECASE)
_PLANE_KEY = re.compile(r"PLANE(\d+)NETNAME", re.IGNORECASE)


def long_layer_id(value: int | str) -> tuple[str, int]:
    """The kind (``signal``, ``plane``, ``mechanical``, ``other``, ``dielectric``) and number of a long
    layer id (``pcb-library.md``, "Long layer ids"). The bottom layer ``0x0100FFFF`` is signal 32, the
    id of the bottom copper layer; an id of no known group is ``("unknown", value)``."""
    number = int(value)
    if number == _BOTTOM_LONG:
        return "signal", BOTTOM
    kind = _LONG_KINDS.get(number >> 16)
    return ("unknown", number) if kind is None else (kind, number & 0xFFFF)


@dataclass(frozen=True, slots=True)
class OutlineVertex:
    """One vertex of the board outline or of a polygon: ``KIND`` 0 a line, else an arc. Lengths in units
    (exact fractions of the mil text), angles in degrees; a missing arc key reads as zero."""

    kind: int
    x: Fraction
    y: Fraction
    cx: Fraction
    cy: Fraction
    start_angle: float
    end_angle: float
    radius: Fraction


@dataclass(frozen=True, slots=True)
class NumberedLayer:
    """The keys ``LAYER<id>…`` of one numbered layer; thickness and dielectric texts are kept as text."""

    id: int
    name: str
    prev: int | None
    next: int | None
    mech_enabled: bool | None
    copper_thickness: str | None
    diel_type: str | None
    diel_const: str | None
    diel_height: str | None
    diel_material: str | None


@dataclass(frozen=True, slots=True)
class StackLayer:
    """One entry ``V9_STACK_LAYER<index>_…`` of the physical stack; ``fields`` holds every key of the entry
    without its prefix, in order."""

    index: int
    name: str | None
    layer_id: int | None
    kind: str | None
    number: int | None
    copper_thickness: str | None
    diel_type: str | None
    diel_const: str | None
    diel_height: str | None
    diel_material: str | None
    fields: tuple[tuple[str, str], ...]

    def get(self, key: str) -> str | None:
        wanted = key.upper()
        return next((value for name, value in self.fields if name.upper() == wanted), None)


@dataclass(frozen=True, slots=True)
class BoardRecord:
    """The board record with typed views; ``record`` keeps every field and the bytes."""

    record: PropertyRecord
    kind: str | None
    version: str | None
    filename: str | None
    origin: tuple[Fraction, Fraction] | None
    display_unit: int | None
    outline: tuple[OutlineVertex, ...]
    layers: tuple[NumberedLayer, ...]
    copper_chain: tuple[int, ...]
    stack: tuple[StackLayer, ...]
    plane_nets: Mapping[int, str]
    layer_pairs: tuple[tuple[str, str], ...]

    @property
    def raw(self) -> bytes:
        return self.record.raw

    @property
    def fields(self) -> tuple[tuple[str, str], ...]:
        return self.record.fields


class KeyReader:
    """Typed reads of one record that report each typed key whose text does not parse."""

    def __init__(self, record: PropertyRecord, where: str) -> None:
        self.record = record
        self.where = where
        self.issues: list[Issue] = []

    def _bad(self, key: str) -> None:
        self.issues.append(
            issue(
                "altium.pcb-read.bad-value",
                f"the value of {key} does not parse; its view is None",
                self.where,
            )
        )

    def int(self, key: str) -> int | None:
        text = self.record.get(key)
        value = parse_int(text)
        if text is not None and value is None:
            self._bad(key)
        return value

    def mil(self, key: str, default: Fraction | None = None) -> Fraction | None:
        text = self.record.get(key)
        if text is None:
            return default
        value = parse_mil(text)
        if value is None:
            self._bad(key)
        return value

    def angle(self, key: str, default: float | None = None) -> float | None:
        text = self.record.get(key)
        if text is None:
            return default
        value = parse_angle(text)
        if value is None:
            self._bad(key)
        return value

    def bool(self, key: str) -> bool | None:
        text = self.record.get(key)
        value = parse_bool(text)
        if text is not None and value is None:
            self._bad(key)
        return value


def read_outline(values: KeyReader) -> tuple[OutlineVertex, ...]:
    """The vertices ``KIND<k>``, ``VX<k>`` … from k = 0 until the first missing ``VX<k>``."""
    out: list[OutlineVertex] = []
    zero = Fraction(0)
    k = 0
    while values.record.get(f"VX{k}") is not None:
        out.append(
            OutlineVertex(
                kind=values.int(f"KIND{k}") or 0,
                x=values.mil(f"VX{k}") or zero,
                y=values.mil(f"VY{k}", zero) or zero,
                cx=values.mil(f"CX{k}", zero) or zero,
                cy=values.mil(f"CY{k}", zero) or zero,
                start_angle=values.angle(f"SA{k}", 0.0) or 0.0,
                end_angle=values.angle(f"EA{k}", 0.0) or 0.0,
                radius=values.mil(f"R{k}", zero) or zero,
            )
        )
        k += 1
    return tuple(out)


def _layers(values: KeyReader) -> tuple[NumberedLayer, ...]:
    record = values.record
    out: list[NumberedLayer] = []
    i = 1
    while (name := record.get(f"LAYER{i}NAME")) is not None:
        out.append(
            NumberedLayer(
                id=i,
                name=name,
                prev=values.int(f"LAYER{i}PREV"),
                next=values.int(f"LAYER{i}NEXT"),
                mech_enabled=values.bool(f"LAYER{i}MECHENABLED"),
                copper_thickness=record.get(f"LAYER{i}COPTHICK"),
                diel_type=record.get(f"LAYER{i}DIELTYPE"),
                diel_const=record.get(f"LAYER{i}DIELCONST"),
                diel_height=record.get(f"LAYER{i}DIELHEIGHT"),
                diel_material=record.get(f"LAYER{i}DIELMATERIAL"),
            )
        )
        i += 1
    return tuple(out)


def _chain(layers: tuple[NumberedLayer, ...], where: str) -> tuple[tuple[int, ...], list[Issue]]:
    """The copper layers from layer 1 following ``NEXT`` until 0; a link to a layer without a name, or a
    loop, ends the chain with one ``bad-stack`` error."""
    by_id = {layer.id: layer for layer in layers}
    if TOP not in by_id:
        return (), []
    chain = [TOP]
    while True:
        following = by_id[chain[-1]].next
        if not following:
            return tuple(chain), []
        if following in chain or following not in by_id:
            reason = (
                "returns to a layer of the chain" if following in chain else "names a layer without a name"
            )
            return tuple(chain), [
                issue(
                    "altium.pcb-read.bad-stack",
                    f"the copper chain from layer 1 {reason} (layer {following}) after {len(chain)} layers",
                    where,
                )
            ]
        chain.append(following)


def _stack(record: PropertyRecord) -> tuple[StackLayer, ...]:
    entries: dict[int, list[tuple[str, str]]] = {}
    for key, value in record.fields:
        match = _STACK_KEY.fullmatch(key)
        if match:
            entries.setdefault(int(match.group(1)), []).append((match.group(2), value))
    out: list[StackLayer] = []
    for index in sorted(entries):
        items = tuple(entries[index])

        def get(key: str, items: tuple[tuple[str, str], ...] = items) -> str | None:
            return next((v for k, v in items if k.upper() == key), None)

        long = parse_int(get("LAYERID"))
        kind, number = long_layer_id(long) if long is not None else (None, None)
        out.append(
            StackLayer(
                index=index,
                name=get("NAME"),
                layer_id=long,
                kind=kind,
                number=number,
                copper_thickness=get("COPTHICK"),
                diel_type=get("DIELTYPE"),
                diel_const=get("DIELCONST"),
                diel_height=get("DIELHEIGHT"),
                diel_material=get("DIELMATERIAL"),
                fields=items,
            )
        )
    return tuple(out)


def _planes(record: PropertyRecord) -> dict[int, str]:
    out: dict[int, str] = {}
    for key, _ in record.fields:
        match = _PLANE_KEY.fullmatch(key)
        if match and int(match.group(1)) not in out:
            name = record.get(key)
            if name is not None and name != NO_NET:
                out[int(match.group(1))] = name
    return out


def _pairs(record: PropertyRecord) -> tuple[tuple[str, str], ...]:
    out: list[tuple[str, str]] = []
    i = 0
    while (low := record.get(f"LAYERPAIR{i}LOW")) is not None:
        out.append((low, record.text(f"LAYERPAIR{i}HIGH")))
        i += 1
    return tuple(out)


def read_board(record: PropertyRecord, *, where: str) -> tuple[BoardRecord, list[Issue]]:
    """The board record of ``record`` with its typed views and the issues of its keys."""
    values = KeyReader(record, where)
    x, y = values.mil("ORIGINX"), values.mil("ORIGINY")
    layers = _layers(values)
    chain, problems = _chain(layers, where)
    board = BoardRecord(
        record=record,
        kind=record.get("KIND"),
        version=record.get("VERSION"),
        filename=record.get("FILENAME"),
        origin=None if x is None or y is None else (x, y),
        display_unit=values.int("DISPLAYUNIT"),
        outline=read_outline(values),
        layers=layers,
        copper_chain=chain,
        stack=_stack(record),
        plane_nets=MappingProxyType(_planes(record)),
        layer_pairs=_pairs(record),
    )
    return board, [*values.issues, *problems]


__all__ = [
    "LAYER_NAMES",
    "NO_NET",
    "BoardRecord",
    "KeyReader",
    "NumberedLayer",
    "OutlineVertex",
    "StackLayer",
    "long_layer_id",
    "read_board",
    "read_outline",
]
