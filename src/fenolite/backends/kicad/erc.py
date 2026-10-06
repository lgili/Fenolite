# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad ERC reports (``sch erc --format json``) read into ``fenolite.backends.base.ErcReport``, and the
locations of the items they name (capability kicad-file-backend, "ERC report reading"; kicad-oracle,
"ERC oracle").

Facts and the reader's choices: ``docs/formats/kicad/erc.md``. Key names are those the tool writes, which
agree with the schema files S-0450 and S-0451; the schema is never vendored or read at runtime. The JSON
is parsed strictly, with numbers kept as text, so no float is ever created.
"""

from __future__ import annotations

import dataclasses
import json
import posixpath
import re
from collections.abc import Mapping
from fractions import Fraction
from types import MappingProxyType
from typing import Any, NoReturn, cast

from fenolite.backends.base import ErcItem, ErcReport, ErcViolation
from fenolite.backends.kicad.drc import UNIT_NM
from fenolite.backends.kicad.sexpr import Node
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-ERC-JSON", "H-K-ERC-POS", "H-K-ERC-COPYSET"))
"""``KICAD-VERIFIED``: the three hypotheses hold on ``kicad-cli`` 9.0.9 and 10.0.6
(``tests/kicad/check/test_erc_facts.py`` and ``test_erc_oracle.py``; c0062 task 8.2)."""
REQUIRED_KEYS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "report": ("source", "date", "kicad_version", "sheets"),
        "sheet": ("path", "uuid_path", "violations"),
        "violation": ("type", "description", "severity", "items"),
    }
)
"""The keys the reader requires at each level of a report; a missing one raises ``FormatError``."""
DEFAULT_UNITS = "mm"
"""The unit of a report without ``coordinate_units``."""
POSITION_SCALE: Mapping[int, int] = MappingProxyType({9: 100, 10: 100})
"""Major → the factor that turns a report position into a sheet position (``H-K-ERC-POS``). It holds a
major only once the probe ``erc-position-scale`` is ``equal`` on it; the others stay as converted."""
UNSCALED_CODE = "kicad.erc.position-unscaled"
ISSUE_CODES: Mapping[str, Severity] = MappingProxyType({UNSCALED_CODE: "info"})
LABEL_HEADS = frozenset({"label", "global_label", "hierarchical_label"})
"""The root children of a sheet file whose text is the location of an ERC item."""
ROOT_PATH = ""
"""The sheet id under which ``item_locations`` lists the location every use of an item agrees on."""
_VERSION = re.compile(r"(\d+)\.")


class _Number(str):
    """A JSON number, kept as its text."""


def _fail(message: str, file: str, where: str = "") -> NoReturn:
    raise FormatError(message, file=file, locator=where)


def _object(value: Any, file: str, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("not an object", file, where)
    return cast(dict[str, Any], value)


def _required(data: Mapping[str, Any], level: str, file: str, where: str) -> None:
    for key in REQUIRED_KEYS[level]:
        if key not in data:
            _fail(f"missing required key {key!r}", file, where)


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
    value = data.get(key, [])
    if not isinstance(value, list):
        _fail(f"{key!r} is not a list", file, f"{where}/{key}")
    return cast(list[Any], value)


def _nm(value: Any, scale: int, file: str, where: str) -> int:
    if not isinstance(value, _Number):
        _fail("a coordinate is not a number", file, where)
    try:
        exact = Fraction(str(value)) * scale
    except (ValueError, ZeroDivisionError):
        _fail("a coordinate is not a number", file, where)
    return round(exact)


def _item(raw: Any, scale: int, file: str, where: str) -> ErcItem:
    data = _object(raw, file, where)
    if "pos" not in data:
        _fail("missing key 'pos'", file, where)
    pos = _object(data["pos"], file, f"{where}/pos")
    for axis in ("x", "y"):
        if axis not in pos:
            _fail(f"missing key {axis!r}", file, f"{where}/pos")
    position = Point(
        _nm(pos["x"], scale, file, f"{where}/pos/x"), _nm(pos["y"], scale, file, f"{where}/pos/y")
    )
    return ErcItem(_string(data, "uuid", file, where), _string(data, "description", file, where), position)


def _violation(raw: Any, scale: int, sheet: str, sheet_id: str, file: str, where: str) -> ErcViolation:
    data = _object(raw, file, where)
    _required(data, "violation", file, where)
    excluded = data.get("excluded", False)
    if not isinstance(excluded, bool):
        _fail("'excluded' is not a boolean", file, f"{where}/excluded")
    items = _list(data, "items", file, where)
    return ErcViolation(
        type=_string(data, "type", file, where),
        description=_string(data, "description", file, where),
        severity=_string(data, "severity", file, where),
        items=tuple(_item(item, scale, file, f"{where}/items/{i}") for i, item in enumerate(items)),
        excluded=excluded,
        sheet=sheet,
        sheet_id=sheet_id,
    )


def _constant(name: str) -> NoReturn:
    raise ValueError(f"{name} is not allowed in strict JSON")


def _major(version: str) -> int | None:
    match = _VERSION.match(version.strip())
    return int(match.group(1)) if match else None


def read_erc_report(
    text: str, *, file: str = "", major: int | None = None, issues: list[Issue] | None = None
) -> ErcReport:
    """An ``ErcReport`` from the JSON text that ``kicad-cli sch erc --format json`` writes (``erc.md``).

    Positions become sheet positions in nm: the report's unit, then ``POSITION_SCALE`` of ``major`` (by
    default the first number of ``kicad_version``). For a major without a proved factor they stay as
    converted, and ``issues`` gets one ``kicad.erc.position-unscaled`` info."""
    try:
        raw = json.loads(text, parse_float=_Number, parse_int=_Number, parse_constant=_constant)
    except ValueError as error:
        _fail(f"not strict JSON: {error}", file)
    data = _object(raw, file, "")
    _required(data, "report", file, "")
    units = _string(data, "coordinate_units", file, "", default=DEFAULT_UNITS)
    unit = UNIT_NM.get(units)
    if unit is None:
        _fail(
            f"unknown coordinate_units {units!r}; expected one of {', '.join(UNIT_NM)}",
            file,
            "/coordinate_units",
        )
    version = _string(data, "kicad_version", file, "")
    running = major if major is not None else _major(version)
    factor = POSITION_SCALE.get(running) if running is not None else None
    if factor is None and issues is not None:
        issues.append(
            Issue(
                UNSCALED_CODE,
                ISSUE_CODES[UNSCALED_CODE],
                f"no position scale is proved for KiCad {version or '?'}: ERC positions are left as the "
                "report gives them",
                where=file,
            )
        )
    scale = unit * (factor if factor is not None else 1)
    violations: list[ErcViolation] = []
    paths: list[str] = []
    for index, entry in enumerate(_list(data, "sheets", file, "")):
        where = f"/sheets/{index}"
        sheet = _object(entry, file, where)
        _required(sheet, "sheet", file, where)
        path = _string(sheet, "path", file, where)
        sheet_id = _string(sheet, "uuid_path", file, where)
        paths.append(path)
        for number, found in enumerate(_list(sheet, "violations", file, where)):
            violations.append(_violation(found, scale, path, sheet_id, file, f"{where}/violations/{number}"))
    severities = _list(data, "included_severities", file, "")
    if not all(isinstance(s, str) and not isinstance(s, _Number) for s in severities):
        _fail("'included_severities' is not a list of strings", file, "/included_severities")
    return ErcReport(
        source=_string(data, "source", file, ""),
        date=_string(data, "date", file, ""),
        kicad_version=version,
        coordinate_units=units,
        violations=tuple(violations),
        ignored_checks=tuple(
            _string(_object(entry, file, f"/ignored_checks/{i}"), "key", file, f"/ignored_checks/{i}")
            for i, entry in enumerate(_list(data, "ignored_checks", file, ""))
        ),
        included_severities=tuple(str(s) for s in severities),
        sheets=tuple(paths),
    )


# -- item locations


def _first(node: Node | None) -> str:
    atoms = node.atoms() if node is not None else ()
    return atoms[0].value if atoms else ""


def _property(node: Node, name: str) -> str:
    for child in node.nodes("property"):
        atoms = child.atoms()
        if len(atoms) >= 2 and atoms[0].value == name:
            return atoms[1].value
    return ""


def _sheet_ids(trees: Mapping[str, Node], root: str) -> dict[str, list[str]]:
    """File name → the uuid paths of its uses, walked from ``root`` through the sheet references."""
    found: dict[str, list[str]] = {}
    tree = trees.get(root)
    if tree is None:
        return found
    queue: list[tuple[str, str, tuple[str, ...]]] = [(root, f"/{_first(tree.find('uuid'))}", (root,))]
    while queue:
        name, path, trail = queue.pop(0)
        found.setdefault(name, []).append(path)
        for sheet in trees[name].nodes("sheet"):
            target = _property(sheet, "Sheetfile") or _property(sheet, "Sheet file")
            if not target:
                continue
            folder = posixpath.dirname(name)
            child = posixpath.normpath(posixpath.join(folder, target.replace("\\", "/")))
            if child not in trees or child in trail:
                continue
            queue.append((child, f"{path}/{_first(sheet.find('uuid'))}", (*trail, child)))
    return found


def _references(symbol: Node, project: str) -> dict[str, str]:
    """Sheet id → the reference of ``symbol`` there; the uses of ``project`` win over those of another."""
    found: dict[str, str] = {}
    instances = symbol.find("instances")
    if instances is None:
        return found
    listed = instances.nodes("project")
    for wanted in (False, True):  # the named project last, so that it overwrites
        for entry in listed:
            if (_first(entry) == project) is not wanted:
                continue
            for use in entry.nodes("path"):
                reference = _first(use.find("reference"))
                if reference:
                    found[_first(use)] = reference
    return found


def item_locations(trees: Mapping[str, Node], project: str) -> Mapping[tuple[str, str], str]:
    """``(sheet id, uuid) → location`` for the pins, symbols and labels of the sheet files ``trees``
    (POSIX name relative to the project root → parsed tree) of the project named ``project``.

    A pin gives ``REF-PIN``, a symbol ``REF`` and a label its text; the reference is the one the symbol's
    ``instances`` give for that sheet. The key ``(ROOT_PATH, uuid)`` holds the location on which every use
    of the item agrees: KiCad lists some violations under the root sheet whatever sheet the item is on.
    Uuids are lower case."""
    uses = _sheet_ids(trees, f"{project}.kicad_sch")
    found: dict[tuple[str, str], str] = {}
    for name, tree in trees.items():
        paths = uses.get(name, [])
        for symbol in tree.nodes("symbol"):
            references = _references(symbol, project)
            uuid = _first(symbol.find("uuid")).lower()
            for path, reference in references.items():
                if uuid:
                    found[(path, uuid)] = reference
                for pin in symbol.nodes("pin"):
                    pin_uuid = _first(pin.find("uuid")).lower()
                    number = _first(pin)
                    if pin_uuid:
                        found[(path, pin_uuid)] = f"{reference}-{number}" if number else reference
        for child in tree.nodes():
            if child.name not in LABEL_HEADS:
                continue
            uuid, text = _first(child.find("uuid")).lower(), _first(child)
            if not uuid or not text:
                continue
            for path in paths:
                found[(path, uuid)] = text
    agreed: dict[str, set[str]] = {}
    for (_, uuid), location in found.items():
        agreed.setdefault(uuid, set()).add(location)
    for uuid, locations in agreed.items():
        if len(locations) == 1:
            found[(ROOT_PATH, uuid)] = next(iter(locations))
    return MappingProxyType(found)


def located(report: ErcReport, locations: Mapping[tuple[str, str], str]) -> ErcReport:
    """``report`` with the ``where`` of every item that ``locations`` knows, on its sheet or everywhere."""

    def where(violation: ErcViolation, item: ErcItem) -> str:
        uuid = item.uuid.lower()
        return locations.get((violation.sheet_id, uuid)) or locations.get((ROOT_PATH, uuid), "")

    return dataclasses.replace(
        report,
        violations=tuple(
            dataclasses.replace(v, items=tuple(dataclasses.replace(i, where=where(v, i)) for i in v.items))
            for v in report.violations
        ),
    )


__all__ = [
    "DEFAULT_UNITS",
    "EVIDENCE",
    "ISSUE_CODES",
    "LABEL_HEADS",
    "POSITION_SCALE",
    "REQUIRED_KEYS",
    "ROOT_PATH",
    "UNSCALED_CODE",
    "item_locations",
    "located",
    "read_erc_report",
]
