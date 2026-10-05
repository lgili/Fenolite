# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The PCB reader is documented (capability altium-pcb-reader, "PCB reader is documented", change c0041):
``docs/formats/altium/pcb-read.md``, the section "Reading PCB files" of ``docs/altium.md`` and
``docs/evidence/altium-pcb-read.md``."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from fenolite.backends.altium.read.pcbprims import PCB_READ_ISSUE_CODES
from fenolite.core.evidence import Level
from fenolite.verify import load_register

ROOT = Path(__file__).resolve().parents[2]
FACTS = ROOT / "docs" / "formats" / "altium" / "pcb-read.md"
GUIDE = ROOT / "docs" / "altium.md"
EVIDENCE = ROOT / "docs" / "evidence" / "altium-pcb-read.md"
SOURCES = ROOT / "docs" / "evidence" / "sources.md"
REGISTER = ROOT / "docs" / "hypotheses.md"
MANIFEST = ROOT / "tests" / "corpus" / "manifest.toml"
SECTIONS = (
    "Record lengths",
    "Fields",
    "Keys",
    "Regions",
    "Wide strings",
    "Rules",
    "Storages kept as bytes",
    "What KiCad does not import",
    "Fenolite's choices",
)


def _level(cell: str) -> Level | None:
    for level in sorted(Level, key=lambda lv: -len(lv.value)):
        if cell == level.value or cell.startswith((level.value + " ", level.value + "(")):
            return level
    return None


def _rows(text: str, header: tuple[str, ...]) -> list[list[str]]:
    """The rows of every table with the header ``header``."""
    rows: list[list[str]] = []
    inside = False
    for line in text.splitlines():
        if not line.startswith("|"):
            inside = False
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
        if tuple(cells) == header:
            inside = True
            continue
        if inside and not set(line.strip()) <= set("|- "):
            rows.append(cells)
    return rows


def test_fact_page_sections_and_rows() -> None:
    text = FACTS.read_text(encoding="utf-8")
    for section in SECTIONS:
        assert f"\n## {section}\n" in text, section
    sources = set(re.findall(r"^\| (S-\d{4}) \|", SOURCES.read_text(encoding="utf-8"), re.MULTILINE))
    hypotheses = {row.id for row in load_register(REGISTER)}
    tables = (
        (("fact", "source", "label", "hypothesis"), 1, 2, 3),
        (("record", "field", "subrecord", "offset", "from length", "source", "label", "hypothesis"), 5, 6, 7),
        (("record", "key", "field", "source", "label", "hypothesis"), 3, 4, 5),
    )
    count = 0
    for header, source, label, hypothesis in tables:
        for cells in _rows(text, header):
            cited = re.findall(r"S-\d{4}", cells[source])
            assert cited and set(cited) <= sources, cells[0]
            assert _level(cells[label]) is not None, cells[label]
            assert cells[hypothesis] in hypotheses, cells[hypothesis]
            count += 1
    assert count > 100
    assert "| S-0173 |" not in text


def test_guide_names_functions_and_codes() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    section = text[text.index("## Reading PCB files") :]
    section = section[: section.index("\n## ", 3)]
    for name in ("read_pcbdoc", "read_pcblib", "c0043", "PcbReadError", "rebuild"):
        assert name in section, name
    for code, severity in PCB_READ_ISSUE_CODES.items():
        assert f"| `{code}` | {severity} |" in section, code
    assert "CORPUS-VERIFIED" in section and "ORACLE-VERIFIED(kicad-cli)" in section


def test_evidence_page_has_every_row() -> None:
    text = EVIDENCE.read_text(encoding="utf-8")
    rows = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))["file"]
    documents = [r["id"] for r in rows if "altium-pcbdoc" in r["uses"]]
    libraries = [r["id"] for r in rows if "altium-pcblib" in r["uses"]]
    census = text[text.index("## Census") : text.index("## Document oracle")]
    documents_oracle = text[text.index("## Document oracle") : text.index("## Library oracle")]
    libraries_oracle = text[text.index("## Library oracle") :]
    for ident in documents:
        assert f"`{ident}`" in census and f"`{ident}`" in documents_oracle, ident
    for ident in libraries:
        assert f"`{ident}`" in census and f"`{ident}`" in libraries_oracle, ident
