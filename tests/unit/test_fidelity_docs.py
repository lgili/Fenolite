# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The fidelity evidence page distinguishes measured rows from explicitly pending work (c0278)."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from _fidelity import ALL_LEVELS
from _fidelity_corpus import COUNT_KEYS, load_ratchet, rtf_roots

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs/evidence/fidelity.md"
RATCHET = ROOT / "tests/kicad/fidelity/accepted.toml"
MANIFEST = ROOT / "tests/corpus/manifest.toml"
BEGIN, END = "<!-- fidelity-corpus:begin -->", "<!-- fidelity-corpus:end -->"


def test_evidence_page_matches_measured_and_pending_rows() -> None:
    text = PAGE.read_text(encoding="utf-8")
    body = text.split(BEGIN, 1)[1].split(END, 1)[0]
    shown = {}
    for line in body.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0].startswith("kicad-demo-"):
            assert len(cells) == 8 and cells[0] not in shown
            shown[cells[0]] = cells[1:]
    record = load_ratchet(RATCHET)
    measured = {row["id"]: row for row in record.get("row", [])}
    pending = record.get("pending", {})
    roots = rtf_roots(tomllib.loads(MANIFEST.read_text(encoding="utf-8"))["file"])
    assert set(shown) == {row["id"] for row in roots} == measured.keys() | pending.keys()
    for row in roots:
        cells = shown[row["id"]]
        assert cells[0] == row["license"]
        if row["id"] in pending:
            assert cells[1:] == ["not baselined", "not baselined", "undecided", "—", "—", "—"]
        else:
            entry = measured[row["id"]]
            counts = ", ".join(f"{key}={value}" for key, value in sorted(entry["counts"].items())) or "none"
            assert cells[2] == counts and cells[3] == entry["attribution"]
            assert cells[4] == record["run"]["fenolite"] and cells[5] == record["run"]["date"]
            assert cells[6] != "—", "measured rows need actual elapsed seconds"
    assert "Level 8 is **INFERRED**" in text and "not a GUI save" in text


def test_actual_probe_counts_and_refusals_match_the_page_without_acceptance() -> None:
    record = json.loads(RATCHET.with_name("observed.json").read_text(encoding="utf-8"))
    assert record["schema"] == "fenolite.fidelity-observations.v0"
    assert record["result"] == "not-passing" and record["accepted"] is False
    text = PAGE.read_text(encoding="utf-8")
    assert record["base"] in text
    body = text.split("<!-- fidelity-observed:begin -->", 1)[1].split("<!-- fidelity-observed:end -->", 1)[0]
    shown = {}
    for line in body.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0].startswith("kicad-demo-"):
            assert len(cells) == 8 and cells[0] not in shown
            shown[cells[0]] = cells[1:]
    assert set(shown) == {row["id"] for row in record["rows"]}
    for row in record["rows"]:
        assert set(row) <= {
            "id",
            "outcome",
            "exit_code",
            "counts",
            "levels",
            "seconds",
            "codes",
            "error_code",
            "attribution",
        }
        equal = ", ".join(str(level) for level in ALL_LEVELS if row["levels"].get(str(level)) == "equal")
        if row["outcome"] == "compared":
            assert row["exit_code"] == 5 and row["counts"] and row["levels"]
            assert set(row["levels"]) == {str(level) for level in ALL_LEVELS}
            assert all(key in COUNT_KEYS and type(n) is int and n > 0 for key, n in row["counts"].items())
            counts = ", ".join(f"{key}={value}" for key, value in sorted(row["counts"].items()))
        else:
            assert row["counts"] is None and row["levels"] == {}, "a refusal is never zero differences"
            counts = "not compared"
        metadata = [record["fenolite"], record["date"], str(row["seconds"])]
        if row["outcome"] == "heavy-skipped":
            metadata = ["—", "—", "—"]
        assert shown[row["id"]] == [
            row["outcome"],
            equal or "not compared",
            counts,
            row["attribution"],
            *metadata,
        ]


def test_fast_and_focused_targets_include_the_fidelity_category() -> None:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    fast = text.split("test-fast:\n", 1)[1].split("\n\n", 1)[0]
    assert "tests/fidelity" in fast
    assert "fidelity:\n\tuv run pytest tests/fidelity" in text
    assert "fidelity-corpus:\n\tuv run pytest tests/kicad/fidelity" in text
