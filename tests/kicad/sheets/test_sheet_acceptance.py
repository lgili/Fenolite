# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""v0.1 acceptance item 4: one generated drawing sheet per example is drawn as predicted on every listed
size, with the same bytes on both majors (capability kicad-oracle, "One drawing sheet serves several sizes
on both majors"; change c0012). The exit code is never read."""

from __future__ import annotations

import _acceptance as acc
import _expected as ex
import pytest
from _probes import run
from _sheet_bench import export_sheet_svg

from fenolite.backends.kicad.wks import read_drawing_sheet

pytestmark = pytest.mark.needs_kicad
CASES = [(example, size) for example, sizes in acc.EXAMPLE_SIZES.items() for size in sizes]


@pytest.mark.parametrize("example", list(acc.EXAMPLE_SIZES))
def test_same_bytes_on_both_majors(example: str) -> None:
    print(f"{example}.kicad_wks sha256 {acc.sha256(example)}")  # compared between the two runs
    assert acc.built(example).read_text(encoding="utf-8").startswith("(kicad_wks\n\t(version 20231118)\n")


@pytest.mark.parametrize(("example", "size"), CASES)
def test_acceptance_on_both_majors(example: str, size: str) -> None:
    outcome, problems = acc.accept(example, size)
    assert outcome == "equal", "\n".join(problems)
    assert run(f"wks-accept-{example}-{size.lower()}") == "equal"


@pytest.mark.parametrize("example", list(acc.EXAMPLE_SIZES))
def test_controls(example: str) -> None:
    assert acc.controls(example) == {
        "broken": "reject",
        "missing-file": "absent",
        "project-missing": "absent",
        "skeleton": "load",
    }


def test_wrong_prediction_fails() -> None:
    example, size = "iso5457_generic", "A4"
    case = export_sheet_svg(acc.board(size), acc.built(example))
    assert case.svg is not None
    sheet = read_drawing_sheet(acc.built(example).read_text(encoding="utf-8"))
    texts, lines = acc.prediction(sheet, case.svg, paper="A4", block=ex.TITLE)
    assert acc.problems_for(size, case.svg, texts, lines) == []
    moved = [texts[0].__class__(texts[0].text, texts[0].x + 1, texts[0].y, texts[0].height), *texts[1:]]
    problems = acc.problems_for(size, case.svg, moved, lines)
    assert problems and problems[0].startswith(f"A4: text {texts[0].text!r} not drawn")
