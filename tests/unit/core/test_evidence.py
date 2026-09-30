# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import pytest

from fenolite.core.evidence import Evidence, Level, min_level, strength

ORDER = [
    Level.ALTIUM_VERIFIED_KIT, Level.KICAD_VERIFIED, Level.ORACLE_VERIFIED, Level.CORPUS_VERIFIED,
    Level.ALTIUM_VERIFIED_AUTHOR_REPORT, Level.INFERRED, Level.UNKNOWN, Level.UNVERIFIED,
]  # fmt: skip


def test_total_order() -> None:
    assert sorted(Level, key=strength, reverse=True) == ORDER
    assert all(strength(a) > strength(b) for a, b in zip(ORDER, ORDER[1:], strict=False))


def test_lowest_level_wins() -> None:
    assert min_level(Level.KICAD_VERIFIED, Level.INFERRED) is Level.INFERRED
    assert (
        min_level(Level.ALTIUM_VERIFIED_AUTHOR_REPORT, Level.CORPUS_VERIFIED)
        is Level.ALTIUM_VERIFIED_AUTHOR_REPORT
    )
    with pytest.raises(ValueError):
        min_level()


def test_labels() -> None:
    assert Evidence(Level.ORACLE_VERIFIED, "kicad-import", ()).label() == "ORACLE-VERIFIED(kicad-import)"
    assert Evidence(Level.KICAD_VERIFIED, "kicad-cli 10.0.6").label() == "KICAD-VERIFIED"
    assert Evidence().label() == "UNVERIFIED"


def test_strings_are_coerced() -> None:
    evidence = Evidence("INFERRED", None, ["H-K-UNIT"])  # type: ignore[arg-type]
    assert evidence.level is Level.INFERRED and evidence.hypotheses == ("H-K-UNIT",)
    with pytest.raises(ValueError):
        Evidence("MAYBE")  # type: ignore[arg-type]


def test_combine() -> None:
    combined = Evidence.combine(
        Evidence(Level.KICAD_VERIFIED, "kicad-cli", ("H-K-1",)),
        Evidence(Level.INFERRED, None, ("H-G-2", "H-K-1")),
    )
    assert combined == Evidence(Level.INFERRED, None, ("H-G-2", "H-K-1"))
    assert Evidence.combine() == Evidence()
