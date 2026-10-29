# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exclusions stored in both item orders are judged as one accepted exception (capability kicad-oracle,
"DRC exclusions written"; change c0209; ``checks.drc.mirrored`` and ``accepted_rows``)."""

from __future__ import annotations

from fenolite.backends.base import DrcItem, DrcReport, DrcViolation, StoredExclusion
from fenolite.checks.drc import STALE, accepted_rows, exclusion_issues, mirrored
from fenolite.core.coords import Point

AT = Point(15_000_123, 17_000_000)


def pair(kind: str, a: str, b: str, comment: str = "ok", at: Point = AT) -> list[StoredExclusion]:
    return [StoredExclusion(kind, at, (a, b), comment), StoredExclusion(kind, at, (b, a), comment)]


def report(*entries: DrcViolation) -> DrcReport:
    found = [e for e in entries if e.type != "unconnected_items"]
    unconnected = [e for e in entries if e.type == "unconnected_items"]
    return DrcReport(
        "b.kicad_pcb", "", "10.0.7", "mm", violations=tuple(found), unconnected_items=tuple(unconnected)
    )


def entry(kind: str, *uuids: str, excluded: bool = False) -> DrcViolation:
    items = tuple(DrcItem(uuid, "item", Point(0, 0)) for uuid in uuids)
    return DrcViolation(kind, kind, "error", items, excluded=excluded, comment="ok" if excluded else "")


def test_mirrored_pairs() -> None:
    stored = [*pair("clearance", "a", "B"), StoredExclusion("clearance", AT, ("c", "d"))]
    assert mirrored(stored) == {0: 1, 1: 0}
    moved = [
        StoredExclusion("clearance", AT, ("a", "b")),
        StoredExclusion("clearance", Point(0, 0), ("b", "a")),
    ]
    assert mirrored(moved) == {}


def test_an_unconnected_pair_is_live_in_either_report_order() -> None:
    """Scenario "An accepted unconnected item", without a tool: one live row, both keys live."""
    stored = pair("unconnected_items", "a", "b")
    for found in (
        entry("unconnected_items", "b", "a", excluded=True),
        entry("unconnected_items", "a", "b", excluded=True),
    ):
        rows, _ = accepted_rows(stored, report(found))
        assert rows == [{"type": "unconnected_items", "items": ["a", "b"], "comment": "ok", "state": "live",
                         "reported": True}]  # fmt: skip
        issues, counts = exclusion_issues(stored, report(found), oracle="kicad", design=None)
        assert issues == [] and counts == {"stored": 2, "live": 2, "stale": 0, "unjudged": 0}


def test_an_unrepeatable_pair_not_reported_is_unjudged() -> None:
    stored = pair("unconnected_items", "a", "b")
    rows, _ = accepted_rows(stored, report())
    assert rows[0]["state"] == "unjudged" and rows[0]["reported"] is False
    assert exclusion_issues(stored, report(), oracle="kicad", design=None)[1]["unjudged"] == 2
    assert accepted_rows(stored, None)[0][0]["state"] == "unjudged"


def test_a_stale_pair_gives_one_warning() -> None:
    stored = pair("silk_overlap", "a", "b")
    issues, counts = exclusion_issues(
        stored, report(entry("silk_overlap", "b", "a")), oracle="kicad", design=None
    )
    assert counts == {"stored": 2, "live": 0, "stale": 2, "unjudged": 0}
    (stale,) = issues
    assert stale.code == STALE and "(moved)" in stale.message
    issues, _ = exclusion_issues(stored, report(), oracle="kicad", design=None)
    assert [i.code for i in issues] == [STALE] and "(gone)" in issues[0].message
