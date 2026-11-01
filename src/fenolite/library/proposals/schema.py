# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Closed, geometry-free proposal records; H-G-PROPOSAL (c0265)."""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import tomllib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from fenolite.catalog.footprints.record import FAMILY_KEYS, LAND_KEYS, Key
from fenolite.catalog.pins import GROUPS, PIN_SHAPES, PIN_TYPES, SIDES
from fenolite.core.errors import FormatError, Issue
from fenolite.core.quantities import LengthRange, QuantityError, micro_units, parse_length_range
from fenolite.library.codes import issue

SCHEMA = "fenolite.proposal.v0"
ROOT_KEYS = frozenset(
    {"schema", "datasheet", "proposer", "device", "package", "pin", "ratings", "part", "doubt"}
)
GEOMETRY = frozenset(
    {
        "pads",
        "pad",
        "x",
        "y",
        "at",
        "position",
        "outline",
        "polygon",
        "courtyard",
        "silkscreen",
        "graphics",
        "vertices",
        "points",
    }
)
PIN_KEYS = frozenset(
    {
        "number",
        "name",
        "type",
        "group",
        "side",
        "unit",
        "bus",
        "shape",
        "hidden",
        "stacked",
        "alternates",
        "cite",
    }
)
RATING_UNITS = {
    "vin": "volt",
    "vout": "volt",
    "voltage": "volt",
    "current": "ampere",
    "power": "watt",
    "temperature": "kelvin",
}


class ProposalTooNew(FormatError):
    cli_code = "FEN-3002"


@dataclass(frozen=True)
class Proposal:
    data: dict[str, Any]
    parameters: dict[str, Any]
    quantities: dict[str, LengthRange]
    parse_issues: tuple[Issue, ...] = ()
    file: str = ""

    @property
    def pins(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], self.data.get("pin", []))

    @property
    def family(self) -> str:
        return str(self.data["package"]["family"])

    @property
    def uncited(self) -> list[str]:
        values = [name for name in ("device", "package") if "cite" not in self.data[name]]
        if "land" in self.data["package"] and "cite" not in self.data["package"]["land"]:
            values.append("package.land")
        values += [f"pin[{row['number']}]" for row in self.pins if "cite" not in row]
        values += [f"ratings.{key}" for key, row in self.data.get("ratings", {}).items() if "cite" not in row]
        values += [f"part[{i}]" for i, row in enumerate(self.data.get("part", [])) if "cite" not in row]
        return values


