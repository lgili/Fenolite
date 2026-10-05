# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pages of the Altium verification (capability altium-verification, "Altium verification is
documented", scenario "Pages name the levels and the codes"; change c0044)."""

from __future__ import annotations

import re
from pathlib import Path

from fenolite.backends.altium.backend import READ_KINDS
from fenolite.checks.codes import ISSUE_CODES
from fenolite.checks.documents import DOCUMENT_STAGES

ROOT = Path(__file__).resolve().parents[2]
LEVELS = ("RT-A0", "RT-A1", "RT-A2")
CODES = (
    "check.document-missing",
    "check.rta0-failed",
    "check.rta1-failed",
    "check.rta1-normalised",
    "check.rta2-failed",
    "check.roundtrip-unjudged",
)
SKIPS = ("native-input", "no-schematic", "single-source", "not-judged", "read-refused", "cache-unreadable")


def _page(name: str) -> str:
    return (ROOT / "docs" / name).read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    start = text.index(f"\n{heading}\n")
    level = heading.split(" ")[0]
    found = re.search(rf"\n{level} ", text[start + 1 :])
    return text[start : start + 1 + found.start()] if found else text[start:]


def test_levels_are_named_in_the_three_pages() -> None:
    for name in ("altium.md", "roadmap.md", "cli-contract.md", "evidence/altium-roundtrip.md"):
        text = _page(name)
        for level in LEVELS:
            assert level in text, (name, level)


def test_contract_names_the_stages_the_codes_and_the_skip_reasons() -> None:
    contract = _page("cli-contract.md")
    section = _section(contract, "### check on Altium input")
    for stage in DOCUMENT_STAGES:
        assert f"`{stage}`" in section, stage
    for reason in SKIPS:
        assert f"`{reason}`" in section, reason
    for key in ("backend", "project", "board", "built", "files", "documents", "skipped", "not_in_model"):
        assert f"`{key}`" in section, key
    for code in CODES:
        assert code in ISSUE_CODES and f"`{code}`" in contract, code
    assert re.search(r"(?m)^## diff$", contract)
    diff = _section(contract, "## diff")
    for view in ("--view model", "--view tree", "--view records"):
        assert view in diff, view
    inspect = _section(contract, "## inspect")
    for kind in READ_KINDS:
        assert f"`{kind}`" in inspect, kind
    assert "`opaque_count`" in inspect and "`result.streams`" in inspect


def test_altium_page_has_the_round_trips_section() -> None:
    section = _section(_page("altium.md"), "## Round trips")
    for word in (
        "not-a-container",
        "too-large",
        "writer-refused",
        "native-input",
        "fenolite check",
        "fenolite inspect",
    ):
        assert word in section, word
    assert "--view records" in section and "not_in_model" in section
    assert "do not take Altium files yet" not in _page("altium.md")


def test_roadmap_says_what_this_change_adds_to_diff() -> None:
    roadmap = _page("roadmap.md")
    assert "Done as c0044" in roadmap and "--view records" in roadmap and "c0066" in roadmap
