# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fact tables of docs/formats/kicad/*.md (capability kicad-sexpr) and docs/formats/altium/*.md
(capability altium-build, "Building for Altium is documented"): sources, labels and hypotheses; and the
figure tables of docs/formats/sheets.md (change c0012): a registered source id per row.

A fact table has the header ``| fact | source | label | hypothesis |``. Every row cites an S-id, its
label is a value of ``fenolite.core.evidence.Level`` (optionally followed by a parenthesised scope,
such as ``KICAD-VERIFIED (10.0.x)``), and a row that is neither ``KICAD-VERIFIED`` nor
``CORPUS-VERIFIED`` names a hypothesis (``H-K-SEXPR-*`` or ``H-K-FMT-*`` on the S-expression page,
``H-A-SCH-*``, ``H-A-SCHBIN-*``, ``H-A-SCHLIB-*`` or ``H-A-PRJ-*`` on the Altium pages).
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
ALTIUM_PAGES = ROOT / "docs" / "formats" / "altium"
HEADER = ["fact", "source", "label", "hypothesis"]
VERIFIED = {Level.KICAD_VERIFIED.value, Level.CORPUS_VERIFIED.value}
HYPOTHESIS_IDS: dict[str, str] = {
    "sexpr.md": r"\bH-K-(SEXPR|FMT)-[A-Z0-9-]+\b",
    "project.md": r"\bH-K-(PRO-[A-Z0-9-]+|TOK-RULES-SILENT)\b",
}
ANY_HYPOTHESIS = r"\bH-[A-Z]-[A-Z0-9-]+\b"
ALTIUM_HYPOTHESES = r"\bH-A-(SCH|SCHBIN|SCHLIB|PRJ|PCB)-[A-Z0-9-]+\b"
"""Every row of an Altium page below the verified levels names one of the writer's hypotheses (c0032,
c0033, c0034, c0035)."""


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


def table_problems(name: str, text: str, hypotheses: str | None = None) -> list[str]:
    """Problems of the fact tables of the page ``name``; ``hypotheses`` overrides the per-page pattern."""
    wanted = hypotheses or HYPOTHESIS_IDS.get(name, ANY_HYPOTHESIS)
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
        elif level not in VERIFIED and not re.search(wanted, hypothesis):
            problems.append(f"{where}: {level} row names no hypothesis")
    return problems


def test_fact_tables() -> None:
    problems: list[str] = []
    for page in sorted(PAGES.glob("*.md")):
        problems += table_problems(page.name, page.read_text(encoding="utf-8"))
    assert not problems, "\n".join(problems)


def test_altium_fact_tables() -> None:
    pages = sorted(ALTIUM_PAGES.glob("*.md"))
    assert [p.name for p in pages] == [
        "compound-file.md",
        "pcb-copper.md",
        "pcb-document.md",
        "pcb-library.md",
        "pcb-records.md",
        "project.md",
        "schematic-ascii.md",
        "schematic-binary.md",
        "schematic-library.md",
    ]
    problems: list[str] = []
    for page in pages:
        text = page.read_text(encoding="utf-8")
        assert "| fact | source | label | hypothesis |" in text, page.name
        problems += table_problems(f"altium/{page.name}", text, ALTIUM_HYPOTHESES)
    assert not problems, "\n".join(problems)


def test_altium_pages_name_the_writer_hypotheses() -> None:
    """A row of an Altium page below the verified levels names ``H-A-SCH-*`` or ``H-A-PRJ-*``."""
    table = TABLE + "| a fact | S-0130 | INFERRED | H-K-PRO-MIN |\n"
    problems = table_problems("altium/project.md", table, ALTIUM_HYPOTHESES)
    assert problems == ["altium/project.md:3: INFERRED row names no hypothesis"]
    for ident in ("H-A-PRJ-OPEN", "H-A-SCH-NETS", "H-A-SCHBIN-CFB", "H-A-SCHLIB-PIN"):
        fixed = table.replace("H-K-PRO-MIN", ident)
        assert table_problems("altium/project.md", fixed, ALTIUM_HYPOTHESES) == []


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


S0150_PIN = "S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca)"


def test_library_page_pins_altiumsharp_to_version_1() -> None:
    """Every fact row of ``schematic-library.md`` that cites S-0150 names version 1 at the pinned commit
    (change c0034; LEGAL.md P1)."""
    text = (ALTIUM_PAGES / "schematic-library.md").read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("|") and "S-0150" in line]
    assert rows
    unpinned = [line for line in rows if line.count("S-0150") != line.count(S0150_PIN)]
    assert not unpinned, "\n".join(unpinned)


def test_pcb_pages_pin_altiumsharp_to_version_1() -> None:
    """Every fact row of the ``pcb-*.md`` pages that cites S-0150 names version 1 at the pinned commit, and
    ``pcb-library.md`` lists what version 2 alone gives (change c0035; LEGAL.md P1)."""
    for name in ("pcb-library.md", "pcb-records.md", "pcb-document.md", "pcb-copper.md"):
        text = (ALTIUM_PAGES / name).read_text(encoding="utf-8")
        rows = [line for line in text.splitlines() if line.startswith("|") and "S-0150" in line]
        unpinned = [line for line in rows if line.count("S-0150") != line.count(S0150_PIN)]
        assert not unpinned, "\n".join(unpinned)
    library = (ALTIUM_PAGES / "pcb-library.md").read_text(encoding="utf-8")
    assert library.count("## Version 2 not used") == 1
