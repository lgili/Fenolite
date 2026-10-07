# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Requirements supplied by the user, as a TOML document of integers (capability board-analyses,
"Requirement tables supplied by the user"; ``docs/analyses.md``, "The requirements file").

Fenolite ships no requirement value. The document names currents per net or net class, distances per
pair, and an optional table from voltage to distance that the user fills. Units are in the key names
(``milliamps``, ``temp_rise_mk``, ``clearance_nm``, ``millivolts``), so every number is an integer and
none needs a parser. A voltage is looked up as the first step at or above it: nothing is interpolated.

Change c0115 adds, under the same schema name: ``[[path]]`` rows (the current between two sets of pads,
with an optional largest voltage drop), ``insulation_nm`` on distance rows and steps (the distance
through the laminate between two layers) and ``groove_nm`` on distance rows (the width below which a
groove is bridged on the creepage path). A file that uses them is refused by a loader that predates them.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from typing import cast

from fenolite.core.errors import FormatError
from fenolite.core.units import Nm
from fenolite.model.circuit import Circuit, Net
from fenolite.model.rules import RuleSubject, Selector

SCHEMA = "fenolite.requirements.v0"
DEFAULT_CLASS = "Default"
QUANTITIES = ("clearance_nm", "creepage_nm", "embedded_nm")
_DISTANCES = (*QUANTITIES, "insulation_nm")
_TOP = ("schema", "current", "distance", "step", "path")


@dataclass(frozen=True, slots=True)
class NetSelector:
    """Exactly one of a net glob and a net-class glob, matched as ``model.rules.Selector`` matches."""

    net: str | None = None
    netclass: str | None = None

    def matches(self, net: Net, circuit: Circuit) -> bool:
        subject = RuleSubject("net", net=net.name, netclass=class_of(net, circuit))
        if self.net is not None:
            return Selector("net", self.net).matches(subject)
        return Selector("netclass", self.netclass or "").matches(subject)

    def text(self) -> str:
        return f"net {self.net}" if self.net is not None else f"netclass {self.netclass}"


@dataclass(frozen=True, slots=True)
class CurrentReq:
    select: NetSelector
    milliamps: int
    temp_rise_mk: int


@dataclass(frozen=True, slots=True)
class DistanceReq:
    """Distances of a pair, or the voltage whose step gives them."""

    a: NetSelector
    b: NetSelector
    clearance_nm: Nm | None = None
    creepage_nm: Nm | None = None
    embedded_nm: Nm | None = None
    millivolts: int | None = None
    insulation_nm: Nm | None = None
    groove_nm: Nm | None = None

    def matches(self, first: Net, second: Net, circuit: Circuit) -> bool:
        if first.id == second.id:
            return False
        return (self.a.matches(first, circuit) and self.b.matches(second, circuit)) or (
            self.a.matches(second, circuit) and self.b.matches(first, circuit)
        )

    def text(self) -> str:
        return f"distance between {self.a.text()} and {self.b.text()}"


@dataclass(frozen=True, slots=True)
class Step:
    """One row of the user's table from voltage to distance."""

    up_to_mv: int
    clearance_nm: Nm | None = None
    creepage_nm: Nm | None = None
    embedded_nm: Nm | None = None
    insulation_nm: Nm | None = None


@dataclass(frozen=True, slots=True)
class PathReq:
    """A power path: the pads where the current enters and leaves (``REF-PIN``), the current, the
    temperature rise the user accepts and the largest voltage drop."""

    start: tuple[str, ...]
    end: tuple[str, ...]
    milliamps: int
    temp_rise_mk: int
    drop_mv: int | None = None


Triple = tuple[Nm | None, Nm | None, Nm | None]


def class_of(net: Net, circuit: Circuit) -> str:
    """The name of the net's class; ``Default`` for a net without one."""
    for netclass in circuit.netclasses:
        if netclass.id == net.netclass_id:
            return netclass.name
    return DEFAULT_CLASS


