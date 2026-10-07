# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Grooves narrower than the user's groove width are bridged on the creepage path (capability
board-analyses, "Creepage grooves"; ``H-G-AN-GROOVE``). Every width here is illustrative."""

from __future__ import annotations

import random

from _analysis import MM, SLOT, SLOT_OUTER, at, box, discs, slot_board, with_outline

from fenolite.analysis import analyze_distances, board_boundary, load_requirements
from fenolite.analysis.boundary import BoardBoundary
from fenolite.analysis.grooves import EVIDENCE, bridge_grooves, double_normal2, passes_groove, pockets
from fenolite.analysis.report import DistanceRow
from fenolite.analysis.requirements import SCHEMA
from fenolite.core.evidence import Level

TEE = (at(4.5, -3), at(5.5, -3), at(5.5, 1), at(8, 1), at(8, 5), at(2, 5), at(2, 1), at(4.5, 1))
"""A stem from (4.5 mm, −3 mm) to (5.5 mm, 1 mm) under a head from (2 mm, 1 mm) to (8 mm, 5 mm)."""
PAIR = (("A", "B"),)


def creepage(boundary: BoardBoundary, groove: int | None, design: object = None) -> int:
    made = design if design is not None else slot_board()[0]
    report = analyze_distances(made, pads=None, boundary=boundary, pairs=PAIR, groove=groove)  # type: ignore[arg-type]
    (row,) = report.rows
    assert isinstance(row, DistanceRow) and row.creepage is not None
    return row.creepage.low


def test_double_normals() -> None:
    assert double_normal2(SLOT) == (2 * MM) ** 2 == double_normal2(tuple(reversed(SLOT)))
    assert double_normal2(TEE) == MM**2
    # a right triangle: the height on its longest side, 3 · 4 / 5 mm
    assert double_normal2((at(0, 0), at(4, 0), at(0, 3))) == 2_400_000**2
    slanted = (at(0, 0), at(6, 6), at(5, 7), at(-1, 1))  # a slot 1.414 mm wide, turned by 45°
    assert double_normal2(slanted) == 2 * MM**2
    assert double_normal2((at(0, 0), at(1, 0))) is None and EVIDENCE.level is Level.INFERRED


def test_a_slot_narrower_than_the_groove_width() -> None:
    """Scenario "A slot narrower than the groove width"."""
    _, boundary = slot_board()
    assert creepage(boundary, None) == 11 * MM
    assert creepage(boundary, 2 * MM) == 11 * MM  # the slot's width is not below the groove width
    assert creepage(boundary, 3 * MM) == 9 * MM
    report = analyze_distances(slot_board()[0], pads=None, boundary=boundary, pairs=PAIR, groove=3 * MM)
    assert report.summary["grooves"] == {"3000000": {"bridged": 1, "counted": 0}}
    assert "H-G-AN-GROOVE" in report.evidence.hypotheses and not report.issues
    (row,) = report.rows
    assert isinstance(row, DistanceRow) and row.clearance is not None and row.clearance.low == 9 * MM
    plain = analyze_distances(slot_board()[0], pads=None, boundary=boundary, pairs=PAIR)
    assert "grooves" not in plain.summary and "H-G-AN-GROOVE" not in plain.evidence.hypotheses


def test_a_tee_shaped_cut_out_is_bridged_whole() -> None:
    """Scenario "A T-shaped cut-out is bridged whole"."""
    design = with_outline(discs().build(), SLOT_OUTER, (TEE,))
    assert design.board is not None
    boundary = board_boundary(design.board)
    assert creepage(boundary, None, design) > 9 * MM
    assert creepage(boundary, MM, design) > 9 * MM  # the stem's 1 mm is not below 1 mm
    assert creepage(boundary, 1_100_000, design) == 9 * MM


def test_none_given_warns_for_a_judged_pair_only() -> None:
    """Scenario "No groove width"; c0047's "Measured only" still holds."""
    design, boundary = slot_board()
    row_text = '[[distance]]\na = { net = "A" }\nb = { net = "B" }\ncreepage_nm = 12000000\n'
    text = f'schema = "{SCHEMA}"\n' + row_text
    report = analyze_distances(design, pads=None, boundary=boundary, requirements=load_requirements(text))
    (row,) = report.rows
    assert isinstance(row, DistanceRow) and row.creepage is not None and row.creepage.low == 11 * MM
    below, missing = report.issues
    assert below.code == "analysis.creepage-below"
    assert (missing.code, missing.where) == (
        "analysis.input-missing",
        "groove width",
    ) and "1 pair" in missing.message
    assert report.evidence.level is Level.UNVERIFIED
    measured = analyze_distances(design, pads=None, boundary=boundary, pairs=PAIR)
    assert not measured.issues and measured.evidence.level is Level.INFERRED
    # the row's own groove width governs, and the largest of the two is used
    with_row = load_requirements(text + "groove_nm = 3000000\n")
    own = analyze_distances(design, pads=None, boundary=boundary, requirements=with_row, groove=MM)
    (row,) = own.rows
    assert isinstance(row, DistanceRow) and row.creepage is not None and row.creepage.low == 9 * MM
    assert [found.code for found in own.issues] == ["analysis.creepage-below"]


