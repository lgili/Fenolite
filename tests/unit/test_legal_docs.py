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


# --- fenolite-library (capability ip-hygiene, "Third-party material only in fenolite-library"; c0279) ---

LIBRARY_RULE = "**Third-party material lives only in `fenolite-library`**"


def library_rule_problems(agents: str) -> list[str]:
    """What the "Hard rules" of ``agents`` lack of the fenolite-library rule; empty when it is complete."""
    rules = agents.split("## Hard rules", 1)[-1].split("\n## ", 1)[0]
    found = [block for block in rules.split("\n- ") if LIBRARY_RULE in block]
    if not found:
        return ["AGENTS.md: the hard rule 'Third-party material lives only in fenolite-library' is missing"]
    text = " ".join(found[0].split())
    words = ("github.com/lgili/fenolite-library", "licence", "NOTICE", "`PROVENANCE.json`")
    return [
        f"AGENTS.md: the fenolite-library rule does not name {word}" for word in words if word not in text
    ]


def test_fenolite_library_sentence_present() -> None:
    assert library_rule_problems(_read("AGENTS.md")) == []
    adr = _read("docs/adr/0003-clean-room-and-provenance.md")
    assert [line for line in adr.splitlines() if "fenolite-library" in line and "2026-10-29" in line]


def test_fenolite_library_sentence_removed() -> None:
    text = _read("AGENTS.md")
    start = text.index("- " + LIBRARY_RULE)
    end = text.index("\n- ", start + 2)
    problems = library_rule_problems(text[:start] + text[end + 1 :])
    assert problems and "missing" in problems[0]
