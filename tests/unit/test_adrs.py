# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Architecture Decision Records follow the MADR-lite structure."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ADR_DIR = Path(__file__).resolve().parents[2] / "docs" / "adr"
SECTIONS = ["## Status", "## Context", "## Decision", "## Alternatives", "## Consequences", "## Evidence"]
STATUS = re.compile(r"^(Proposed|Accepted|Deprecated|Superseded by ADR-\d{4})\b")
REQUIRED = [
    "0001-neutral-model.md",
    "0002-kicad-file-backend.md",
    "0003-clean-room-and-provenance.md",
    "0004-licence-apache-2.0.md",
    "0005-sheet-templates.md",
    "0006-specctra-and-freerouting.md",
    "0007-fetching-external-tools.md",
]


def _adrs() -> list[Path]:
    return sorted(p for p in ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md"))


@pytest.mark.parametrize("name", REQUIRED)
def test_required_adr_exists(name: str) -> None:
    assert (ADR_DIR / name).is_file()


@pytest.mark.parametrize("path", _adrs(), ids=lambda p: p.name)
def test_adr_structure(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    number = path.name[:4]
    assert text.startswith(f"# ADR-{number}: "), "title must be '# ADR-NNNN: <title>'"
    positions = [text.find(s + "\n") for s in SECTIONS]
    assert all(p >= 0 for p in positions), (
        f"missing sections: {[s for s, p in zip(SECTIONS, positions, strict=True) if p < 0]}"
    )
    assert positions == sorted(positions), "sections out of order"
    status_line = text.split("## Status\n", 1)[1].strip().splitlines()[0]
    assert STATUS.match(status_line), f"invalid status line: {status_line!r}"


def test_adr_0004_states_process_boundary_rule() -> None:
    text = (ADR_DIR / "0004-licence-apache-2.0.md").read_text(encoding="utf-8")
    assert "only behind a process boundary or a published plugin API, never" in text
    assert "imported or vendored" in text


# --- ADR-0007: fetching external tools (capability routing, "Fetched tools decision record"; c0078) ----

ROOT = ADR_DIR.parents[1]
ROW_CITED = re.compile(r"`docs/roadmap\.md`, Open decisions, row (\d+)")


def open_decisions(roadmap: str) -> dict[int, str]:
    """The rows of "Open decisions" of the roadmap page by number."""
    section = roadmap.split("\n## Open decisions\n", 1)[1].split("\n## ", 1)[0]
    return {int(m.group(1)): m.group(0) for m in re.finditer(r"^\| (\d+) \|.*$", section, re.MULTILINE)}


def decision_row_problems(record: str, roadmap: str) -> list[str]:
    """Why the record's roadmap row is not the row of its decision; an empty list when it is."""
    cited = ROW_CITED.search(record)
    if cited is None:
        return ["the record names no row of Open decisions"]
    row = open_decisions(roadmap).get(int(cited.group(1)))
    if row is None:
        return [f"Open decisions has no row {cited.group(1)}"]
    return [] if "fenolite fetch" in row else [f"row {cited.group(1)} does not hold 'fenolite fetch'"]


def test_adr_0007_is_accepted_and_states_the_rule() -> None:
    text = (ADR_DIR / "0007-fetching-external-tools.md").read_text(encoding="utf-8")
    status = text.split("## Status\n", 1)[1].strip().splitlines()[0]
    assert status.startswith("Accepted") and "2026-10-05" in status and "2026-10-07" in status
    decision = " ".join(text.split("## Decision\n", 1)[1].split("## Alternatives\n", 1)[0].split())
    for words in (
        "only inside `fenolite fetch NAME`",
        "`--confirm`",
        "docs/evidence/sources.md",
        "SHA-256",
        "imports nothing",
        "ADR-0004",
        "No other command opens a network connection",
    ):
        assert words in decision, words
    alternatives = text.split("## Alternatives\n", 1)[1].split("## Consequences\n", 1)[0]
    for words in ("Bundling the jar", "A download on the first `route`", "Leaving the install manual"):
        assert f"- **{words}" in alternatives, words
    assert ROW_CITED.search(text) is not None


def test_adr_0007_names_its_roadmap_row() -> None:
    """The row is written by task 1.2 of c0078. Until the roadmap holds a row of that number the test is
    skipped; once it does, the row must be the one of the decision."""
    record = (ADR_DIR / "0007-fetching-external-tools.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
    problems = decision_row_problems(record, roadmap)
    if problems and problems[0].startswith("Open decisions has no row"):
        pytest.skip(f"{problems[0]}: task 1.2 of c0078 adds it")
    assert problems == []


def test_adr_0007_row_check_detects_a_wrong_row() -> None:
    record = "held by `docs/roadmap.md`, Open decisions, row 2."
    table = "| # | decision |\n|---|---|\n| 1 | a |\n| 2 | b |\n"
    page = f"# x\n\n## Open decisions\n\n{table}\n## Next\n| 3 | c |\n"
    assert decision_row_problems(record, page) == ["row 2 does not hold 'fenolite fetch'"]
    assert decision_row_problems(record, page.replace("| 2 | b |", "| 2 | `fenolite fetch` only |")) == []
    assert decision_row_problems(record.replace("row 2", "row 3"), page) == ["Open decisions has no row 3"]
    assert decision_row_problems("no row", page) == ["the record names no row of Open decisions"]


def test_adr_0006_is_amended_and_keeps_its_sentences() -> None:
    text = (ADR_DIR / "0006-specctra-and-freerouting.md").read_text(encoding="utf-8")
    decision = text.split("## Decision\n", 1)[1].split("## Alternatives\n", 1)[0]
    third = decision.split("3. **Freerouting only as a program.**", 1)[1].split("4. **", 1)[0]
    assert "Fenolite never imports it, vendors it, downloads it or reads its source code" in third
    amended = [line for line in third.splitlines() if "ADR-0007" in line]
    assert len(amended) == 1 and "2026-10-07" in amended[0] and "`fenolite fetch`" in amended[0]


def test_adr_0007_is_listed_and_logged() -> None:
    index = (ADR_DIR / "README.md").read_text(encoding="utf-8")
    assert "| [0007](0007-fetching-external-tools.md) |" in index
    annex = (ROOT / "LEGAL-ANNEX.md").read_text(encoding="utf-8")
    rows = [line for line in annex.splitlines() if "0007-fetching-external-tools.md" in line]
    assert len(rows) == 1 and "`fenolite fetch`" in rows[0] and "fetch.toml" in rows[0]
