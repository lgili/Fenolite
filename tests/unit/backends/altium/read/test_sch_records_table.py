# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``RECORD_TYPES`` and every class's ``MODELED`` equal the tables of
``docs/formats/altium/schematic-records.md`` (capability altium-schematic-reader, "Table and page agree")."""

from __future__ import annotations

import re
from pathlib import Path

from fenolite.backends.altium.read.sch.records import BASE_FIELDS, RECORD_TYPES
from fenolite.core.evidence import Level
from fenolite.verify import load_register

ROOT = Path(__file__).resolve().parents[5]
PAGE = ROOT / "docs" / "formats" / "altium" / "schematic-records.md"
SOURCES = ROOT / "docs" / "evidence" / "sources.md"
REGISTER = ROOT / "docs" / "hypotheses.md"
HEADER = ["key", "type", "default", "attribute", "source", "label", "hypothesis"]
HEADING = re.compile(r"^### (\d+) `(\w+)`$")


def _cells(line: str) -> list[str]:
    inner = line.strip().strip("|")
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", inner)]


def page_tables(text: str) -> dict[str, tuple[str, list[list[str]]]]:
    """Section → (class name, rows) for "Every record" (``"base"``) and each "### <id> `<Class>`" section."""
    tables: dict[str, tuple[str, list[list[str]]]] = {}
    current: str | None = None
    for line in text.splitlines():
        heading = HEADING.match(line)
        if heading:
            current = heading.group(1)
            tables[current] = (heading.group(2), [])
            continue
        if line == "## Every record":
            current = "base"
            tables[current] = ("SchRecord", [])
            continue
        if line.startswith("## "):
            current = None
            continue
        if current is None or not line.startswith("|"):
            continue
        cells = _cells(line)
        if cells == HEADER or set(line.replace("|", "").strip()) <= {"-", " "}:
            continue
        tables[current][1].append(cells)
    return tables


def table_problems(text: str) -> list[str]:
    sources = set(re.findall(r"^\| (S-\d{4}) \|", SOURCES.read_text(encoding="utf-8"), flags=re.M))
    registered = {row.id for row in load_register(REGISTER)}
    labels = {level.value for level in Level}
    tables = page_tables(text)
    problems: list[str] = []
    base = [spec.key for spec in BASE_FIELDS]
    expected: dict[str, tuple[str, list[str]]] = {"base": ("SchRecord", base)}
    for record_id, cls in RECORD_TYPES.items():
        expected[str(record_id)] = (cls.__name__, [key for key in cls.MODELED if key not in base])
    for section in sorted(set(tables) | set(expected)):
        if section not in tables:
            problems.append(f"record {section}: no table on the page")
            continue
        if section not in expected:
            problems.append(f"record {section}: a table for an id outside RECORD_TYPES")
            continue
        name, rows = tables[section]
        wanted_name, wanted_keys = expected[section]
        if name != wanted_name:
            problems.append(f"record {section}: the page names class {name}, the code {wanted_name}")
        keys = [row[0].strip("`") for row in rows]
        if keys != wanted_keys:
            missing = [key for key in wanted_keys if key not in keys]
            extra = [key for key in keys if key not in wanted_keys]
            problems.append(f"record {section}: keys differ; missing {missing}, not modelled {extra}")
        for row in rows:
            if len(row) != len(HEADER):
                problems.append(f"record {section}: row {row[0]} has {len(row)} cells")
                continue
            ids = re.findall(r"\bS-\d{4}\b", row[4])
            if not ids or not set(ids) <= sources or "S-0142" in ids:
                problems.append(f"record {section}: row {row[0]} cites {row[4]!r}")
            level = re.sub(r"\(.*", "", row[5]).strip()
            if row[5] not in labels and not any(row[5].startswith(label) for label in labels):
                problems.append(f"record {section}: row {row[0]} has label {row[5]!r}")
            if (
                level not in (Level.CORPUS_VERIFIED.value, Level.KICAD_VERIFIED.value)
                and row[6] not in registered
            ):
                problems.append(f"record {section}: row {row[0]} names hypothesis {row[6]!r}, not registered")
    return problems


def test_table_and_page_agree() -> None:
    problems = table_problems(PAGE.read_text(encoding="utf-8"))
    assert problems == []


def test_the_check_sees_a_missing_key() -> None:
    text = PAGE.read_text(encoding="utf-8")
    row = "| `LOCATIONCOUNT` | count | 0 | `points` | S-0130 | INFERRED | H-A-RD-SCH-CASE |\n"
    assert row in text
    broken = text.replace(row, "", 1)
    assert broken != text
    assert any("missing ['LOCATIONCOUNT']" in problem for problem in table_problems(broken))


def test_the_check_sees_an_unmodelled_key_and_a_bad_source() -> None:
    text = PAGE.read_text(encoding="utf-8")
    row = '| `LIBREFERENCE` | text | "" | `lib_reference` | S-0130 | INFERRED | H-A-RD-SCH-CASE |'
    assert row in text
    broken = text.replace(
        row, row + '\n| `NOTMODELLED` | text | "" | — | S-0142 | INFERRED | H-A-RD-SCH-CASE |'
    )
    problems = table_problems(broken)
    assert any("not modelled ['NOTMODELLED']" in problem for problem in problems)
    assert any("cites 'S-0142'" in problem for problem in problems)


def test_closed_table_has_43_classes() -> None:
    assert len(RECORD_TYPES) == 43
    assert len(page_tables(PAGE.read_text(encoding="utf-8"))) == 44
