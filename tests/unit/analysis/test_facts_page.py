# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The table "Capacity fit" of ``docs/analyses.md`` equals the code, and nothing else is shipped
(capability board-analyses, "Coefficients are recorded with their sources" and "No shipped requirement
values"; change c0047)."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from fenolite.analysis import current, load_requirements

ROOT = Path(__file__).resolve().parents[3]
PAGE = ROOT / "docs" / "analyses.md"
SOURCES = ROOT / "docs" / "evidence" / "sources.md"
HYPOTHESES = ROOT / "docs" / "hypotheses.md"
EXAMPLE = ROOT / "tests" / "data" / "analysis" / "requirements_example.toml"
MARK = "authored for Fenolite; illustrative values, not requirements"
BARREL = "barrel_area_nm2"


def constants() -> dict[str, Decimal]:
    """Every ``FIT_*`` constant and ``MIL_NM`` of the module, as decimals."""
    return {
        name: Decimal(str(value))
        for name, value in vars(current).items()
        if (name.startswith("FIT_") or name == "MIL_NM") and isinstance(value, (int, Decimal))
    }


def table(text: str) -> list[list[str]]:
    """The cells of the rows of the table under the heading "Capacity fit"."""
    section = text.split("### Capacity fit", 1)[1].split("\n### ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("|")]
    return [[cell.strip() for cell in row.strip().strip("|").split("|")] for row in rows[2:]]


def page_problems(text: str) -> list[str]:
    sources = set(re.findall(r"^\| (S-\d{4}) \|", SOURCES.read_text(encoding="utf-8"), re.MULTILINE))
    hypotheses = set(
        re.findall(r"^\| (H-[A-Z0-9-]+) \|", HYPOTHESES.read_text(encoding="utf-8"), re.MULTILINE)
    )
    problems: list[str] = []
    seen: dict[str, int] = {}
    for cells in table(text):
        if len(cells) != 7:
            problems.append(f"{cells[0]}: a row has seven cells")
            continue
        name = cells[0].strip("`")
        seen[name] = seen.get(name, 0) + 1
        value, source, level, hypothesis = cells[1], cells[4], cells[5], cells[6]
        if source not in sources:
            problems.append(f"{name}: source {source!r} is not registered")
        if level != "INFERRED":
            problems.append(f"{name}: level must be INFERRED")
        if hypothesis not in hypotheses:
            problems.append(f"{name}: hypothesis {hypothesis!r} is not registered")
        wanted = constants().get(name)
        if wanted is not None and Decimal(value) != wanted:
            problems.append(f"{name}: the page says {value}, the code {wanted}")
        elif wanted is None and name != BARREL:
            problems.append(f"{name}: no such constant in fenolite.analysis.current")
    for name in (*constants(), BARREL):
        if seen.get(name, 0) != 1:
            problems.append(f"{name}: needs exactly one row, found {seen.get(name, 0)}")
    return problems


def test_table_equals_the_code() -> None:
    assert len(constants()) == 9
    assert page_problems(PAGE.read_text(encoding="utf-8")) == []


def test_unsourced_constant_fails() -> None:
    text = PAGE.read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| `FIT_EXP_AREA`"))
    cells = row.split("|")
    cells[5] = "  "
    assert page_problems(text.replace(row, "|".join(cells))) == ["FIT_EXP_AREA: source '' is not registered"]


def test_changed_value_and_missing_row_fail() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert page_problems(text.replace("| 0.725 |", "| 0.7 |")) == [
        "FIT_EXP_AREA: the page says 0.7, the code 0.725"
    ]
    row = next(line for line in text.splitlines() if line.startswith("| `MIL_NM`"))
    assert page_problems(text.replace(row + "\n", "")) == ["MIL_NM: needs exactly one row, found 0"]


def test_page_states_the_attribution_and_the_limits() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "attributes the fit\nto a standard" in text and "did not consult that standard" in text
    for limit in ("Holes", "Solder mask", "third net", "Fenolite measures; you decide"):
        assert limit in text, limit
    for analysis in ("capacity of tracks", "clearance on a layer", "creepage", "clearance across the edge"):
        assert f"| {analysis}" in text, analysis


def test_no_data_files() -> None:
    package = ROOT / "src" / "fenolite" / "analysis"
    names = sorted(p.name for p in package.iterdir() if p.name != "__pycache__")
    assert all(name.endswith(".py") or name == "PROVENANCE.md" for name in names), names
    assert "file" in load_requirements.__kwdefaults__ and load_requirements.__defaults__ is None


def test_example_is_marked_as_authored() -> None:
    first = EXAMPLE.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("#") and MARK in first
    assert MARK in PAGE.read_text(encoding="utf-8")
