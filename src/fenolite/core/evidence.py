# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Evidence labels: how a result was verified. The combined label of several steps is the lowest.

``ALTIUM-VERIFIED(author-report)`` records what the author observed in ordinary use of a licensed
tool; it never promotes an operation to "verified" in the release matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Level(StrEnum):
    """Evidence levels, declared from strongest to weakest."""

    ALTIUM_VERIFIED_KIT = "ALTIUM-VERIFIED(kit)"
    KICAD_VERIFIED = "KICAD-VERIFIED"
    ORACLE_VERIFIED = "ORACLE-VERIFIED"
    CORPUS_VERIFIED = "CORPUS-VERIFIED"
    ALTIUM_VERIFIED_AUTHOR_REPORT = "ALTIUM-VERIFIED(author-report)"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"
    UNVERIFIED = "UNVERIFIED"


_STRENGTH: dict[Level, int] = {level: len(Level) - index for index, level in enumerate(Level)}


def strength(level: Level) -> int:
    """Higher is stronger."""
    return _STRENGTH[level]


def min_level(*levels: Level) -> Level:
    """The weakest of ``levels`` (the label a combined result deserves)."""
    if not levels:
        raise ValueError("min_level() needs at least one level")
    return min(levels, key=strength)


@dataclass(frozen=True, slots=True)
class Evidence:
    """A level plus the oracle that produced it and the hypotheses it depends on."""

    level: Level = Level.UNVERIFIED
    oracle: str | None = None
    hypotheses: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "level", Level(self.level))
        object.__setattr__(self, "hypotheses", tuple(self.hypotheses))

    def label(self) -> str:
        """``ORACLE-VERIFIED(kicad-import)``, ``KICAD-VERIFIED``, …"""
        if self.level is Level.ORACLE_VERIFIED and self.oracle:
            return f"{self.level.value}({self.oracle})"
        return self.level.value

    @staticmethod
    def combine(*items: Evidence) -> Evidence:
        """Lowest level wins; hypotheses are merged."""
        if not items:
            return Evidence()
        weakest = min(items, key=lambda e: strength(e.level))
        hypotheses = tuple(sorted({h for e in items for h in e.hypotheses}))
        return Evidence(weakest.level, weakest.oracle, hypotheses)


__all__ = ["Evidence", "Level", "min_level", "strength"]
