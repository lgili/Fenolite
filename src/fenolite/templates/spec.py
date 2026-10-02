# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Sheet specification files (``*.sheet.toml``): a closed key set, exact millimetres and per-number
provenance (normative text: openspec capability ``sheet-templates``; user guide:
``docs/sheet-templates.md``).

Every problem is collected in file order and raised as one ``TemplateError``. Lengths are read with
``tomllib.loads(text, parse_float=Decimal)`` and converted to nanometres exactly; no float is created.
"""

from __future__ import annotations

import math
import os
import re
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.core.units import Nm
from fenolite.model.presentation import (
    PAPER_SIZES,
    Corner,
    HJustify,
    PaperSize,
    SheetPoint,
    split_tokens,
)

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "template.unknown-key": "error",
        "template.bad-value": "error",
        "template.resolution": "error",
        "template.unknown-token": "error",
        "template.unproven-value": "error",
        "template.cell-overlap": "error",
        "template.cell-outside": "error",
        "template.zone-letters": "error",
        "template.bitmap-not-png": "error",
        "template.too-wide": "warning",
    }
)
KEYS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "provenance": frozenset({"sources", "licence", "values"}),
        "sheet": frozenset(
            {"name", "sizes", "width", "height", "orientation", "text_size", "line_width", "text_line_width"}
        ),
        "margins": frozenset({"left", "right", "top", "bottom"}),
        "frame": frozenset(
            {"line_width", "zones", "zone_pitch", "zone_band", "zone_line_width", "zone_text_size"}
        ),
        "bitmap": frozenset({"path", "corner", "x", "y", "scale"}),
        "title_block": frozenset({"corner", "columns", "rows", "line_width", "label_size", "cell"}),
        "cell": frozenset({"row", "col", "span", "label", "token", "font_size", "justify"}),
    }
)
"""The closed key set of a specification (requirement "Sheet specification files")."""
SIZES: tuple[PaperSize, ...] = ("A0", "A1", "A2", "A3", "A4", "A5", "Letter", "Legal", "Tabloid", "custom")
CORNERS: tuple[Corner, ...] = ("lt", "lb", "rt", "rb")
JUSTIFIES: tuple[HJustify, ...] = ("left", "center", "right")
GRID_INDICES = frozenset({"row", "col", "span"})
MAX_ZONE_LETTERS = 8
"""``incrlabel`` does not skip letters, so the letters stop at ``H`` and ``I`` and ``O`` never occur."""
FENOLITE_CHOICE = "fenolite-choice"
_SOURCE_ID = re.compile(r"S-\d{4}")
_UM = 1_000
_MM = Decimal(1_000_000)


class TemplateError(FormatError):
    """A specification that cannot be built: every problem, one ``Issue`` each; ``locator`` is the key path
    of the first problem in file order."""

    def __init__(self, issues: tuple[Issue, ...], *, file: str = "") -> None:
        self.issues = issues
        summary = "; ".join(f"{i.code} at {i.where}: {i.message}" for i in issues)
        super().__init__(
            summary or "invalid specification", file=file, locator=issues[0].where if issues else ""
        )


@dataclass(frozen=True, slots=True)
class TitleCell:
    row: int
    col: int
    span: int = 1
    label: str = ""
    token: str = ""
    font_size: Nm | None = None
    justify: HJustify = "left"


@dataclass(frozen=True, slots=True)
class FrameSpec:
    line_width: Nm
    zones: bool = False
    zone_pitch: Nm = 0
    zone_band: Nm = 0
    zone_line_width: Nm = 0
    zone_text_size: Nm = 0


@dataclass(frozen=True, slots=True)
class TitleBlockSpec:
    corner: Corner
    columns: tuple[Nm, ...]
    rows: tuple[Nm, ...]
    line_width: Nm
    label_size: Nm
    cells: tuple[TitleCell, ...] = ()


@dataclass(frozen=True, slots=True)
class BitmapSpec:
    path: str
    pos: SheetPoint
    scale_ppm: int = 1_000_000


@dataclass(frozen=True, slots=True)
class SheetSpec:
    name: str
    sizes: tuple[PaperSize, ...]
    portrait: bool
    width: Nm | None
    height: Nm | None
    margins: tuple[Nm, Nm, Nm, Nm]
    """Left, right, top and bottom margins."""
    text_size: Nm
    line_width: Nm
    text_line_width: Nm
    frame: FrameSpec
    title_block: TitleBlockSpec | None = None
    bitmap: BitmapSpec | None = None
    provenance: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    """Key path → ``fenolite-choice`` or a source id (``[provenance.values]``)."""
    sources: tuple[str, ...] = ()
    licence: str = ""


def page_size(spec: SheetSpec, size: PaperSize) -> tuple[Nm, Nm]:
    """The page of ``size`` in the specified orientation (``custom``: the specified width and height)."""
    if size == "custom":
        assert spec.width is not None and spec.height is not None
        return spec.width, spec.height
    short, long = PAPER_SIZES[size]
    return (short, long) if spec.portrait else (long, short)


class _Collector:
    """Problems in file order."""

    def __init__(self) -> None:
        self.issues: list[Issue] = []

    def add(self, code: str, where: str, message: str) -> None:
        self.issues.append(Issue(code, ISSUE_CODES[code], message, where=where))


def _length(value: Any, where: str, out: _Collector, *, positive: bool = True) -> Nm | None:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        out.add("template.bad-value", where, f"expected a length in millimetres, got {value!r}")
        return None
    nm = Decimal(value) * _MM
    if positive and nm <= 0 or nm < 0:
        out.add(
            "template.bad-value", where, f"expected a {'positive' if positive else 'non-negative'} length"
        )
        return None
    if nm != nm.to_integral_value() or int(nm) % _UM:
        out.add("template.resolution", where, f"{value} mm is not a whole number of micrometres")
        return None
    return int(nm)


def _string(value: Any, where: str, out: _Collector) -> str | None:
    if not isinstance(value, str):
        out.add("template.bad-value", where, f"expected a string, got {value!r}")
        return None
    return value


def _choice(value: Any, choices: tuple[str, ...], where: str, out: _Collector) -> str | None:
    if value not in choices:
        out.add("template.bad-value", where, f"expected one of {', '.join(choices)}, got {value!r}")
        return None
    return cast(str, value)


def _integer(value: Any, where: str, out: _Collector, *, minimum: int = 0) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        out.add("template.bad-value", where, f"expected an integer of at least {minimum}, got {value!r}")
        return None
    return value


def _table(data: Mapping[str, Any], name: str, out: _Collector, *, required: bool) -> Mapping[str, Any]:
    value = data.get(name)
    if value is None:
        if required:
            out.add("template.bad-value", name, f"the table [{name}] is required")
        return {}
    if not isinstance(value, dict):
        out.add("template.bad-value", name, f"[{name}] must be a table")
        return {}
    table = cast(dict[str, Any], value)
    for key in table:
        if key not in KEYS[name]:
            out.add("template.unknown-key", f"{name}.{key}", f"unknown key {key!r} in [{name}]")
    return table


_MISSING = object()


def _field(
    table: Mapping[str, Any],
    key: str,
    where: str,
    out: _Collector,
    convert: Callable[[Any, str, _Collector], Any],
    default: Any = _MISSING,
) -> Any:
    """``convert`` of ``table[key]``; a missing key gives ``default``, or a ``bad-value`` when required."""
    if key not in table:
        if default is _MISSING:
            out.add("template.bad-value", where, f"{where} is required")
            return None
        return default
    return convert(table[key], where, out)


def _non_negative(value: Any, where: str, out: _Collector) -> Nm | None:
    return _length(value, where, out, positive=False)


def _numeric_paths(data: Mapping[str, Any], prefix: str = "") -> list[str]:
    """Key paths whose value is a number or an array of numbers (array-of-table items by index)."""
    paths: list[str] = []
    for key, value in data.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            paths += _numeric_paths(cast(dict[str, Any], value), f"{path}.")
        elif isinstance(value, list) and value and all(isinstance(v, dict) for v in cast(list[Any], value)):
            for i, item in enumerate(cast(list[dict[str, Any]], value)):
                paths += _numeric_paths(item, f"{path}[{i}].")
        elif _is_number(value) or (
            isinstance(value, list) and value and all(_is_number(v) for v in cast(list[Any], value))
        ):
            if key not in GRID_INDICES:
                paths.append(path)
    return paths


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, Decimal)) and not isinstance(value, bool)


def _parse(text: str, file: str) -> dict[str, Any]:
    try:
        return tomllib.loads(text, parse_float=Decimal)
    except tomllib.TOMLDecodeError as exc:
        issue = Issue("template.bad-value", "error", f"TOML syntax error: {exc}", where="")
        raise TemplateError((issue,), file=file) from None


def load_spec(
    source: str | os.PathLike[str], *, file: str = "", require_provenance: bool = False
) -> SheetSpec:
    """A ``SheetSpec`` from a ``*.sheet.toml`` path or its text; raises one ``TemplateError`` naming every
    problem."""
    if isinstance(source, str):
        text = source
    else:
        path = Path(source)
        text = path.read_text(encoding="utf-8")
        file = file or os.fspath(path)
    data = _parse(text, file)
    out = _Collector()
    for key in data:
        if key not in ("provenance", "sheet", "margins", "frame", "bitmap", "title_block"):
            out.add("template.unknown-key", key, f"unknown table or key {key!r}")
    tables = {name: _table(data, name, out, required=name in ("sheet", "margins", "frame"))
              for name in ("provenance", "sheet", "margins", "frame", "bitmap", "title_block")}  # fmt: skip
    spec = _build(data, tables, out)
    if require_provenance:
        _check_provenance(data, tables["provenance"], out)
    if out.issues or spec is None:
        raise TemplateError(_file_order(text, tuple(out.issues)), file=file)
    return spec


def _file_order(text: str, issues: tuple[Issue, ...]) -> tuple[Issue, ...]:
    """Issues sorted by where their key path first appears in the text (stable for ties)."""
    lines = text.splitlines()

    def position(issue: Issue) -> int:
        parts = re.split(r"[.\[\]]+", issue.where)
        table, key = (parts[0], parts[-1]) if parts else ("", "")
        start = 0
        for n, line in enumerate(lines):
            if re.match(rf"\s*\[\[?{re.escape(table)}(\]|\.)", line):
                start = n
                break
        for n in range(start, len(lines)):
            if re.match(rf"\s*{re.escape(key)}\s*=", lines[n]):
                return n
        return start

    return tuple(sorted(issues, key=position))


def _build(
    data: Mapping[str, Any], tables: Mapping[str, Mapping[str, Any]], out: _Collector
) -> SheetSpec | None:
    sheet, margins, frame = tables["sheet"], tables["margins"], tables["frame"]
    name = _field(sheet, "name", "sheet.name", out, _string) if sheet else None
    sizes: list[PaperSize] = []
    raw_sizes = _field(sheet, "sizes", "sheet.sizes", out, lambda v, w, o: v) if sheet else None
    if raw_sizes is not None:
        if not isinstance(raw_sizes, list) or not raw_sizes:
            out.add("template.bad-value", "sheet.sizes", "expected a non-empty list of sizes")
        else:
            for i, size in enumerate(cast(list[Any], raw_sizes)):
                found = _choice(size, SIZES, f"sheet.sizes[{i}]", out)
                if found is not None:
                    sizes.append(cast(PaperSize, found))
    custom = "custom" in sizes
    dims: dict[str, Nm | None] = {}
    for key in ("width", "height"):
        if custom:
            dims[key] = _field(sheet, key, f"sheet.{key}", out, _length)
        else:
            dims[key] = None
            if key in sheet:
                out.add(
                    "template.bad-value", f"sheet.{key}", f"sheet.{key} is given only when 'custom' is listed"
                )
    width, height = dims["width"], dims["height"]
    orientation = _choice(
        sheet.get("orientation", "landscape"), ("landscape", "portrait"), "sheet.orientation", out
    )
    lengths = {k: _field(sheet, k, f"sheet.{k}", out, _length) if sheet else None
               for k in ("text_size", "line_width", "text_line_width")}  # fmt: skip
    margin = tuple(
        _field(margins, k, f"margins.{k}", out, _non_negative) if margins else None
        for k in ("left", "right", "top", "bottom")
    )
    frame_spec = _frame(frame, out)
    title = _title_block(tables["title_block"], out) if "title_block" in data else None
    bitmap = _bitmap(tables["bitmap"], out) if "bitmap" in data else None
    provenance = tables["provenance"]
    values = provenance.get("values", {})
    sources = provenance.get("sources", [])
    if None in (name, orientation, *lengths.values(), *margin) or frame_spec is None or not sizes:
        return None
    if custom and (width is None or height is None):
        return None
    spec = SheetSpec(
        name=cast(str, name),
        sizes=tuple(sizes),
        portrait=orientation == "portrait",
        width=width,
        height=height,
        margins=cast(tuple[Nm, Nm, Nm, Nm], margin),
        text_size=cast(Nm, lengths["text_size"]),
        line_width=cast(Nm, lengths["line_width"]),
        text_line_width=cast(Nm, lengths["text_line_width"]),
        frame=frame_spec,
        title_block=title,
        bitmap=bitmap,
        provenance=MappingProxyType({str(k): str(v) for k, v in cast(dict[str, Any], values).items()})
        if isinstance(values, dict)
        else MappingProxyType({}),
        sources=tuple(str(s) for s in cast(list[Any], sources)) if isinstance(sources, list) else (),
        licence=str(provenance.get("licence", "")),
    )
    _check_zones(spec, out)
    _check_cells(spec, out)
    return spec


def _frame(frame: Mapping[str, Any], out: _Collector) -> FrameSpec | None:
    if not frame:
        return None
    line_width = _field(frame, "line_width", "frame.line_width", out, _length)
    zones = frame.get("zones", False)
    if not isinstance(zones, bool):
        out.add("template.bad-value", "frame.zones", f"expected true or false, got {zones!r}")
        zones = False
    values: dict[str, Nm | None] = {
        key: _field(frame, key, f"frame.{key}", out, _length, _MISSING if zones else 0)
        for key in ("zone_pitch", "zone_band", "zone_line_width", "zone_text_size")
    }
    for key in ("zone_pitch", "zone_band"):
        value = values[key]
        if value and value % (2 * _UM):
            out.add("template.resolution", f"frame.{key}", "half of it must be a whole number of micrometres")
    if line_width is None or None in values.values():
        return None
    return FrameSpec(line_width, zones, **cast(dict[str, Nm], values))


def _title_block(table: Mapping[str, Any], out: _Collector) -> TitleBlockSpec | None:
    corner = _choice(table.get("corner", "rb"), CORNERS, "title_block.corner", out)
    grids: dict[str, tuple[Nm, ...] | None] = {}
    for key in ("columns", "rows"):
        raw = _field(table, key, f"title_block.{key}", out, lambda v, w, o: v)
        if raw is None:
            grids[key] = None
        elif not isinstance(raw, list) or not raw:
            out.add("template.bad-value", f"title_block.{key}", "expected a non-empty list of lengths")
            grids[key] = None
        else:
            items = [_length(v, f"title_block.{key}", out) for v in cast(list[Any], raw)]
            grids[key] = None if None in items else tuple(cast(list[Nm], items))
    line_width = _field(table, "line_width", "title_block.line_width", out, _length)
    label_size = _field(table, "label_size", "title_block.label_size", out, _length)
    cells: list[TitleCell] = []
    raw_cells = table.get("cell", [])
    if not isinstance(raw_cells, list):
        out.add("template.bad-value", "title_block.cell", "expected an array of tables [[title_block.cell]]")
        raw_cells = []
    for i, raw in enumerate(cast(list[Any], raw_cells)):
        where = f"title_block.cell[{i}]"
        if not isinstance(raw, dict):
            out.add("template.bad-value", where, "expected a table")
            continue
        cell = cast(dict[str, Any], raw)
        for key in cell:
            if key not in KEYS["cell"]:
                out.add("template.unknown-key", f"{where}.{key}", f"unknown key {key!r} in a cell")
        row = _field(cell, "row", f"{where}.row", out, _integer)
        col = _field(cell, "col", f"{where}.col", out, _integer)
        span = _integer(cell.get("span", 1), f"{where}.span", out, minimum=1)
        label = _string(cell.get("label", ""), f"{where}.label", out)
        token = _string(cell.get("token", ""), f"{where}.token", out)
        if label:
            try:
                split_tokens(label)
            except ValueError as exc:
                out.add("template.unknown-token", f"{where}.label", str(exc))
                label = None
        if token:
            try:
                split_tokens(f"{{{token}}}")
            except ValueError as exc:
                out.add("template.unknown-token", f"{where}.token", str(exc))
                token = None
        font_size = _field(cell, "font_size", f"{where}.font_size", out, _length, None)
        justify = _choice(cell.get("justify", "left"), JUSTIFIES, f"{where}.justify", out)
        if None in (row, col, span, label, token, justify) or ("font_size" in cell and font_size is None):
            continue
        cells.append(
            TitleCell(
                cast(int, row),
                cast(int, col),
                cast(int, span),
                cast(str, label),
                cast(str, token),
                font_size,
                cast(HJustify, justify),
            )
        )
    if corner is None or None in grids.values() or line_width is None or label_size is None:
        return None
    return TitleBlockSpec(
        cast(Corner, corner),
        cast(tuple[Nm, ...], grids["columns"]),
        cast(tuple[Nm, ...], grids["rows"]),
        line_width,
        label_size,
        tuple(cells),
    )


def _bitmap(table: Mapping[str, Any], out: _Collector) -> BitmapSpec | None:
    path = _field(table, "path", "bitmap.path", out, _string)
    corner = _choice(table.get("corner", "rb"), CORNERS, "bitmap.corner", out)
    x = _length(table.get("x", 0), "bitmap.x", out, positive=False)
    y = _length(table.get("y", 0), "bitmap.y", out, positive=False)
    scale = table.get("scale", 1)
    ppm: int | None = None
    if not _is_number(scale) or Decimal(scale) <= 0:
        out.add("template.bad-value", "bitmap.scale", f"expected a positive number, got {scale!r}")
    else:
        value = Decimal(scale) * 1_000_000
        if value != value.to_integral_value():
            out.add(
                "template.bad-value", "bitmap.scale", f"{scale} is not a whole number of parts per million"
            )
        else:
            ppm = int(value)
    if path is not None and (
        os.path.isabs(path) or ".." in re.split(r"[/\\]", path) or re.match(r"^[A-Za-z]:", path)
    ):
        out.add(
            "template.bad-value", "bitmap.path", "expected a path relative to the specification, without '..'"
        )
        path = None
    if None in (path, corner, x, y, ppm):
        return None
    return BitmapSpec(
        cast(str, path), SheetPoint(cast(Corner, corner), cast(Nm, x), cast(Nm, y)), cast(int, ppm)
    )


def _check_zones(spec: SheetSpec, out: _Collector) -> None:
    if not spec.frame.zones or not spec.frame.zone_pitch:
        return
    _, _, top, bottom = spec.margins
    for size in spec.sizes:
        _, height = page_size(spec, size)
        rows = math.ceil((height - top - bottom) / spec.frame.zone_pitch)
        if rows > MAX_ZONE_LETTERS:
            message = (
                f"size {size} needs {rows} letter rows; at most {MAX_ZONE_LETTERS} (A to H) are possible"
            )
            out.add("template.zone-letters", "frame.zone_pitch", message)


def _check_cells(spec: SheetSpec, out: _Collector) -> None:
    block = spec.title_block
    if block is None:
        return
    taken: dict[tuple[int, int], int] = {}
    for i, cell in enumerate(block.cells):
        where = f"title_block.cell[{i}]"
        if cell.row >= len(block.rows) or cell.col + cell.span > len(block.columns):
            out.add(
                "template.cell-outside",
                where,
                f"the cell leaves the {len(block.rows)} × {len(block.columns)} grid",
            )
            continue
        for col in range(cell.col, cell.col + cell.span):
            if (cell.row, col) in taken:
                other = taken[(cell.row, col)]
                message = f"the cell covers row {cell.row}, column {col}, already covered by cell[{other}]"
                out.add("template.cell-overlap", where, message)
                break
            taken[(cell.row, col)] = i


def _check_provenance(data: Mapping[str, Any], provenance: Mapping[str, Any], out: _Collector) -> None:
    sources = provenance.get("sources", [])
    listed: set[str] = {str(s) for s in cast(list[Any], sources)} if isinstance(sources, list) else set()
    values = provenance.get("values", {})
    table = cast(dict[str, Any], values) if isinstance(values, dict) else {}
    if "licence" not in provenance:
        out.add("template.unproven-value", "provenance.licence", "[provenance] licence is required")
    checked = {k: v for k, v in data.items() if k != "provenance"}
    for path in _numeric_paths(checked):
        origin = table.get(path)
        if origin is None:
            out.add("template.unproven-value", path, f"{path} is missing from [provenance.values]")
        elif origin != FENOLITE_CHOICE and not (
            isinstance(origin, str) and _SOURCE_ID.fullmatch(origin) and origin in listed
        ):
            message = (
                f"{path} maps to {origin!r}: expected {FENOLITE_CHOICE!r} or a source of [provenance] sources"
            )
            out.add("template.unproven-value", path, message)


__all__ = [
    "FENOLITE_CHOICE",
    "ISSUE_CODES",
    "KEYS",
    "MAX_ZONE_LETTERS",
    "SIZES",
    "BitmapSpec",
    "FrameSpec",
    "SheetSpec",
    "TemplateError",
    "TitleBlockSpec",
    "TitleCell",
    "load_spec",
    "page_size",
]