@dataclass(frozen=True, slots=True)
class Requirements:
    currents: tuple[CurrentReq, ...] = ()
    distances: tuple[DistanceReq, ...] = ()
    steps: tuple[Step, ...] = ()
    paths: tuple[PathReq, ...] = ()

    def current_for(self, net: Net, circuit: Circuit) -> CurrentReq | None:
        """The governing current row of ``net``: the matching row with the largest current."""
        matching = [row for row in self.currents if row.select.matches(net, circuit)]
        return max(matching, key=lambda row: row.milliamps) if matching else None

    def step_for(self, millivolts: int) -> Step | None:
        """The step with the smallest ``up_to_mv`` that is at least ``millivolts``; no interpolation."""
        usable = [step for step in self.steps if step.up_to_mv >= millivolts]
        return min(usable, key=lambda step: step.up_to_mv) if usable else None

    def values(self, row: DistanceReq) -> Triple | None:
        """The clearance, creepage and embedded distance of one row; ``None`` when its voltage is above
        every step."""
        if row.millivolts is None:
            return row.clearance_nm, row.creepage_nm, row.embedded_nm
        step = self.step_for(row.millivolts)
        return None if step is None else (step.clearance_nm, step.creepage_nm, step.embedded_nm)

    def distance_for(self, a: Net, b: Net, circuit: Circuit) -> Triple:
        """``(clearance, creepage, embedded)`` required of the pair: the largest value of each quantity
        over the matching rows, ``None`` where no row gives one."""
        found: list[Nm | None] = [None, None, None]
        for row in self.distances:
            if not row.matches(a, b, circuit):
                continue
            values = self.values(row)
            if values is None:
                continue
            for index, value in enumerate(values):
                current = found[index]
                if value is not None and (current is None or value > current):
                    found[index] = value
        return found[0], found[1], found[2]

    def insulation_for(self, a: Net, b: Net, circuit: Circuit) -> Nm | None:
        """The distance through the laminate required of the pair: the largest ``insulation_nm`` over the
        matching rows, a row with ``millivolts`` taking its step's; ``None`` where no row gives one."""
        found: Nm | None = None
        for row in self.distances:
            if not row.matches(a, b, circuit):
                continue
            value = row.insulation_nm
            if row.millivolts is not None:
                step = self.step_for(row.millivolts)
                value = None if step is None else step.insulation_nm
            if value is not None and (found is None or value > found):
                found = value
        return found

    def groove_for(self, a: Net, b: Net, circuit: Circuit) -> Nm | None:
        """The groove width of the pair: the largest ``groove_nm`` over the matching rows."""
        widths = [row.groove_nm for row in self.distances if row.groove_nm and row.matches(a, b, circuit)]
        return max(widths) if widths else None


def _fail(file: str, key: str, why: str) -> FormatError:
    return FormatError(f"{key}: {why}", file=file, locator=key)


def _integer(table: dict[str, object], key: str, where: str, file: str, *, required: bool) -> int | None:
    if key not in table:
        if required:
            raise _fail(file, f"{where}.{key}", "missing key")
        return None
    value = table[key]
    if type(value) is not int:
        raise _fail(file, f"{where}.{key}", "must be an integer (the unit is in the key name)")
    if value < 0:
        raise _fail(file, f"{where}.{key}", "must not be negative")
    return value


def _positive(table: dict[str, object], key: str, where: str, file: str) -> int:
    value = _integer(table, key, where, file, required=True)
    if not value:
        raise _fail(file, f"{where}.{key}", "must be above 0")
    return value


def _known(table: dict[str, object], allowed: tuple[str, ...], where: str, file: str) -> None:
    for key in table:
        if key not in allowed:
            raise _fail(file, f"{where}.{key}" if where else key, "unknown key")


def _selector(table: dict[str, object], key: str, where: str, file: str) -> NetSelector:
    name = f"{where}.{key}"
    if key not in table:
        raise _fail(file, name, "missing key")
    value = table[key]
    if not isinstance(value, dict):
        raise _fail(file, name, "must be a table with one of the keys net and netclass")
    entry = cast(dict[str, object], value)
    _known(entry, ("net", "netclass"), name, file)
    if len(entry) != 1:
        raise _fail(file, name, "must hold exactly one of the keys net and netclass")
    ((kind, glob),) = entry.items()
    if not isinstance(glob, str) or not glob:
        raise _fail(file, f"{name}.{kind}", "must be a non-empty string")
    return NetSelector(net=glob) if kind == "net" else NetSelector(netclass=glob)


