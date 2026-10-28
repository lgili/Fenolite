# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The inputs of a pour are recorded facts (change c0215; capability altium-pour, "Pour inputs are recorded
facts"): ``pour.INPUTS`` and the rows of ``docs/formats/altium/pcb-pour.md``, "Pour inputs", name each
other, and every row has a registered source and a registered hypothesis."""

from __future__ import annotations

import re
from pathlib import Path

from fenolite.backends.altium.pour import INPUTS, REASONS
from fenolite.verify import load_register

ROOT = Path(__file__).resolve().parents[4]
PAGE = ROOT / "docs" / "formats" / "altium" / "pcb-pour.md"
SOURCES = ROOT / "docs" / "evidence" / "sources.md"


def _rows() -> dict[str, list[str]]:
    """``I<n>`` → the cells of its row in the section "Pour inputs"."""
    text = PAGE.read_text(encoding="utf-8")
    section = text.split("## Pour inputs", 1)[1].split("\n## ", 1)[0]
    rows: dict[str, list[str]] = {}
    for line in section.splitlines():
        match = re.match(r"\| (I\d+)\. ", line)
        if match:
            rows[match.group(1)] = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
    return rows


def test_rows() -> None:
    """Scenario "Every input has a row"."""
    rows = _rows()
    assert sorted(rows, key=lambda k: int(k[1:])) == list(INPUTS)
    sources = set(re.findall(r"^\| (S-\d{4}) ", SOURCES.read_text(encoding="utf-8"), re.M))
    registered = {row.id for row in load_register(ROOT / "docs" / "hypotheses.md")}
    for ident, cells in rows.items():
        _fact, source, _label, hypothesis = cells
        assert set(re.findall(r"S-\d{4}", source)) <= sources and re.search(r"S-\d{4}", source), ident
        assert hypothesis in registered, (ident, hypothesis)


def test_reasons_read_as_sentences() -> None:
    """Each reason of a refusal is a lower-case key with a sentence that an issue can carry."""
    for key, text in REASONS.items():
        assert re.fullmatch(r"[a-z]+(-[a-z]+)*", key) and text and not text.endswith("."), key
