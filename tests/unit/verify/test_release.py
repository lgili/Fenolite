# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Release-verified levels, author reports and refuted rows (capability verification-evidence)."""

from __future__ import annotations

from pathlib import Path

from fenolite.core.evidence import Evidence, Level
from fenolite.verify import RELEASE_VERIFIED, is_release_evidence, load_register, release_verified

LIVE = Path(__file__).resolve().parents[3] / "docs" / "hypotheses.md"


def test_whole_level_table() -> None:
    verified = {Level.ALTIUM_VERIFIED_KIT, Level.KICAD_VERIFIED, Level.ORACLE_VERIFIED, Level.CORPUS_VERIFIED}
    assert RELEASE_VERIFIED == verified
    for level in Level:
        assert release_verified(level) is (level in verified), level


def test_author_report_is_not_release_verified() -> None:
    assert release_verified(Level.ALTIUM_VERIFIED_AUTHOR_REPORT) is False
    assert release_verified(Level.KICAD_VERIFIED) is True


def test_combined_with_a_kicad_result() -> None:
    combined = Evidence.combine(
        Evidence(Level.ALTIUM_VERIFIED_AUTHOR_REPORT), Evidence(Level.KICAD_VERIFIED, "kicad-cli 10.0.6")
    )
    assert combined.level is Level.ALTIUM_VERIFIED_AUTHOR_REPORT and not release_verified(combined.level)


def test_combined_with_a_kit_result() -> None:
    combined = Evidence.combine(
        Evidence(Level.ALTIUM_VERIFIED_KIT), Evidence(Level.ALTIUM_VERIFIED_AUTHOR_REPORT)
    )
    assert combined.level is Level.ALTIUM_VERIFIED_AUTHOR_REPORT


def test_refuted_row_gives_no_release_support() -> None:
    rows = {r.id: r for r in load_register(LIVE)}
    refuted = rows["H-K-TOK-FUTURE"]
    assert refuted.refuted and release_verified(refuted.level) and not is_release_evidence(refuted)
    assert is_release_evidence(rows["H-K-TOK-FUTURE-2"])


def test_no_refuted_row_counts() -> None:
    refuted = [r for r in load_register(LIVE) if r.refuted]
    assert refuted and not any(is_release_evidence(r) for r in refuted)


def test_author_report_rows_are_not_release_verified() -> None:
    rows = [r for r in load_register(LIVE) if r.level is Level.ALTIUM_VERIFIED_AUTHOR_REPORT]
    assert not any(release_verified(r.level) or is_release_evidence(r) for r in rows)
