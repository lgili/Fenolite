# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The types of KiCad's parity test per board edit, on the running major (capability kicad-oracle, "Parity
types are probed"; ``H-K-PARITY-TYPES``; change c0072). The probes run on the blink that ``build`` writes;
the demo case repeats them on ``pic_programmer`` when the corpus cache holds it."""

from __future__ import annotations

from pathlib import Path

import _paritycases as cases
import _paritycorpus as corpus
import pytest
from _erccases import runner
from _probes import run

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("edit", cases.PROBED)
def test_types_on_the_built_blink(edit: str) -> None:
    found = cases.blink_types(edit)
    assert found is not None, "kicad-cli wrote no DRC report"
    print(f"parity-type-{edit}: {dict(found)}")
    assert cases.expected(edit, found), f"{edit}: {dict(found)}, expected {dict(cases.EXPECTED[edit])}"
    assert run(f"parity-type-{edit}") == "equal"


def test_every_entry_is_a_warning_or_an_error(tmp_path: Path) -> None:
    """The parity entries carry the severities of the project, as other DRC entries do."""
    board, _ = cases.blink_project(tmp_path)
    cases.with_edit(board, "ref", cases.BLINK)
    report = corpus.kicad_parity(runner(), board)
    assert report is not None and report.schematic_parity
    assert {entry.severity for entry in report.schematic_parity} <= {"warning", "error"}


@pytest.mark.needs_corpus
@pytest.mark.parametrize("edit", cases.PROBED)
def test_types_on_the_demo(edit: str, tmp_path: Path) -> None:
    project = cases.pic_project(tmp_path)
    if project is None:
        pytest.skip("the pic_programmer demo of this major's tag is not in the corpus cache")
    board, _ = project
    before = corpus.kicad_parity(runner(), board)
    cases.with_edit(board, edit, cases.PIC)
    report = corpus.kicad_parity(runner(), board)
    assert before is not None and report is not None, "kicad-cli wrote no DRC report"
    # the demo of tag 9.0.9.1 disagrees with its schematic as published: the edit adds to that
    base = cases.types_of(before)
    found = {kind: count - base.get(kind, 0) for kind, count in cases.types_of(report).items()}
    found = {kind: count for kind, count in found.items() if count}
    print(f"pic_programmer {edit}: {found} more than the published demo's {base}")
    mismatched = bool(base.get(cases.MISMATCH))
    assert cases.expected(edit, found, mismatched=mismatched), (
        f"{edit}: {found}, expected {dict(cases.EXPECTED[edit])}"
    )
