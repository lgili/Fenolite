# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pure verdicts of the build oracle (c0011 Decision 26): DRC reports in, c0017's closed outcomes out.

Every verdict comes from the DRC JSON report, never from the exit code. ``assert_loaded`` fails an
``inconclusive`` case with "rules file not loaded".
"""

from __future__ import annotations

import pytest

from fenolite.backends.base import DrcReport

LIB_ISSUES = "lib_footprint_issues"
LIB_MISMATCH = "lib_footprint_mismatch"


def _keys(report: DrcReport, kind: str) -> set[frozenset[str]]:
    return {frozenset(i.uuid for i in v.items) for v in report.violations if v.type == kind}


def canary_outcome(plain: DrcReport, canary: DrcReport | None) -> str:
    """``present`` when the canary copy holds a ``clearance`` violation absent from the plain run."""
    if canary is None:
        return "inconclusive"
    return "present" if _keys(canary, "clearance") - _keys(plain, "clearance") else "inconclusive"


def class_outcome(
    variant: DrcReport, noproject: DrcReport, asbuilt: DrcReport, *, pads: tuple[str, str]
) -> str:
    """``present``: the variant has the ``clearance`` violation of exactly the two pads, and neither the
    no-project copy nor the as-built blink has it; ``absent``: the variant lacks it; ``different``
    otherwise."""
    pair = frozenset(pads)
    if pair not in _keys(variant, "clearance"):
        return "absent"
    if pair in _keys(noproject, "clearance") or pair in _keys(asbuilt, "clearance"):
        return "different"
    return "present"


def libtable_outcome(with_table: DrcReport | None, without_table: DrcReport | None) -> str:
    """``equal``: the table is read and parity holds, and the copy without it gives library issues."""
    if with_table is None or without_table is None:
        return "reject"
    if not without_table.of_type(LIB_ISSUES):
        return "inconclusive"
    if with_table.of_type(LIB_ISSUES):
        return "absent"
    return "different" if with_table.of_type(LIB_MISMATCH) else "equal"


def baseline_outcome(report: DrcReport | None, *, excepted: frozenset[str] = frozenset()) -> str:
    """``absent`` when the report holds no violation of severity ``error`` outside ``excepted``."""
    if report is None:
        return "reject"
    errors = [v for v in report.violations if v.severity == "error" and v.type not in excepted]
    return "present" if errors else "absent"


def assert_loaded(outcome: str, case: str) -> None:
    if outcome == "inconclusive":
        pytest.fail(f"rules file not loaded: case {case!r} is inconclusive", pytrace=False)


__all__ = ["assert_loaded", "baseline_outcome", "canary_outcome", "class_outcome", "libtable_outcome"]
