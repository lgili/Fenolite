# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Verdict classes of the drawing-sheet oracle on fake runs (capability kicad-oracle, "Drawing sheets
are judged by what KiCad draws"; change c0012). No ``kicad-cli`` is run."""

from __future__ import annotations

from decimal import Decimal

from _sheet_bench import DRAWING_SHEET_ERROR, Expected, SheetCase, board_text, classify, compare
from _svg import Segment, SheetSvg, SvgText

D = Decimal


def svg(*texts: str, paths: tuple[Segment, ...] = ()) -> SheetSvg:
    return SheetSvg(
        D("297.0022"),
        D("210.0072"),
        tuple(SvgText(t, D(10 + i), D(20), "start", D("2")) for i, t in enumerate(texts)),
        paths,
    )


def case(*texts: str, lines: tuple[str, ...] = (), outcome: str = "exit") -> SheetCase:
    return SheetCase(outcome, lines, svg(*texts))


DEFAULT = case("Date:", "Rev:", "Size: A4")
CONTROL = case("1", "2", "Title")


def test_reject_on_message_whatever_the_drawing() -> None:
    broken = case(*DEFAULT.strings(), lines=(f"{DRAWING_SHEET_ERROR}: board.kicad_wks",))
    assert classify(broken, default=DEFAULT, control=CONTROL, marker="Broken") == "reject"


def test_silent_fallback_is_absent() -> None:
    assert classify(case(*DEFAULT.strings()), default=DEFAULT, control=CONTROL) == "absent"


def test_load_needs_the_marker() -> None:
    assert classify(case("Alpha", "Bravo"), default=DEFAULT, control=CONTROL, marker="Alpha") == "load"
    assert classify(case("Alpha", "Bravo"), default=DEFAULT, control=CONTROL) == "load"


def test_marker_missing_is_not_a_load() -> None:
    other = case("Something", "else")
    assert classify(other, default=DEFAULT, control=CONTROL, marker="Alpha") == "different"


def test_failed_control_makes_the_session_inconclusive() -> None:
    fallback_control = case(*DEFAULT.strings())
    for sheet_case in (case("Alpha"), case(*DEFAULT.strings()), case("x", lines=(DRAWING_SHEET_ERROR,))):
        outcome = classify(sheet_case, default=DEFAULT, control=fallback_control, marker="Alpha")
        assert outcome == "inconclusive"


def test_default_without_text_is_inconclusive() -> None:
    assert classify(case("Alpha"), default=case(), control=CONTROL, marker="Alpha") == "inconclusive"


def test_no_svg_and_timeout() -> None:
    assert classify(SheetCase("exit", (), None), default=DEFAULT, control=CONTROL) == "inconclusive"
    assert classify(SheetCase("timeout", (), None), default=DEFAULT, control=CONTROL) == "timeout"


def test_compare_tolerances() -> None:
    drawn = svg("A", paths=(Segment(D(10), D(10), D(20), D(10)),))  # "A" anchored at (10, 20)
    assert compare(drawn, [Expected("A", D("10.005"), D(19), D(2))], [(D(20), D(10), D(10), D(10))]) == []
    assert compare(drawn, [Expected("A", D("10.02"), D(20), D(2))])  # x off by 0.02 mm
    assert compare(drawn, [Expected("A", D(10), D("18.9"), D(2))])  # y off by more than half the height
    assert compare(drawn, [Expected("A", D(10), D(20), D(2))], [(D(10), D(10), D(20), D("10.02"))])
    assert compare(drawn, []) == ["unpredicted text 'A' at (10, 20)"]


def test_board_text_paper_and_title_block() -> None:
    text = board_text(paper='(paper "User" 300 200)', title_block='(title_block (title "Bench"))')
    paper = text.index('(paper "User" 300 200)')
    assert paper < text.index("(title_block") < text.index("(layers")
