# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The build oracle's judge on authored reports (capability kicad-oracle, "Built projects pass the build
oracle", scenario "Canary missing fails"; change c0011)."""

from __future__ import annotations

import pytest
from _build_judge import assert_loaded, baseline_outcome, canary_outcome, class_outcome, libtable_outcome

from fenolite.backends.base import DrcItem, DrcReport, DrcViolation
from fenolite.core.coords import Point


def violation(kind: str, *uuids: str, severity: str = "error") -> DrcViolation:
    return DrcViolation(kind, "", severity, tuple(DrcItem(u, "", Point(0, 0)) for u in uuids))


def report(*violations: DrcViolation) -> DrcReport:
    return DrcReport("b.kicad_pcb", "", "10.0.6", "mm", violations=violations)


EMPTY = report()
PADS = ("p9", "p10")


def test_canary() -> None:
    assert canary_outcome(EMPTY, report(violation("clearance", "a", "b"))) == "present"
    assert (
        canary_outcome(report(violation("clearance", "a", "b")), report(violation("clearance", "a", "b")))
        == "inconclusive"
    )
    assert canary_outcome(EMPTY, None) == "inconclusive"


def test_canary_missing_fails() -> None:
    with pytest.raises(pytest.fail.Exception, match="rules file not loaded"):
        assert_loaded(canary_outcome(EMPTY, EMPTY), "canary")
    assert_loaded("present", "canary")


def test_class() -> None:
    hit = report(violation("clearance", *PADS))
    assert class_outcome(hit, EMPTY, EMPTY, pads=PADS) == "present"
    assert class_outcome(EMPTY, EMPTY, EMPTY, pads=PADS) == "absent"
    assert class_outcome(hit, hit, EMPTY, pads=PADS) == "different"
    assert class_outcome(hit, EMPTY, hit, pads=PADS) == "different"
    assert class_outcome(report(violation("clearance", "p9", "track")), EMPTY, EMPTY, pads=PADS) == "absent"
    other = report(violation("clearance", *PADS), violation("clearance", "p9", "p8"))
    assert class_outcome(other, EMPTY, EMPTY, pads=PADS) == "present"


def test_libtable() -> None:
    issues, mismatch = (
        report(violation("lib_footprint_issues", "x", severity="warning")),
        report(violation("lib_footprint_mismatch", "x")),
    )
    assert libtable_outcome(EMPTY, issues) == "equal"
    assert libtable_outcome(mismatch, issues) == "different"
    assert libtable_outcome(issues, issues) == "absent"
    assert libtable_outcome(EMPTY, EMPTY) == "inconclusive"
    assert libtable_outcome(None, issues) == "reject"


def test_baseline() -> None:
    assert baseline_outcome(EMPTY) == "absent" and baseline_outcome(None) == "reject"
    assert baseline_outcome(report(violation("x", "a", severity="warning"))) == "absent"
    assert baseline_outcome(report(violation("x", "a"))) == "present"
    assert baseline_outcome(report(violation("x", "a")), excepted=frozenset({"x"})) == "absent"
