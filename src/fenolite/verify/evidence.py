# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Which evidence counts as verified for a release.

An author report (``ALTIUM-VERIFIED(author-report)``) never promotes an operation, and a refuted row
never counts as support, although it carries the level of the run that refuted it. The set is
explicit, so a level added later changes the release rule only through a failing test.
"""

from __future__ import annotations

from fenolite.core.evidence import Level
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


__all__ = ["RELEASE_VERIFIED", "is_release_evidence", "release_verified"]