def _table(value: Any, file: str, path: str, allowed: set[str] | frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FormatError("must be a table", file=file, locator=path)
    data = cast(dict[str, Any], value)
    for key in sorted(set(data) - allowed):
        geometry = key in GEOMETRY
        message = "proposal.geometry-refused: a proposal carries no geometry" if geometry else "unknown key"
        raise FormatError(message, file=file, locator=f"{path}.{key}" if path else key)
    return data


def _text(value: Any, file: str, path: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()) or not value.isprintable() and value:
        raise FormatError("must be printable text", file=file, locator=path)
    return value


def _cite(row: dict[str, Any], file: str, path: str) -> None:
    if "cite" not in row:
        return
    cite = _table(row["cite"], file, path + ".cite", {"page", "table", "figure"})
    page = cite.get("page")
    if type(page) is not int or page < 1:
        raise FormatError(
            "citation page must be an integer of at least 1", file=file, locator=path + ".cite.page"
        )
    if "table" in cite and "figure" in cite:
        raise FormatError("cite names at most one table or figure", file=file, locator=path + ".cite")
    for key in ("table", "figure"):
        if key in cite:
            _text(cite[key], file, path + ".cite." + key)


def _rows(data: dict[str, Any], key: str, file: str) -> list[dict[str, Any]]:
    values = data.get(key, [])
    if not isinstance(values, list) or any(not isinstance(v, dict) for v in cast(list[Any], values)):
        raise FormatError("must be an array of tables", file=file, locator=key)
    return cast(list[dict[str, Any]], values)


def _parameter(
    value: Any,
    spec: Key,
    path: str,
    file: str,
    quantities: dict[str, LengthRange],
    issues: list[Issue],
    *,
    strict: bool = True,
) -> Any:
    if spec.kind == "length":
        try:
            parsed = parse_length_range(value, file=file, locator=path)
        except FormatError as error:
            if "bounds out of order" in str(error):
                issues.append(issue("proposal.range", str(error), where=path))
                return value
            raise
        quantities[path] = parsed
        return {"min": parsed.min, "nom": parsed.nom, "max": parsed.max}
    if spec.kind == "table":
        table = _table(value, file, path, set(spec.table))
        for key, child in spec.table.items():
            if strict and child.required and key not in table:
                raise FormatError("required key is missing", file=file, locator=path + "." + key)
        return {
            key: _parameter(v, spec.table[key], path + "." + key, file, quantities, issues, strict=strict)
            for key, v in table.items()
        }
    if spec.kind == "tables":
        if not isinstance(value, list):
            raise FormatError("must be an array of tables", file=file, locator=path)
        return [
            _parameter(
                v, Key("table", table=spec.table), path + f"[{i}]", file, quantities, issues, strict=strict
            )
            for i, v in enumerate(cast(list[Any], value))
        ]
    if spec.kind in {"count", "drawing"}:
        if type(value) is not int or value < 1:
            raise FormatError("must be a positive integer", file=file, locator=path)
    elif spec.kind == "text":
        _text(value, file, path)
        if spec.choices and value not in spec.choices:
            raise FormatError(f"must be one of {spec.choices}", file=file, locator=path)
    elif spec.kind in {"texts", "counts"}:
        if not isinstance(value, list) or any(
            (not isinstance(v, str) if spec.kind == "texts" else type(v) is not int)
            for v in cast(list[Any], value)
        ):
            raise FormatError("must be an array of the declared type", file=file, locator=path)
    elif spec.kind == "lengths":
        if isinstance(value, dict):
            return _parameter(
                value, Key("table", table=spec.table), path, file, quantities, issues, strict=strict
            )
        return _parameter(value, Key("length"), path, file, quantities, issues)
    elif spec.kind == "span":
        if not isinstance(value, str) or not re.fullmatch(r"[1-9]\d*\.\.[1-9]\d*", value):
            raise FormatError("must be a positive integer span N..N", file=file, locator=path)
    elif spec.kind == "depopulated":
        if not isinstance(value, (dict, list)):
            raise FormatError("must name depopulated balls or a centre block", file=file, locator=path)
        if isinstance(value, dict):
            table = _table(value, file, path, {"center"})
            if not isinstance(table.get("center"), str) or not re.fullmatch(
                r"[1-9]\d*x[1-9]\d*", table["center"]
            ):
                raise FormatError("center must be text 'RxC' with positive counts", file=file, locator=path)
        elif any(not isinstance(v, str) for v in cast(list[Any], value)):
            raise FormatError("depopulated balls must be text", file=file, locator=path)
    return cast(Any, value)


def parse_proposal(text: str, *, file: str = "") -> Proposal:
    try:
        data = tomllib.loads(text, parse_float=Decimal)
    except tomllib.TOMLDecodeError as error:
        raise FormatError(f"not TOML: {error}", file=file) from None
    _table(data, file, "", ROOT_KEYS)
    schema = data.get("schema")
    if (
        isinstance(schema, str)
        and re.fullmatch(r"fenolite\.proposal\.v\d+", schema)
        and int(schema.rsplit("v", 1)[1]) > 0
    ):
        raise ProposalTooNew("proposal schema is newer than supported", file=file, locator="schema")
    if schema != SCHEMA:
        raise FormatError(f"schema must be {SCHEMA}", file=file, locator="schema")
    ds = _table(data.get("datasheet"), file, "datasheet", {"file", "sha256", "revision", "title"})
    name = _text(ds.get("file"), file, "datasheet.file")
    if Path(name).name != name or "/" in name or "\\" in name or ":" in name:
        raise FormatError("datasheet.file must be a basename", file=file, locator="datasheet.file")
    if not isinstance(ds.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", ds["sha256"]):
        raise FormatError("must be a 64-hex SHA-256", file=file, locator="datasheet.sha256")
    for key in ("revision", "title"):
        if key in ds:
            _text(ds[key], file, "datasheet." + key, empty=True)
    author = _table(data.get("proposer"), file, "proposer", {"kind", "name", "date"})
    if not isinstance(author.get("kind"), str) or author["kind"] not in {"agent", "person", "tool"}:
        raise FormatError("proposer.kind must be agent, person or tool", file=file, locator="proposer.kind")
    _text(author.get("name"), file, "proposer.name")
    try:
        datetime.date.fromisoformat(author.get("date", ""))
    except (TypeError, ValueError):
        raise FormatError("must be an ISO date", file=file, locator="proposer.date") from None
    device = _table(
        data.get("device"), file, "device", {"id", "manufacturer", "mpn", "summary", "ref_prefix", "cite"}
    )
    if (
        not isinstance(device.get("id"), str)
        or not re.fullmatch(r"[A-Za-z0-9_.+-]+:[A-Za-z0-9_.+-]+", device["id"])
        or device["id"].startswith("Fenolite:")
    ):
        raise FormatError("must name a project NS:NAME", file=file, locator="device.id")
    for key in ("manufacturer", "mpn", "summary"):
        _text(device.get(key, ""), file, "device." + key, empty=True)
    if not isinstance(device.get("ref_prefix", "U"), str) or not re.fullmatch(
        r"[A-Z][A-Z_]*", device.get("ref_prefix", "U")
    ):
        raise FormatError("must be a reference prefix", file=file, locator="device.ref_prefix")
    _cite(device, file, "device")
    package = _table(
        data.get("package"),
        file,
        "package",
        set[str]().union(
            *(set(keys) for keys in FAMILY_KEYS.values()), {"family", "cite", "land", "row_labels", "pins"}
        ),
    )
    family = _text(package.get("family", ""), file, "package.family", empty=True)
    keys = FAMILY_KEYS.get(family)
    parameter_keys = keys or {
        key: spec for family_keys in FAMILY_KEYS.values() for key, spec in family_keys.items()
    }
    if keys is not None:
        _table(
            package,
            file,
            "package",
            set(keys) | {"family", "cite", "land", "row_labels"} | ({"pins"} if family == "grid" else set()),
        )
        for key, spec in keys.items():
            if spec.required and key not in package:
                raise FormatError("required key is missing", file=file, locator="package." + key)
    quantities: dict[str, LengthRange] = {}
    issues: list[Issue] = []
    parameters = {
        key: _parameter(
            value,
            parameter_keys.get(key, Key("count")),
            "package." + key,
            file,
            quantities,
            issues,
            strict=keys is not None,
        )
        for key, value in package.items()
        if key not in {"family", "cite", "land", "row_labels"}
    }
    _cite(package, file, "package")
    if "row_labels" in package:
        labels = package["row_labels"]
        if (
            family != "grid"
            or not isinstance(labels, list)
            or any(not isinstance(v, str) or not re.fullmatch(r"[A-Z]+", v) for v in cast(list[Any], labels))
        ):
            raise FormatError(
                "row_labels is an array of grid row letters", file=file, locator="package.row_labels"
            )
    if "land" in package:
        land_keys = LAND_KEYS.get(family) or {
            key: spec for options in LAND_KEYS.values() for key, spec in options.items()
        }
        land = _table(package["land"], file, "package.land", set(land_keys) | {"cite"})
        if "source" in land:
            raise FormatError("land source comes from its citation", file=file, locator="package.land.source")
        for key, spec in land_keys.items():
            if keys is not None and key != "source" and spec.required and key not in land:
                raise FormatError("required key is missing", file=file, locator="package.land." + key)
        parameters["land"] = {
            key: _parameter(
                value,
                land_keys[key],
                "package.land." + key,
                file,
                quantities,
                issues,
                strict=keys is not None,
            )
            for key, value in land.items()
            if key != "cite"
        }
        _cite(land, file, "package.land")
    for index, row in enumerate(_rows(data, "pin", file)):
        path = f"pin[{index}]"
        _table(row, file, path, PIN_KEYS)
        for key in ("number", "name", "type"):
            _text(row.get(key), file, path + "." + key)
        choices = (
            (row["type"], PIN_TYPES),
            (row.get("group", ""), GROUPS | {""}),
            (row.get("side", ""), SIDES | {""}),
            (row.get("shape", "line"), PIN_SHAPES),
        )
        if any(not isinstance(value, str) or value not in allowed for value, allowed in choices):
            raise FormatError("unknown pin type, group, side or shape", file=file, locator=path)
        for key in ("unit",):
            if key in row and (type(row[key]) is not int or row[key] < 1):
                raise FormatError("must be positive", file=file, locator=path + "." + key)
        if "hidden" in row and type(row["hidden"]) is not bool:
            raise FormatError("must be boolean", file=file, locator=path + ".hidden")
        for key in ("bus",):
            if key in row:
                _text(row[key], file, path + "." + key)
        for alt in _rows(row, "alternates", file):
            _table(alt, file, path + ".alternates", {"name", "type", "shape"})
            _text(alt.get("name"), file, path + ".alternates.name")
            choices = ((alt.get("type", row["type"]), PIN_TYPES), (alt.get("shape", "line"), PIN_SHAPES))
            if any(not isinstance(value, str) or value not in allowed for value, allowed in choices):
                raise FormatError("invalid alternate", file=file, locator=path)
        if "stacked" in row and (
            not isinstance(row["stacked"], list)
            or any(not isinstance(v, str) for v in cast(list[Any], row["stacked"]))
        ):
            raise FormatError("stacked must be pin numbers", file=file, locator=path)
        _cite(row, file, path)
    for key, row in _table(data.get("ratings", {}), file, "ratings", set(RATING_UNITS)).items():
        if key not in RATING_UNITS:
            raise FormatError("unknown rating", file=file, locator="ratings." + key)
        row = _table(row, file, "ratings." + key, {"min", "max", "cite", "limit"})
        if not ({"min", "max"} & row.keys()):
            raise FormatError("rating needs a bound", file=file, locator="ratings." + key)
        for bound in ("min", "max"):
            if bound in row:
                try:
                    micro_units(RATING_UNITS[key], _text(row[bound], file, "ratings." + key + "." + bound))
                except QuantityError as error:
                    raise FormatError(str(error), file=file, locator="ratings." + key + "." + bound) from None
        if not isinstance(row.get("limit", "abs_max"), str) or row.get("limit", "abs_max") not in {
            "abs_max",
            "operating",
        }:
            raise FormatError("unknown limit kind", file=file, locator="ratings." + key)
        _cite(row, file, "ratings." + key)
    for index, row in enumerate(_rows(data, "part", file)):
        _table(
            row,
            file,
            f"part[{index}]",
            {"mpn", "packing", "manufacturer", "summary", "lifecycle", "grade", "datasheet", "cite"},
        )
        for key, value in row.items():
            if key != "cite":
                _text(value, file, f"part[{index}].{key}")
        _text(row.get("mpn"), file, f"part[{index}].mpn")
        _cite(row, file, f"part[{index}]")
    for index, row in enumerate(_rows(data, "doubt", file)):
        _table(row, file, f"doubt[{index}]", {"field", "reason"})
        for key in ("field", "reason"):
            _text(row.get(key), file, f"doubt[{index}].{key}")
    return Proposal(data, parameters, quantities, tuple(issues), file)


def inline(value: Any) -> str:
    if isinstance(value, dict):
        return (
            "{ "
            + ", ".join(
                f"{json.dumps(k)} = {inline(v)}" for k, v in sorted(cast(dict[str, Any], value).items())
            )
            + " }"
        )
    if isinstance(value, list):
        return "[" + ", ".join(inline(v) for v in cast(list[Any], value)) + "]"
    if isinstance(value, (str, int, bool)):
        return json.dumps(value, ensure_ascii=False)
    raise FormatError(f"unsupported TOML value {type(value).__name__}")


def proposal_text(proposal: Proposal) -> str:
    """Canonical TOML: fixed root order, sorted table keys, arrays in their declared order."""
    _table(proposal.data, proposal.file, "", ROOT_KEYS)
    return (
        "\n".join(
            f"{key} = {inline(proposal.data[key])}"
            for key in (
                "schema",
                "datasheet",
                "proposer",
                "device",
                "package",
                "pin",
                "ratings",
                "part",
                "doubt",
            )
            if key in proposal.data
        )
        + "\n"
    )


def datasheet_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise FormatError("datasheet must start with %PDF-", file=path.name)
    return data


def skeleton(name: str, data: bytes) -> str:
    raw: dict[str, Any] = {
        "schema": SCHEMA,
        "datasheet": {"file": name, "sha256": hashlib.sha256(data).hexdigest(), "revision": "", "title": ""},
        "proposer": {"kind": "person", "name": "proposer-name", "date": "1970-01-01"},
        "device": {"id": "Proposed:NAME", "manufacturer": "", "mpn": "", "summary": "", "ref_prefix": "U"},
        "package": {"family": ""},
        "pin": [],
        "ratings": {},
        "part": [],
        "doubt": [],
    }
    comments = [
        "# Fill printed values and cite = {page = N, table = NAME} or figure = NAME.",
        "# The placeholder date and identity must be replaced; no geometry or guessed values.",
        "# pin: number, name, type; optional group/side/unit/bus/shape/hidden/stacked/alternates/cite.",
        "# ratings: vin/vout/voltage/current/power/temperature, min/max text with units, limit and cite.",
        "# part: mpn, packing/manufacturer/summary/lifecycle/grade/datasheet and cite.",
        "# doubt: field and reason; keep every unreadable fact open.",
    ]
    for family, keys in FAMILY_KEYS.items():
        comments.append(
            f"# package {family}: "
            + ", ".join(sorted(keys))
            + "; land: "
            + ", ".join(sorted(LAND_KEYS[family]))
        )
    return "\n".join(comments) + "\n" + proposal_text(Proposal(raw, {}, {}))
