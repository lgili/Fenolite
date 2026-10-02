# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fact tables of docs/formats/kicad/*.md (capability kicad-sexpr): sources, labels and hypotheses; and
the figure tables of docs/formats/sheets.md (change c0012): a registered source id per row.

A fact table has the header ``| fact | source | label | hypothesis |``. Every row cites an S-id, its
label is a value of ``fenolite.core.evidence.Level`` (optionally followed by a parenthesised scope,
such as ``KICAD-VERIFIED (10.0.x)``), and a row that is neither ``KICAD-VERIFIED`` nor
``CORPUS-VERIFIED`` names a hypothesis (``H-K-SEXPR-*`` or ``H-K-FMT-*`` on the S-expression page).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from fenolite.core.evidence import Level

ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / "docs" / "formats" / "kicad"
SHEETS_PAGE = ROOT / "docs" / "formats" / "sheets.md"
SOURCES = ROOT / "docs" / "evidence" / "sources.md"
HEADER = ["fact", "source", "label", "hypothesis"]
VERIFIED = {Level.KICAD_VERIFIED.value, Level.CORPUS_VERIFIED.value}
HYPOTHESIS_IDS: dict[str, str] = {
    "sexpr.md": r"\bH-K-(SEXPR|FMT)-[A-Z0-9-]+\b",
    "project.md": r"\bH-K-(PRO-[A-Z0-9-]+|TOK-RULES-SILENT)\b",
}
ANY_HYPOTHESIS = r"\bH-[A-Z]-[A-Z0-9-]+\b"


def _cells(line: str) -> list[str]:
    """Split a table row on unescaped pipes."""
    inner = line.strip()
    inner = inner[1:] if inner.startswith("|") else inner
    inner = inner[:-1] if inner.endswith("|") and not inner.endswith("\\|") else inner
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", inner)]


def _label(cell: str) -> str | None:
    """The Level value of a label cell, or None when the cell is not a label."""
    for level in sorted(Level, key=lambda lv: -len(lv.value)):
        if cell == level.value or re.fullmatch(re.escape(level.value) + r"(\(\S+\))?( \(.+\))?", cell):
            return level.value
    return None


def table_problems(name: str, text: str) -> list[str]:
    problems: list[str] = []
    in_table = False
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.startswith("|"):
            in_table = False
            continue
        cells = _cells(line)
        if cells == HEADER:
            in_table = True
            continue
        if not in_table or set(line.replace("|", "").strip()) <= {"-", " "}:
            continue
        where = f"{name}:{number}"
        if len(cells) != 4:
            problems.append(f"{where}: expected 4 cells, found {len(cells)}")
            continue
        _fact, source, label, hypothesis = cells
        if not re.search(r"\bS-\d{4}\b", source):
            problems.append(f"{where}: no source id (S-NNNN)")
        level = _label(label)
        if level is None:
            problems.append(f"{where}: label {label!r} is not a fenolite.core.evidence.Level value")
        elif level not in VERIFIED and not re.search(HYPOTHESIS_IDS.get(name, ANY_HYPOTHESIS), hypothesis):
            problems.append(f"{where}: {level} row names no hypothesis")
    return problems


def test_fact_tables() -> None:
    problems: list[str] = []
    for page in sorted(PAGES.glob("*.md")):
        problems += table_problems(page.name, page.read_text(encoding="utf-8"))
    assert not problems, "\n".join(problems)


def test_sexpr_page_has_a_fact_table() -> None:
    text = (PAGES / "sexpr.md").read_text(encoding="utf-8")
    assert "| fact | source | label | hypothesis |" in text


TABLE = "| fact | source | label | hypothesis |\n|---|---|---|---|\n"


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ("| a | S-0020 | INFERRED | H-K-SEXPR-LEX-10 |", None),
        ("| a | S-0020 | KICAD-VERIFIED (10.0.x) |  |", None),
        ("| a \\| b | S-0020 | CORPUS-VERIFIED | — |", None),
        ("| a | S-0020 |  | H-K-SEXPR-LEX-10 |", "is not a fenolite.core.evidence.Level value"),
        ("| a | S-0020 | INFERRED |  |", "names no hypothesis"),
        ("| a | S-0020 | INFERRED | H-G-ROT-DIR |", "names no hypothesis"),
        ("| a | docs | INFERRED | H-K-FMT-INDENT |", "no source id"),
    ],
)
def test_row_rules(row: str, expected: str | None) -> None:
    problems = table_problems("sexpr.md", TABLE + row + "\n")
    if expected is None:
        assert problems == []
    else:
        assert len(problems) == 1 and expected in problems[0] and "sexpr.md:3" in problems[0]


def test_project_page_names_its_own_hypotheses() -> None:
    """A ``project.md`` row below the verified levels names ``H-K-PRO-*`` or ``H-K-TOK-RULES-SILENT``."""
    header = "| fact | source | label | hypothesis |\n|---|---|---|---|\n"
    table = header + "| a fact | S-0045 | INFERRED | H-K-SEXPR-STRICT |\n"
    assert table_problems("project.md", table) == ["project.md:3: INFERRED row names no hypothesis"]
    ok = table.replace("H-K-SEXPR-STRICT", "H-K-PRO-MIN")
    assert table_problems("project.md", ok) == []


def registered_sources(text: str) -> set[str]:
    """The ids of the rows of ``docs/evidence/sources.md``."""
    return set(re.findall(r"^\| (S-\d{4}) \|", text, flags=re.MULTILINE))


def sheets_problems(text: str, registered: set[str], name: str = "sheets.md") -> list[str]:
    """Every row of every table in ``sheets.md`` cites a registered source id."""
    problems: list[str] = []
    header = True
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.startswith("|"):
            header = True
            continue
        if header:  # the first row of a table is its header
            header = False
            continue
        if set(line.replace("|", "").strip()) <= {"-", " "}:
            continue
        ids = re.findall(r"\bS-\d{4}\b", line)
        if not ids:
            problems.append(f"{name}:{number}: no source id (S-NNNN)")
        unknown = [sid for sid in ids if sid not in registered]
        problems += [f"{name}:{number}: {sid} is not registered in sources.md" for sid in unknown]
    return problems


def test_collected_pages_include_the_sheet_pages() -> None:
    names = {page.name for page in PAGES.glob("*.md")}
    assert "worksheet.md" in names
    assert SHEETS_PAGE.is_file()


def test_sheets_page_rows_cite_registered_sources() -> None:
    registered = registered_sources(SOURCES.read_text(encoding="utf-8"))
    problems = sheets_problems(SHEETS_PAGE.read_text(encoding="utf-8"), registered)
    assert not problems, "\n".join(problems)


def test_sheets_rows_without_registered_source_refused() -> None:
    table = "| size | width × height (mm) | source |\n|---|---|---|\n"
    assert sheets_problems(table + "| A4 | 210 × 297 | S-0077 |\n", {"S-0077"}) == []
    assert sheets_problems(table + "| A4 | 210 × 297 | fenolite-choice |\n", {"S-0077"}) == [
        "sheets.md:3: no source id (S-NNNN)"
    ]
    assert sheets_problems(table + "| A4 | 210 × 297 | S-9999 |\n", {"S-0077"}) == [
        "sheets.md:3: S-9999 is not registered in sources.md"
    ]


def test_worksheet_row_without_hypothesis_refused() -> None:
    table = TABLE + "| a corner fact | S-0035 | INFERRED |  |\n"
    assert table_problems("worksheet.md", table) == ["worksheet.md:3: INFERRED row names no hypothesis"]
