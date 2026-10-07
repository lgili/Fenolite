# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad DRC reports (``pcb drc --format json``) read into ``fenolite.backends.base.DrcReport``.

Facts and the reader's choices: ``docs/formats/kicad/drc.md``. Key names come from the schema files
S-0055 and S-0056, which are never vendored or read at runtime. The JSON is parsed strictly, with
numbers kept as text, so no float is ever created.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from fractions import Fraction
from types import MappingProxyType
from typing import Any, NoReturn, cast

from fenolite.backends.base import DrcItem, DrcLimits, DrcReport, DrcViolation
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-DRC-JSON",))
"""Settled on ``kicad-cli`` 9.0.9 and 10.0.6 (``tests/kicad/board/test_drc_report.py``)."""
REQUIRED_KEYS: tuple[str, ...] = (
    "source",
    "date",
    "kicad_version",
    "violations",
    "unconnected_items",
    "schematic_parity",
    "coordinate_units",
)
LIB_FOOTPRINT_MISMATCH = "lib_footprint_mismatch"
LIB_FOOTPRINT_ISSUES = "lib_footprint_issues"
_MEASURED = DrcLimits({"clearance": 499, "unconnected_items": 499}, others=199)
REPORT_LIMITS: Mapping[int, DrcLimits] = MappingProxyType({9: _MEASURED, 10: _MEASURED})
"""Per ``kicad-cli`` major, the number of entries at which ``pcb drc --format json`` stops writing a type
(``H-K-DRC-LIMITS``): 499 for ``clearance`` and for the unconnected items, 199 for every other type. Each
number is pinned to a probe ``drc-limit-<type>`` (``tests/kicad/check/test_drc_limits.py``); ``others`` is
measured for eleven types and assumed for the rest. 9.0.9 can write a few more than 499 ``clearance``
entries (``H-K-DRC-LIMIT``), so a count at or above its limit is a lower bound. A major without a row was
not measured."""


def report_limits(major: int) -> DrcLimits:
    """``REPORT_LIMITS[major]``; ``ValueError`` for a major that no probe measured."""
    limits = REPORT_LIMITS.get(major)
    if limits is None:
        raise ValueError(
            f"unsupported KiCad {major}; DRC report limits are measured for: {tuple(REPORT_LIMITS)}"
        )
    return limits


UNIT_NM: Mapping[str, int] = MappingProxyType({"mm": 1_000_000, "mils": 25_400, "in": 25_400_000})
"""Nanometres per unit of ``coordinate_units``."""


class _Number(str):
    """A JSON number, kept as its text."""


def _fail(message: str, file: str, where: str = "") -> NoReturn:
    raise FormatError(message, file=file, locator=where)


def _string(data: Mapping[str, Any], key: str, file: str, where: str, default: str | None = None) -> str:
    if key not in data:
        if default is not None:
            return default
        _fail(f"missing key {key!r}", file, where)
    value = data[key]
    if not isinstance(value, str) or isinstance(value, _Number):
        _fail(f"{key!r} is not a string", file, f"{where}/{key}")
    return value


def _list(data: Mapping[str, Any], key: str, file: str, where: str) -> list[Any]:
    if key not in data:
        _fail(f"missing key {key!r}", file, where)
    value = data[key]
    if not isinstance(value, list):
        _fail(f"{key!r} is not a list", file, f"{where}/{key}")
    return value  # pyright: ignore[reportUnknownVariableType]


def _optional_list(data: Mapping[str, Any], key: str, file: str) -> list[Any]:
    value = data.get(key, [])
    if not isinstance(value, list):
        _fail(f"{key!r} is not a list", file, f"/{key}")
    return cast(list[Any], value)


