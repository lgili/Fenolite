# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Field evidence of the PCB reader (capability altium-pcb-reader, "Field evidence table", change c0041):
every typed field of every binary record has exactly one row in "Fields" of
``docs/formats/altium/pcb-read.md``, and ``FIELD_LEVELS`` holds the label of that row."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from pathlib import Path

import pytest

from fenolite.backends.altium.read.pcbprims import (
    BINARY_RECORDS,
    FIELD_LEVELS,
    UNTYPED,
    field_level,
    typed_fields,
)
from fenolite.core.evidence import Level

ROOT = Path(__file__).resolve().parents[5]
PAGE = ROOT / "docs" / "formats" / "altium" / "pcb-read.md"
HEADER = ["record", "field", "subrecord", "offset", "from length", "source", "label", "hypothesis"]
HYPOTHESIS = re.compile(r"^H-A-RD-PCB-[A-Z0-9-]+$")
ORACLE_TESTS = ("test_pcbdoc_read_oracle.py", "test_pcblib_read_oracle.py")


@dataclass(frozen=True)
class Row:
    record: str
    field: str
    source: str
    label: str
    hypothesis: str


def _level(cell: str) -> Level | None:
    for level in sorted(Level, key=lambda lv: -len(lv.value)):
        if cell == level.value or cell.startswith(level.value + " ") or cell.startswith(level.value + "("):
            return level
    return None


def field_rows(text: str) -> list[Row]:
    """The rows of the table "Fields"."""
    rows: list[Row] = []
    inside = False
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")] if line.startswith("|") else []
        if cells == HEADER:
            inside = True
            continue
        if not inside or not cells:
            inside = inside and bool(cells)
            continue
        if set(line.strip()) <= set("|- "):
            continue
        rows.append(Row(cells[0], cells[1], cells[5], cells[6], cells[7]))
    return rows


def field_problems(records: Iterable[type], rows: list[Row], levels: Mapping[str, Level]) -> list[str]:
    """A message naming the record and the field for each typed field without exactly one row, each row
    without a typed field, and each level that differs from its row's label."""
    typed = [f"{r.__name__}.{f.name}" for r in records for f in fields(r) if f.name not in UNTYPED]
    keys = [f"{row.record}.{row.field}" for row in rows]
    problems = [f"{key}: {keys.count(key)} rows" for key in typed if keys.count(key) != 1]
    problems += [f"{key}: a row without a typed field" for key in keys if key not in typed]
    for row in rows:
        key = f"{row.record}.{row.field}"
        if levels.get(key) != _level(row.label):
            problems.append(f"{key}: FIELD_LEVELS {levels.get(key)} differs from the label {row.label!r}")
    return problems


def test_table_and_code_agree() -> None:
    rows = field_rows(PAGE.read_text(encoding="utf-8"))
    assert len(rows) == len(typed_fields()) == len(FIELD_LEVELS)
    assert field_problems(BINARY_RECORDS, rows, FIELD_LEVELS) == []
    for row in rows:
        assert HYPOTHESIS.match(row.hypothesis), row
        sources = re.findall(r"S-\d{4}", row.source)
        assert sources != ["S-0173"], f"{row.record}.{row.field}: S-0173 is the only source"
        assert len(sources) >= 2 or "census" in row.source, f"{row.record}.{row.field}: one source, no check"
        if "S-0150" in row.source:
            assert "version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca" in row.source
        if _level(row.label) is Level.ORACLE_VERIFIED:
            assert any(name in row.source + row.label for name in ORACLE_TESTS), row
    assert field_level("TrackRecord", "x1") is FIELD_LEVELS["TrackRecord.x1"]


def test_a_field_without_a_row() -> None:
    @dataclass(frozen=True)
    class TrackRecord:
        raw: bytes
        x1: int
        brand_new: int

    rows = [Row("TrackRecord", "x1", "S-0160, S-0150", "INFERRED", "H-A-RD-PCB-KICAD-DOC")]
    problems = field_problems([TrackRecord], rows, {"TrackRecord.x1": Level.INFERRED})
    assert problems == ["TrackRecord.brand_new: 0 rows"]
    with pytest.raises(KeyError):
        field_level("TrackRecord", "brand_new")