def test_a_notch_is_filled() -> None:
    """Scenario "A notch is filled"."""
    _, boundary = slot_board(notch=True)
    (pocket,) = pockets(boundary.outer)
    assert pocket.mouth == (at(4, -10), at(6, -10)) and len(pocket.chain) == 4
    assert creepage(boundary, None) == 11 * MM and creepage(boundary, 2 * MM) == 11 * MM
    assert creepage(boundary, 3 * MM) == 9 * MM
    found = bridge_grooves(boundary, 3 * MM)
    assert (found.bridged, found.counted) == (1, 0) and len(found.boundary.outer) == 6
    assert passes_groove((at(0, 0), at(4, 3), at(6, 3), at(10, 0)), boundary)
    assert not passes_groove((at(0, 0), at(10, 0)), boundary)


def test_a_notch_in_the_floor_of_a_wide_bay() -> None:
    """A bay 10 mm wide with a notch 1 mm wide in its floor: the bay is a pocket, the two shoulders of
    board material beside the notch are pockets of the bay, and the notch is not a pocket of its own
    (a limit of the hull tree; ``docs/analyses.md``)."""
    outer = (
        at(0, 0), at(10, 0), at(10, 10), at(14.5, 10), at(14.5, 14), at(15.5, 14), at(15.5, 10), at(20, 10),
        at(20, 0), at(30, 0), at(30, 20), at(0, 20),
    )  # fmt: skip
    boundary = BoardBoundary(outer, (), None, 0, "model")
    (bay,) = pockets(outer)
    assert bay.mouth == (at(10, 0), at(20, 0))
    kept = bridge_grooves(boundary, 2 * MM)
    assert (kept.bridged, kept.counted) == (0, 1) and set(kept.boundary.outer) == set(outer)
    filled = bridge_grooves(boundary, 11 * MM)
    assert (filled.bridged, filled.counted) == (1, 0) and len(filled.boundary.outer) == 6


def test_bridging_never_lengthens_a_creepage_on_generated_boards() -> None:
    rng = random.Random(20261007)
    compared = shorter = 0
    for _ in range(40):
        cutouts = []
        for _ in range(rng.randint(1, 3)):
            x, y = rng.randint(2, 7), rng.randint(-6, 3)
            cutouts.append(box(x, y, x + rng.choice((0.5, 1, 2)), y + rng.randint(1, 5)))
        if any(
            a[0].x <= b[2].x + MM // 2
            and b[0].x <= a[2].x + MM // 2
            and a[0].y <= b[2].y + MM // 2
            and b[0].y <= a[2].y + MM // 2
            for i, a in enumerate(cutouts)
            for b in cutouts[i + 1 :]
        ):
            continue
        design = with_outline(discs().build(), SLOT_OUTER, cutouts)
        assert design.board is not None
        boundary = board_boundary(design.board)
        plain = creepage(boundary, None, design)
        before = plain
        for width in (600_000, 1_100_000, 2_100_000, 6 * MM):
            bridged = creepage(boundary, width, design)
            assert 9 * MM <= bridged <= before, (cutouts, width)
            before = bridged
        assert before == 9 * MM
        shorter += before < plain
        compared += 1
    assert compared >= 15 and shorter >= 5
