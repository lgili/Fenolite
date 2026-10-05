# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pads whose drill has an offset on the readable demo boards, and the clearance findings that name one
(capability kicad-oracle, "Pad shape offset passes the oracle"; ``H-G-FRAME-OFFSET``; change c0068).

A measurement, never a gate: the test fails only when a board raises. Each board is checked as ``check``
checks it, with the classes and the board minimum of its own project file when the corpus holds one (it
holds no rules file for a demo). Counts go to the JSON file named by ``FENOLITE_CENSUS_OUT``
(``docs/evidence/kicad-frame.md`` is written from it), and nowhere else: no name, value or coordinate of a
board is recorded.
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
from fenolite.model.base import Opaque
from fenolite.model.board import Pad
from fenolite.model.design import Design

pytestmark = [pytest.mark.needs_corpus, pytest.mark.slow]


def items() -> tuple[CorpusItem, ...]:
    found = checked_items()
    if not found:
        require(READABLE_ITEMS[0])  # skips, or fails in required-resource mode
    return found


def has_offset_drill(pad: Pad) -> bool:
    """True when the pad's drill node, kept opaque by the reader, holds an ``offset`` child."""
    return any(
        isinstance(slot, Opaque) and slot.fragment.startswith("(drill") and "(offset" in slot.fragment
        for slot in slotlib.from_ext(pad.ext["kicad"])
    )


def offset_census(design: Design, project_text: str | None) -> dict[str, int]:
    """Pads, pads with an offset drill, clearance findings, and the findings that name such a pad, by the
    kinds of the two items."""
    major = project_major(project_text)
    rules = design_rules_from_texts(design, project_text=project_text, rules_text=None, major=major)
    board = rules.design.board
    assert board is not None
    pads = [pad for footprint in board.footprints for pad in footprint.pads]
    offset = {pad.id for pad in pads if has_offset_drill(pad)}
    report = check_copper(
        rules.design,
        pads=KicadBackend().board_pads(rules.design),
        min_clearance=rules.min_clearance,
        rules_over_classes=rules.rules_over_classes,
        floor_over_rules=rules.floor_over_rules,
    )
    counts: Counter[str] = Counter(
        pads=len(pads), pads_with_offset_drill=len(offset), project_file=int(project_text is not None)
    )
    counts["clearance_findings"] = 0
    counts["clearance_findings_naming_an_offset_pad"] = 0
    for finding in report.findings:
        if finding.code != "copper.clearance":
            continue
        counts["clearance_findings"] += 1
        if any(item.entity_id in offset for item in finding.items):
            counts["clearance_findings_naming_an_offset_pad"] += 1
            kinds = "+".join(sorted(item.kind for item in finding.items))
            counts[f"naming_an_offset_pad:{kinds}"] += 1
    return dict(sorted(counts.items()))


def test_offset_census_on_the_demo_boards() -> None:
    """Scenario "The census is recorded"."""
    measured = 0
    for item in items():
        design, _ = read(item.path)
        project = project_of(item)
        text = project.read_text(encoding="utf-8") if project is not None else None
        data = offset_census(design, text)
        census("copper_offset", item.id, data)
        print(item.id, data)
        measured += 1
    assert measured == len(items())
