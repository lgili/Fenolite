# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""LEGAL.md, LEGAL-ANNEX.md and CONTRIBUTING.md keep their required structure."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANNEX_HEADER = ["date", "area", "files touched", "public sources consulted", "author"]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_legal_has_both_blocks() -> None:
    text = _read("LEGAL.md")
    assert "## A. Format analysis" in text
    assert "## B. Material from organisations" in text


def test_legal_block_a_forbids_reverse_engineering_and_requires_sources() -> None:
    text = _read("LEGAL.md").lower()
    assert "never" in text and "decompile" in text
    assert "docs/formats/" in text and "docs/evidence/sources.md" in text


def test_legal_block_b_states_clean_room() -> None:
    assert "clean-room" in _read("LEGAL.md")


def test_annex_table_header() -> None:
    header_rows = [line for line in _read("LEGAL-ANNEX.md").splitlines() if line.startswith("| date")]
    assert len(header_rows) == 1
    cells = [c.strip() for c in header_rows[0].strip("|").split("|")]
    assert cells == ANNEX_HEADER


def test_contributing_requires_dco() -> None:
    text = _read("CONTRIBUTING.md")
    assert "Signed-off-by:" in text
    assert "https://developercertificate.org/" in text


def test_legal_lists_the_four_prohibitions() -> None:
    text = _read("LEGAL.md")
    for tag in ("(P1)", "(P2)", "(P3)", "(P4)"):
        assert tag in text
    lower = text.lower()
    assert "decompil" in lower and "grammar" in lower and "entitled to read" in lower
    assert "employer's software licence" in lower


def test_legal_allows_facts_with_source_only() -> None:
    assert "only when the fact is recorded there with its source" in _read("LEGAL.md")


def test_contributing_explains_allowed_vs_forbidden() -> None:
    assert "## Allowed vs forbidden derivation" in _read("CONTRIBUTING.md")
