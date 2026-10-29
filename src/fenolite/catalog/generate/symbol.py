# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Symbols generated from pin tables by a deterministic layout rule (change c0261).

Supply pins on top, ground at the bottom, inputs, control and passive pins on the left, outputs,
bidirectional and unconnected pins on the right; buses kept together; one empty slot between groups; every
connection point and body corner on the 2.54 mm grid. Above ``PinTable.split_above`` visible rows the
symbol is split into units. The constants are Fenolite's own and recorded ``INFERRED`` in
``docs/formats/library/symbols.md``; the rule is described in ``docs/symbols.md``. Pure: the same table
and arguments give equal definitions.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm
from fenolite.model.library import (
    PinRow,
    PinTable,
    SymbolDef,
    SymbolGraphic,
    SymbolPin,
    SymbolUnit,
)

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {"symbol.bus-gap": "info", "symbol.bus-split": "warning", "symbol.units-split": "info"}
)
"""The findings of ``generate_symbol`` and their severities."""
G: Nm = 2_540_000
"""The grid and the pin pitch: 100 mil."""
L: Nm = 2_540_000
"""The pin length."""
A: Nm = 1_016_000
"""The estimated advance of one character of a pin name at the 1.27 mm font."""
STROKE: Nm = 254_000
"""The width of the body outline."""
STACKED_TYPE = "passive"
"""The electrical type of the further pin of a ``stacked`` pad number: the value of
``backends.kicad.symembed.STACKED_TYPE`` (change c0123), which this package cannot import."""
ID_BACKEND = "fenolite.catalog"
"""The backend part of the ids of a generated symbol (``derived_id("sym", ID_BACKEND, lib id)``)."""

SIDE_OF_GROUP: dict[str, str] = {
    "supply": "top",
    "ground": "bottom",
    "input": "left",
    "control": "left",
    "passive": "left",
    "output": "right",
    "io": "right",
    "nc": "right",
}
_ALL_GROUPS = ("input", "control", "passive", "output", "io", "nc", "supply", "ground")
GROUP_ORDER: dict[str, tuple[str, ...]] = {
    side: (*own, *(g for g in _ALL_GROUPS if g not in own))
    for side, own in (
        ("left", ("input", "control", "passive")),
        ("right", ("output", "io", "nc")),
        ("top", ("supply",)),
        ("bottom", ("ground",)),
    )
}
"""The order of the groups on each side: the side's own groups, then any group a row moves there with an
explicit ``side``."""
_GROUP_OF_TYPE: dict[str, str] = {
    "input": "input",
    "output": "output",
    "power_out": "output",
    "open_collector": "output",
    "open_emitter": "output",
    "tri_state": "output",
    "bidirectional": "io",
    "passive": "passive",
    "free": "passive",
    "unspecified": "passive",
    "no_connect": "nc",
}
GROUND_NAME = re.compile(r"(?i)^(A|D|P|S)?(GND|VSS)")
PAD_NAME = re.compile(r"(?i)^(EP|PAD|THERMAL)$")
BUS_NAME = re.compile(r"^(.*[^0-9])([0-9]+)$")
_OVERBAR = re.compile(r"~\{([^}]*)\}")
_ROTATION = {"left": 0, "right": 180_000_000, "top": 270_000_000, "bottom": 90_000_000}


def default_group(row: PinRow) -> str:
    """The group of ``row``: its own, else the default of its type (design decision 2)."""
    if row.group:
        return row.group
    if row.etype == "power_in":
        return "ground" if GROUND_NAME.match(row.name) or PAD_NAME.fullmatch(row.name) else "supply"
    return _GROUP_OF_TYPE[row.etype]


def name_width(name: str) -> int:
    """The characters of a pin name as drawn: overbar markup removed, ``~`` (unnamed) is empty."""
    return 0 if name == "~" else len(_OVERBAR.sub(r"\1", name))


def natural_key(text: str) -> tuple[tuple[int, int, str], ...]:
    """``D2`` before ``D10``: digit runs compare as numbers."""
    return tuple(
        (0, int(part), part) if part.isdigit() else (1, 0, part)
        for part in re.split(r"([0-9]+)", text)
        if part
    )


