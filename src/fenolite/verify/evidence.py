# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Which evidence counts as verified for a release.

An author report (``ALTIUM-VERIFIED(author-report)``) never promotes an operation, and a refuted row
never counts as support, although it carries the level of the run that refuted it. The set is
explicit, so a level added later changes the release rule only through a failing test.

``report_problems`` is the rule that every declared evidence passes (capability verification-evidence,
"Declared levels agree with the register"; change c0067): lowest wins.
"""

from __future__ import annotations

from collections.abc import Sequence

from fenolite.core.evidence import Evidence, Level, strength
from fenolite.verify.hypotheses import HypothesisRow

RELEASE_VERIFIED: frozenset[Level] = frozenset(
    {Level.ALTIUM_VERIFIED_KIT, Level.KICAD_VERIFIED, Level.ORACLE_VERIFIED, Level.CORPUS_VERIFIED}
)


def release_verified(level: Level) -> bool:
    """True exactly for the levels of ``RELEASE_VERIFIED``."""
    return level in RELEASE_VERIFIED


def is_release_evidence(row: HypothesisRow) -> bool:
    """True when the row supports a release claim: not refuted, and release-verified."""
    return not row.refuted and release_verified(row.level)


def report_problems(evidence: Evidence, rows: Sequence[HypothesisRow]) -> list[str]:
    """One message per hypothesis of ``evidence`` that is unregistered, refuted, or weaker than the
    evidence's level. A level below every row it names is accepted: a row states what its test covered,
    and a declaration states what holds for an arbitrary file."""
    by_id = {row.id: row for row in rows}
    problems: list[str] = []
    for ident in evidence.hypotheses:
        row = by_id.get(ident)
        if row is None:
            problems.append(f"{ident} is not registered")
        elif row.refuted:
            problems.append(f"{ident} is refuted and supports no report")
        elif strength(evidence.level) > strength(row.level):
            problems.append(
                f"the report says {evidence.level.value}, stronger than {ident} "
                f"({row.level.value}): lowest wins"
            )
    return problems


__all__ = ["RELEASE_VERIFIED", "is_release_evidence", "release_verified", "report_problems"]