def _rows(data: dict[str, object], key: str, file: str) -> list[tuple[str, dict[str, object]]]:
    listed = data.get(key, [])
    if not isinstance(listed, list):
        raise _fail(file, key, "must be an array of tables")
    rows: list[tuple[str, dict[str, object]]] = []
    for index, item in enumerate(cast(list[object], listed)):
        if not isinstance(item, dict):
            raise _fail(file, f"{key}[{index}]", "must be a table")
        rows.append((f"{key}[{index}]", cast(dict[str, object], item)))
    return rows


def _pad_names(table: dict[str, object], key: str, where: str, file: str) -> tuple[str, ...]:
    """A non-empty array of pad names ``REF-PIN``, split at the last ``-`` with both parts non-empty."""
    name = f"{where}.{key}"
    if key not in table:
        raise _fail(file, name, "missing key")
    value = table[key]
    if not isinstance(value, list) or not value:
        raise _fail(file, name, "must be a non-empty array of pad names REF-PIN")
    names: list[str] = []
    for item in cast(list[object], value):
        ref, dash, pin = item.rpartition("-") if isinstance(item, str) else ("", "", "")
        if not isinstance(item, str) or not dash or not ref or not pin:
            raise _fail(file, name, f"{item!r} is not a pad name REF-PIN")
        names.append(item)
    return tuple(names)


def load_requirements(text: str, *, file: str = "") -> Requirements:
    """The requirements of a TOML document of schema ``fenolite.requirements.v0``; ``FormatError`` naming
    the file and the key for a float, an unknown key, a missing key or another schema."""
    try:
        data: dict[str, object] = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise FormatError(f"not valid TOML: {error}", file=file) from None
    if data.get("schema") != SCHEMA:
        raise _fail(file, "schema", f"must be {SCHEMA!r}")
    _known(data, _TOP, "", file)
    currents: list[CurrentReq] = []
    for where, row in _rows(data, "current", file):
        _known(row, ("select", "milliamps", "temp_rise_mk"), where, file)
        select = _selector(row, "select", where, file)
        currents.append(
            CurrentReq(
                select, _positive(row, "milliamps", where, file), _positive(row, "temp_rise_mk", where, file)
            )
        )
    distances: list[DistanceReq] = []
    for where, row in _rows(data, "distance", file):
        _known(row, ("a", "b", "millivolts", "groove_nm", *_DISTANCES), where, file)
        a, b = _selector(row, "a", where, file), _selector(row, "b", where, file)
        values = [_integer(row, key, where, file, required=False) for key in _DISTANCES]
        millivolts = _integer(row, "millivolts", where, file, required=False)
        groove = _integer(row, "groove_nm", where, file, required=False)
        given = any(value is not None for value in values)
        if given == (millivolts is not None):
            raise _fail(file, where, "needs either millivolts or any of " + ", ".join(_DISTANCES))
        distances.append(DistanceReq(a, b, values[0], values[1], values[2], millivolts, values[3], groove))
    steps: list[Step] = []
    for where, row in _rows(data, "step", file):
        _known(row, ("up_to_mv", *_DISTANCES), where, file)
        up_to = _positive(row, "up_to_mv", where, file)
        values = [_integer(row, key, where, file, required=False) for key in _DISTANCES]
        if all(value is None for value in values):
            raise _fail(file, where, "needs any of " + ", ".join(_DISTANCES))
        steps.append(Step(up_to, values[0], values[1], values[2], values[3]))
    paths: list[PathReq] = []
    for where, row in _rows(data, "path", file):
        _known(row, ("from", "to", "milliamps", "temp_rise_mk", "drop_mv"), where, file)
        paths.append(
            PathReq(
                _pad_names(row, "from", where, file),
                _pad_names(row, "to", where, file),
                _positive(row, "milliamps", where, file),
                _positive(row, "temp_rise_mk", where, file),
                _integer(row, "drop_mv", where, file, required=False),
            )
        )
    return Requirements(tuple(currents), tuple(distances), tuple(steps), tuple(paths))


__all__ = [
    "DEFAULT_CLASS",
    "SCHEMA",
    "CurrentReq",
    "DistanceReq",
    "NetSelector",
    "PathReq",
    "Requirements",
    "Step",
    "class_of",
    "load_requirements",
]
