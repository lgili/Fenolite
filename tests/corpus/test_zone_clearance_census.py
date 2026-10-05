# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Clearance findings whose value is a zone's own clearance, on the readable demo boards (capability
kicad-oracle, "Fresh fills stay clean under the zone clearance"; ``H-K-COPPER-ZONECLR``; change c0068).

A measurement, never a gate: a demo's stored fill may be stale, so the test fails only when a board
raises. Each board is checked as ``check`` checks it, with the classes and the board minimum of its own
project file when the corpus holds one (it holds no rules file for a demo). The findings of source
``zone`` are counted per kind of the other item, and so are those that name a pad with a clearance
override of its own or of its footprint, which the copper check does not model (design, Open Questions).
Each board is checked a second time with the zone's value switched off, so the census tells the findings
that the zone's clearance ADDS from the pairs that were findings already and only change their source.
Counts go to the JSON file named by ``FENOLITE_CENSUS_OUT`` (``docs/evidence/copper-check.md`` is written
from it), and nowhere else: no name, value or coordinate of a board is recorded.
"""

from __future__ import annotations

from collections import Counter

import pytest
from _boardcorpus import READABLE_ITEMS, checked_items, project_of, read
from _boards import census
from _corpus import CorpusItem, require

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.copperrules import design_rules_from_texts, project_major
from fenolite.checks import check_copper
from fenolite.checks import copper as copper_module
from fenolite.checks.copper import CopperFinding
from fenolite.model.base import Opaque
from fenolite.model.design import Design

pytestmark = [pytest.mark.needs_corpus, pytest.mark.slow]


def items() -> tuple[CorpusItem, ...]:
    found = checked_items()
    if not found:
        require(READABLE_ITEMS[0])  # skips, or fails in required-resource mode
    return found


def _has_clearance(entity: object) -> bool:
    """True when the entity's own node holds a ``(clearance …)`` child, which the reader keeps opaque."""
    return any(
        isinstance(slot, Opaque) and slot.fragment.startswith("(clearance")
        for slot in slotlib.from_ext(getattr(entity, "ext", {}).get("kicad", ()))
    )


def _pair(finding: CopperFinding) -> frozenset[str]:
    return frozenset(item.entity_id for item in finding.items)


def zone_census(design: Design, project_text: str | None, monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    major = project_major(project_text)
    rules = design_rules_from_texts(design, project_text=project_text, rules_text=None, major=major)
    board = rules.design.board
    assert board is not None
    overridden = {
        pad.id
        for footprint in board.footprints
        for pad in footprint.pads
        if _has_clearance(pad) or _has_clearance(footprint)
    }
    filled = [zone for zone in board.zones if zone.fills]
    pads = KicadBackend().board_pads(rules.design)

    def check() -> tuple[CopperFinding, ...]:
        return check_copper(
            rules.design,
            pads=pads,
            min_clearance=rules.min_clearance,
            rules_over_classes=rules.rules_over_classes,
            floor_over_rules=rules.floor_over_rules,
        ).findings

    found = check()
    with monkeypatch.context() as patch:  # the rule of c0029: no zone value for any pair
        patch.setattr(copper_module._Judge, "_zone_clearance", lambda self, a, b: None)  # pyright: ignore[reportPrivateUsage]
        before = {_pair(f) for f in check() if f.code == "copper.clearance"}
    counts: Counter[str] = Counter(
        zones_with_fills=len(filled),
        zones_with_fills_and_a_clearance=sum(1 for zone in filled if zone.settings.clearance > 0),
        pads_with_a_clearance_override=len(overridden),
        project_file=int(project_text is not None),
        clearance_findings=0,
        clearance_findings_without_the_zone_value=len(before),
        clearance_findings_of_source_zone=0,
        added_by_the_zone_value=0,
        added_naming_an_overridden_pad=0,
    )
    for finding in found:
        if finding.code != "copper.clearance":
            continue
        counts["clearance_findings"] += 1
        if finding.source != "zone":
            continue
        counts["clearance_findings_of_source_zone"] += 1
        if _pair(finding) in before:
            continue
        (other,) = [item for item in finding.items if item.kind != "fill"]
        counts["added_by_the_zone_value"] += 1
        counts[f"added:{other.kind}"] += 1
        if other.entity_id in overridden:
            counts["added_naming_an_overridden_pad"] += 1
    return dict(sorted(counts.items()))


def test_zone_clearance_census_on_the_demo_boards(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "The corpus census is recorded"."""
    measured = 0
    for item in items():
        design, _ = read(item.path)
        project = project_of(item)
        text = project.read_text(encoding="utf-8") if project is not None else None
        data = zone_census(design, text, monkeypatch)
        census("zone_clearance", item.id, data)
        print(item.id, data)
        measured += 1
    assert measured == len(items())