def ceil2g(value: int) -> int:
    """The smallest multiple of ``2 G`` that is at least ``value``."""
    step = 2 * G
    return -(-value // step) * step


@dataclass(frozen=True, slots=True)
class _Row:
    index: int
    row: PinRow
    group: str
    side: str
    bus: str  # "" or a key: "=<name>" for an explicit bus, "~<group>/<side>/<prefix>" for an implicit one


def _rows(table: PinTable, issues: list[Issue], where: str) -> list[_Row]:
    """The rows with their effective group, side and bus; reports ``symbol.bus-gap``."""
    found = [
        _Row(i, r, default_group(r), r.side or SIDE_OF_GROUP[default_group(r)], "")
        for i, r in enumerate(table.rows)
    ]
    first: dict[str, _Row] = {}
    out: list[_Row] = []
    for item in found:
        if item.row.bus:
            key = "=" + item.row.bus
            head = first.setdefault(key, item)
            out.append(_Row(item.index, item.row, head.group, head.side, key))
        else:
            out.append(item)
    if table.auto_bus:
        members: dict[str, list[int]] = {}
        for position, item in enumerate(out):
            match = BUS_NAME.fullmatch(item.row.name)
            if not item.bus and match:
                members.setdefault(f"~{item.group}/{item.side}/{match.group(1)}", []).append(position)
        for key, positions in members.items():
            if len(positions) >= 2:
                for position in positions:
                    item = out[position]
                    out[position] = _Row(item.index, item.row, item.group, item.side, key)
    buses: dict[str, list[str]] = {}
    for item in out:
        if item.bus:
            buses.setdefault(item.bus, []).append(item.row.name)
    for key, names in buses.items():
        matches = [BUS_NAME.fullmatch(name) for name in names]
        prefixes = {m.group(1) for m in matches if m}
        if not all(matches) or len(prefixes) != 1:
            continue
        indices = {int(m.group(2)) for m in matches if m}
        missing = sorted(set(range(min(indices), max(indices) + 1)) - indices)
        if missing:
            label = key[1:] if key.startswith("=") else key.rsplit("/", 1)[1]
            shown = ", ".join(str(n) for n in missing[:16]) + (", …" if len(missing) > 16 else "")
            issues.append(
                Issue(
                    "symbol.bus-gap",
                    "info",
                    f"{where}: bus {label} skips the indices {shown}",
                    where=f"{where} bus {label}",
                )
            )
    return out


def _side_slots(rows: Sequence[_Row], side: str) -> list[_Row | None]:
    """The slots of one side: groups in ``GROUP_ORDER``, a bus as one block at its first row in natural
    order of its names, other rows in table order, one empty slot (``None``) between groups."""
    slots: list[_Row | None] = []
    for group in GROUP_ORDER[side]:
        members = [r for r in rows if r.side == side and r.group == group]
        if not members:
            continue
        block: list[_Row] = []
        done: set[str] = set()
        for item in members:
            if not item.bus:
                block.append(item)
            elif item.bus not in done:
                done.add(item.bus)
                block += sorted(
                    (m for m in members if m.bus == item.bus),
                    key=lambda m: (natural_key(m.row.name), m.index),
                )
        if slots:
            slots.append(None)
        slots += block
    return slots


@dataclass(frozen=True, slots=True)
class _Frame:
    width: int
    height: int
    top_centre: int
    bottom_centre: int


def _join(common: list[_Row | None], own: list[_Row | None]) -> list[_Row | None]:
    return [*common, None, *own] if common and own else [*common, *own]


def _frame(sides: Sequence[dict[str, list[_Row | None]]]) -> _Frame:
    """The body size of the units whose sides are ``sides``, for design decision 4's formulas."""

    def chars(side: dict[str, list[_Row | None]], key: str) -> int:
        return max((name_width(r.row.name) for r in side[key] if r is not None), default=0)

    width = height = 4 * G
    n_top = n_bottom = 0
    for side in sides:
        n_top, n_bottom = max(n_top, len(side["top"])), max(n_bottom, len(side["bottom"]))
        width = max(
            width,
            ceil2g(A * (chars(side, "left") + chars(side, "right")) + 2 * G),
            ceil2g((max(len(side["top"]), len(side["bottom"])) + 1) * G),
        )
        height = max(
            height,
            ceil2g((max(len(side["left"]), len(side["right"])) + 1) * G),
            ceil2g(A * (chars(side, "top") + chars(side, "bottom")) + 2 * G),
        )
    return _Frame(width, height, (n_top - 1) // 2 if n_top else 0, (n_bottom - 1) // 2 if n_bottom else 0)


def _place(side: str, slot: int, frame: _Frame) -> Point:
    half_w, half_h = frame.width // 2, frame.height // 2
    if side == "left":
        return Point(-half_w - L, half_h - G * (slot + 1))
    if side == "right":
        return Point(half_w + L, half_h - G * (slot + 1))
    if side == "top":
        return Point(G * (slot - frame.top_centre), half_h + L)
    return Point(G * (slot - frame.bottom_centre), -half_h - L)


def _pins(item: _Row, at: Point, side: str, unit: int) -> list[SymbolPin]:
    row = item.row
    rotation = _ROTATION[side]
    pin = SymbolPin(
        row.number, row.name, row.etype, at, row.shape, rotation, L, unit, 1, row.hidden, row.alternates
    )
    stacked = [
        SymbolPin(number, row.name, STACKED_TYPE, at, "line", rotation, L, unit, 1, True)  # type: ignore[arg-type]
        for number in row.stacked
    ]
    return [pin, *stacked]


def _auto_units(
    table: PinTable, rows: list[_Row], issues: list[Issue], where: str
) -> tuple[list[list[_Row]], int] | None:
    """The automatic split (design decision 3): the units and the number of signal units, or ``None``
    when the table stays one unit."""
    if sum(1 for r in rows if not r.row.hidden) <= table.split_above:
        return None
    size = table.unit_pins
    power = [r for r in rows if r.group == "supply"] + [r for r in rows if r.group == "ground"]
    others = [r for r in rows if r.group not in ("supply", "ground")]
    blocks: list[tuple[str, list[_Row]]] = []
    seen: set[str] = set()
    for item in others:
        if item.bus:
            if item.bus not in seen:
                seen.add(item.bus)
                blocks.append((item.bus, [m for m in others if m.bus == item.bus]))
        elif blocks and not blocks[-1][0] and blocks[-1][1][-1].group == item.group:
            blocks[-1][1].append(item)
        else:
            blocks.append(("", [item]))
    signal: list[list[_Row]] = []
    for key, block in blocks:
        if len(block) > size and key:
            label = key[1:] if key.startswith("=") else key.rsplit("/", 1)[1]
            issues.append(
                Issue(
                    "symbol.bus-split",
                    "warning",
                    f"{where}: bus {label} of {len(block)} pins is larger than a unit of {size} pins and is "
                    "cut across units",
                    where=f"{where} bus {label}",
                )
            )
        for start in range(0, len(block), size):
            part = block[start : start + size]
            if signal and len(signal[-1]) + len(part) <= size:
                signal[-1] += part
            else:
                signal.append(list(part))
    power_units = [power[start : start + size] for start in range(0, len(power), size)]
    units = signal + power_units
    if len(units) > 1:
        counts = ", ".join(str(len(u)) for u in signal) or "none"
        power_counts = ", ".join(str(len(u)) for u in power_units) or "none"
        issues.append(
            Issue(
                "symbol.units-split",
                "info",
                f"{where}: {len(rows)} pins split into {len(units)} units: {len(signal)} signal unit(s) of "
                f"{counts} pins and {len(power_units)} power unit(s) of {power_counts} pins",
                where=where,
            )
        )
    return units, len(signal)


def generate_symbol(
    table: PinTable, *, library: str, footprint: str = "", fp_filters: Sequence[str] = ()
) -> tuple[SymbolDef, tuple[SymbolDef, ...], tuple[Issue, ...]]:
    """The symbol of ``table`` in ``library``, its derived symbols (one per ``[[variant]]``) and the
    findings. ``footprint`` and ``fp_filters`` give the ``Footprint`` and ``ki_fp_filters`` properties."""
    lib_id = f"{library}:{table.name}" if library else table.name
    issues: list[Issue] = []
    rows = _rows(table, issues, lib_id)
    sides_of = ("left", "right", "top", "bottom")
    explicit = any(r.row.unit is not None for r in rows)
    pins: list[tuple[int, list[SymbolPin]]] = []
    graphics: list[SymbolGraphic] = []
    if explicit:
        count = max(r.row.unit or 0 for r in rows)
        common = [r for r in rows if r.row.unit == 0]
        common_sides = {s: _side_slots(common, s) for s in sides_of}
        unit_sides = [
            {
                s: _join(common_sides[s], _side_slots([r for r in rows if r.row.unit == u], s))
                for s in sides_of
            }
            for u in range(1, count + 1)
        ]
        shared = _frame(unit_sides) if common else None
        frames = [shared or _frame([sides]) for sides in unit_sides]
        units = list(range(1, count + 1))
    else:
        split = _auto_units(table, rows, issues, lib_id)
        groups = [rows] if split is None else split[0]
        unit_sides = [{s: _side_slots(members, s) for s in sides_of} for members in groups]
        frames = [_frame([sides]) for sides in unit_sides]
        units = list(range(1, len(groups) + 1))
    placed: set[int] = set()
    for unit, sides, frame in zip(units, unit_sides, frames, strict=True):
        for side in sides_of:
            for slot, item in enumerate(sides[side]):
                if item is None or item.index in placed:
                    continue
                owner = 0 if explicit and item.row.unit == 0 else unit
                if owner == 0:
                    placed.add(item.index)
                pins.append((item.index, _pins(item, _place(side, slot, frame), side, owner)))
        many = len(units) > 1
        half_w, half_h = frame.width // 2, frame.height // 2
        graphics.append(
            SymbolGraphic(
                "rect",
                (Point(-half_w, -half_h), Point(half_w, half_h)),
                STROKE,
                True,
                unit if many else 0,
                1 if many else 0,
            )
        )
    ordered = [pin for _, found in sorted(pins, key=lambda item: item[0]) for pin in found]
    names = dict(table.unit_names)
    properties = {
        "Reference": table.reference,
        "Value": table.name,
        "Footprint": footprint,
        "Datasheet": "",
        "Description": table.description or table.summary,
    }
    if table.keywords:
        properties["ki_keywords"] = " ".join(table.keywords)
    if fp_filters:
        properties["ki_fp_filters"] = " ".join(fp_filters)
    base = SymbolDef(
        id=derived_id("sym", ID_BACKEND, lib_id),
        name=table.name,
        library=library,
        properties=properties,
        units=tuple(SymbolUnit(u, 1, names.get(u, "")) for u in units),
        pins=tuple(ordered),
        graphics=tuple(graphics),
    )
    derived: list[SymbolDef] = []
    for variant in table.variants:
        own: dict[str, str] = {}
        for key, value in (
            ("Value", variant.value),
            ("Footprint", variant.footprint),
            ("Datasheet", variant.datasheet),
            ("Description", variant.description),
            ("ki_keywords", " ".join(variant.keywords)),
            ("ki_fp_filters", " ".join(variant.fp_filters)),
        ):
            if value:
                own[key] = value
        variant_id = f"{library}:{variant.name}" if library else variant.name
        derived.append(
            SymbolDef(
                id=derived_id("sym", ID_BACKEND, variant_id),
                name=variant.name,
                library=library,
                extends=table.name,
                properties=own,
            )
        )
    return base, tuple(derived), tuple(issues)


def sides(symbol: SymbolDef, unit: int = 1) -> dict[str, tuple[str, ...]]:
    """The visible pin names of one unit of a generated symbol per side, top to bottom on the left and right
    sides, left to right on the top and bottom: what the result of ``fenolite library symbol`` lists."""
    found: dict[str, list[tuple[int, str]]] = {"left": [], "right": [], "top": [], "bottom": []}
    side_of = {v: k for k, v in _ROTATION.items()}
    for pin in symbol.pins_of(unit):
        if (
            pin.hidden
            and pin.etype == STACKED_TYPE
            and any(p.position == pin.position and not p.hidden for p in symbol.pins)
        ):
            continue
        side = side_of[pin.rotation]
        key = -pin.position.y if side in ("left", "right") else pin.position.x
        found[side].append((key, pin.name))
    return {side: tuple(name for _, name in sorted(items)) for side, items in found.items()}


__all__ = [
    "GROUND_NAME",
    "GROUP_ORDER",
    "ID_BACKEND",
    "ISSUE_CODES",
    "PAD_NAME",
    "SIDE_OF_GROUP",
    "STACKED_TYPE",
    "STROKE",
    "A",
    "G",
    "L",
    "ceil2g",
    "default_group",
    "generate_symbol",
    "name_width",
    "natural_key",
    "sides",
]