def _object(value: Any, file: str, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("not an object", file, where)
    return value  # pyright: ignore[reportUnknownVariableType]


def _nm(value: Any, scale: int, file: str, where: str) -> int:
    if not isinstance(value, _Number):
        _fail("a coordinate is not a number", file, where)
    exact = Fraction(str(value)) * scale
    return round(exact)


def _item(raw: Any, scale: int, file: str, where: str) -> DrcItem:
    data = _object(raw, file, where)
    pos = (
        _object(data["pos"], file, f"{where}/pos")
        if "pos" in data
        else _fail("missing key 'pos'", file, where)
    )
    for axis in ("x", "y"):
        if axis not in pos:
            _fail(f"missing key {axis!r}", file, f"{where}/pos")
    position = Point(
        _nm(pos["x"], scale, file, f"{where}/pos/x"), _nm(pos["y"], scale, file, f"{where}/pos/y")
    )
    return DrcItem(_string(data, "uuid", file, where), _string(data, "description", file, where), position)


def _violations(raw: Sequence[Any], scale: int, file: str, where: str) -> tuple[DrcViolation, ...]:
    out: list[DrcViolation] = []
    for index, entry in enumerate(raw):
        loc = f"{where}/{index}"
        data = _object(entry, file, loc)
        excluded = data.get("excluded", False)
        if not isinstance(excluded, bool):
            _fail("'excluded' is not a boolean", file, f"{loc}/excluded")
        items = _list(data, "items", file, loc)
        out.append(
            DrcViolation(
                type=_string(data, "type", file, loc),
                description=_string(data, "description", file, loc),
                severity=_string(data, "severity", file, loc),
                items=tuple(_item(item, scale, file, f"{loc}/items/{i}") for i, item in enumerate(items)),
                excluded=excluded,
                comment=_string(data, "comment", file, loc, default=""),
            )
        )
    return tuple(out)


def _constant(name: str) -> NoReturn:
    raise ValueError(f"{name} is not allowed in strict JSON")


def read_drc_report(text: str, *, file: str = "") -> DrcReport:
    """A ``DrcReport`` from the JSON text that ``kicad-cli pcb drc --format json`` writes (``drc.md``)."""
    try:
        raw = json.loads(text, parse_float=_Number, parse_int=_Number, parse_constant=_constant)
    except ValueError as error:
        _fail(f"not strict JSON: {error}", file)
    data = _object(raw, file, "")
    for key in REQUIRED_KEYS:
        if key not in data:
            _fail(f"missing required key {key!r}", file)
    units = _string(data, "coordinate_units", file, "")
    scale = UNIT_NM.get(units)
    if scale is None:
        _fail(
            f"unknown coordinate_units {units!r}; expected one of {', '.join(UNIT_NM)}",
            file,
            "/coordinate_units",
        )
    ignored = _optional_list(data, "ignored_checks", file)
    severities = _optional_list(data, "included_severities", file)
    if not all(isinstance(s, str) and not isinstance(s, _Number) for s in severities):
        _fail("'included_severities' is not a list of strings", file, "/included_severities")
    return DrcReport(
        source=_string(data, "source", file, ""),
        date=_string(data, "date", file, ""),
        kicad_version=_string(data, "kicad_version", file, ""),
        coordinate_units=units,
        violations=_violations(_list(data, "violations", file, ""), scale, file, "/violations"),
        unconnected_items=_violations(
            _list(data, "unconnected_items", file, ""), scale, file, "/unconnected_items"
        ),
        schematic_parity=_violations(
            _list(data, "schematic_parity", file, ""), scale, file, "/schematic_parity"
        ),
        ignored_checks=tuple(
            _string(_object(entry, file, f"/ignored_checks/{i}"), "key", file, f"/ignored_checks/{i}")
            for i, entry in enumerate(ignored)
        ),
        included_severities=tuple(str(s) for s in severities),
    )


__all__ = [
    "EVIDENCE",
    "LIB_FOOTPRINT_ISSUES",
    "LIB_FOOTPRINT_MISMATCH",
    "REPORT_LIMITS",
    "REQUIRED_KEYS",
    "UNIT_NM",
    "read_drc_report",
    "report_limits",
]
