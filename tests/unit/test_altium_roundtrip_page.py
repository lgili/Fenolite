# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``docs/evidence/altium-roundtrip.md`` (capability altium-verification, "Round trips over the corpus and
the samples", scenario "Page matches the census"; change c0044): the three level tables, the run, the rows
of the manifest and the labels of the register."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from fenolite.backends.altium.roundtrip import EVIDENCE_RT_A0, EVIDENCE_RT_A1, EVIDENCE_RT_A2
from fenolite.core.evidence import Level, strength
from fenolite.verify import load_register

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "evidence" / "altium-roundtrip.md"
ROW_ID = re.compile(r"`(altium-third-party-[a-z]+-\d{2})`")
SET_ID = re.compile(r"`(altium-set:\d{2})`")


def _sections(text: str) -> dict[str, str]:
    parts = re.split(r"(?m)^## ", text)
    return {part.split("\n", 1)[0]: part for part in parts[1:]}


def _table(section: str) -> list[list[str]]:
    rows = [line for line in section.splitlines() if line.startswith("|")]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows[2:]]


def _manifest() -> list[dict[str, object]]:
    text = (ROOT / "tests" / "corpus" / "manifest.toml").read_text(encoding="utf-8")
    return list(tomllib.loads(text).get("file", []))


def test_page_holds_the_three_level_tables_and_the_run() -> None:
    text = PAGE.read_text(encoding="utf-8")
    sections = _sections(text)
    assert {"The levels", "Reasons for an unjudged level", "The run", "RT-A0", "RT-A1", "RT-A2"} <= set(
        sections
    )
    assert "run: pending" not in text
    run = re.search(r"run: (\d{4}-\d{2}-\d{2}), commit `([0-9a-f]{7,40})`", sections["The run"])
    assert run is not None
    for name in ("RT-A0", "RT-A1", "RT-A2"):
        assert _table(sections[name]), name


def test_page_names_every_rta_row_and_no_other() -> None:
    text = PAGE.read_text(encoding="utf-8")
    sections = _sections(text)
    rows = _manifest()
    tagged = {str(row["id"]) for row in rows if "rta" in row["uses"]}  # type: ignore[operator]
    assert set(ROW_ID.findall(text)) == tagged
    for name in ("RT-A0", "RT-A1"):
        listed = [ROW_ID.fullmatch(cells[0]) for cells in _table(sections[name])]
        assert all(listed) and {found.group(1) for found in listed if found} == tagged, name
    sets = {use for row in rows for use in row["uses"] if use.startswith("altium-set:")}  # type: ignore[union-attr]
    assert set(SET_ID.findall(text)) == sets


def test_page_counts_are_consistent() -> None:
    """The summary line of each level equals its table, and every unjudged row names a reason."""
    sections = _sections(PAGE.read_text(encoding="utf-8"))
    summary = {cells[0]: cells for cells in _table(sections["The run"])}
    a0 = _table(sections["RT-A0"])
    judged = [cells for cells in a0 if cells[4] == "yes"]
    assert int(summary["RT-A0"][1]) == len(a0) and int(summary["RT-A0"][2]) == len(judged)
    assert all(cells[5] == "yes" for cells in judged) and int(summary["RT-A0"][3]) == len(judged)
    unjudged = [cells for cells in a0 if cells[4] == "no"]
    assert all(cells[9] in ("`too-large`", "`writer-refused`", "`not-a-container`") for cells in unjudged)
    assert all(not cells[9] for cells in judged)
    for cells in unjudged:
        assert cells[0] in sections["RT-A0"].split("Unjudged files:")[1], cells[0]
    a1 = _table(sections["RT-A1"])
    assert int(summary["RT-A1"][1]) == len(a1) == int(summary["RT-A1"][3])
    assert all(
        cells[2] == cells[3] == "yes" and cells[4] == cells[6] for cells in a1
    )  # bytes equal == streams
    a2 = _table(sections["RT-A2"])
    assert summary["RT-A2"][1] == f"{len(a2)} builds" and all(
        cells[2] == "yes" and cells[3] == "0" for cells in a2
    )
    assert {cells[0] for cells in a2} >= {
        "`examples/blink_2layer/design.py`",
        "`examples/altium_sample/design.py`",
    }


def test_page_labels_follow_the_register() -> None:
    """The level column equals the constants of ``roundtrip`` and the state of the hypothesis rows."""
    sections = _sections(PAGE.read_text(encoding="utf-8"))
    summary = {cells[0]: cells for cells in _table(sections["The run"])}
    register = {row.id: row for row in load_register(ROOT / "docs" / "hypotheses.md")}
    assert summary["RT-A0"][5] == f"`{EVIDENCE_RT_A0.level.value}`"
    lowest = min((evidence.level for evidence in EVIDENCE_RT_A1.values()), key=strength)
    assert summary["RT-A1"][5] == f"`{lowest.value}`"
    assert summary["RT-A2"][5] == f"`{EVIDENCE_RT_A2.level.value}`" == "`INFERRED`"
    for level, row in (("RT-A0", "H-A-VER-RTA0"), ("RT-A1", "H-A-VER-RTA1"), ("RT-A2", "H-A-VER-RTA2-2")):
        assert row in summary[level][6]
        confirmed = register[row].result.startswith("confirmed")
        assert ("pending" in summary[level][6]) is (not confirmed) or level == "RT-A2"
    assert register["H-A-VER-RTA2"].result.startswith("refuted; superseded by H-A-VER-RTA2-2")
    assert register["H-A-VER-RTA2-2"].level is Level.INFERRED
    for label in ("ORACLE-VERIFIED", "ALTIUM-VERIFIED", "KICAD-VERIFIED"):
        assert label not in PAGE.read_text(encoding="utf-8")
