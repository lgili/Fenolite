# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Outline shapes on the running ``kicad-cli`` (capability kicad-oracle, "Outline shapes and holes pass the
oracle"; hypotheses H-K-OUTLINE-ARCS, H-K-OUTLINE-INVALID and H-K-OUTLINE-OUTSIDE; change c0102).

The boards are those of ``_outlinebench``: each probe records the board written with its edges as
``Edge.Cuts`` graphics, and the same board built from a script must give the same outcome."""

from __future__ import annotations

import _outlinebench as ob
import pytest
from _probes import major, run

from fenolite.backends.kicad.outline import board_outline, check_outline
from fenolite.backends.kicad.pcb import read_board
from fenolite.dsl import to_model

pytestmark = pytest.mark.needs_kicad
INVALID_ON_10 = {"cross", "touch", "overlap", "selfx"}
INVALID_ON_9 = {"overlap"}
"""The malformed outlines for which each major reports ``invalid_outline`` (``H-K-OUTLINE-INVALID``). 9.0.9
reports none for the self-crossing ring of the bench (``outline-invalid-selfx`` ``absent`` in
``9.0.9.json``)."""


def test_arcs_drc() -> None:
    assert run("outline-arcs-drc") == "absent", "KiCad calls the outline of lines and arcs invalid"
    assert ob.arcs_drc("script") == "absent", "the board built from the script differs"


def test_arcs_drill() -> None:
    assert run("outline-arcs-drill") == "absent", "a cut-out reached a drill file"
    assert ob.arcs_drill("script") == "absent", "the board built from the script differs"


def test_arcs_rings_read_back() -> None:
    for form in ob.FORMS:
        text = dict(ob.arcs_files(form))["blink.kicad_pcb"]
        found = board_outline(read_board(text.decode("utf-8") if isinstance(text, bytes) else text))
        assert len(found.rings) == 5 and found.problem == "" and not found.exact, form


@pytest.mark.kicad_min_major(10)
def test_arcs_keep() -> None:
    assert run("outline-arcs-keep") == "equal", "a re-save changed the signature of the outline"


@pytest.mark.parametrize("case", ob.INVALID_CASES)
def test_invalid_outlines(case: str) -> None:
    wanted = INVALID_ON_10 if major() >= 10 else INVALID_ON_9
    assert run(f"outline-invalid-{case}") == ("present" if case in wanted else "absent")
    # the build's check takes KiCad's strictest verdict, and refuses the nested cut-out too
    codes = [issue.code for issue in check_outline(to_model(ob.invalid_script(case)))]
    assert codes == ([] if case == "inside" else ["kicad.outline.invalid"])


def test_copper_outside_the_outline() -> None:
    assert run("outline-outside-free") == "absent", "KiCad reports copper wholly outside the outline"
    assert run("outline-outside-across") == "present", "KiCad does not report copper across the edge"
