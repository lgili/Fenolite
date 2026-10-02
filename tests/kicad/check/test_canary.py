# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The check canary on ``kicad-cli`` (``H-K-CHECK-CANARY``; capability kicad-oracle, "Check canary
injection"): it fires once, changes nothing else, and is silenced by a dropped rules file or an ignored
``clearance`` severity. Also records whether KiCad reports on a board Fenolite refuses
(``check-unparsed-drc``, supporting data for ``H-K-SEXPR-STRICT``)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _boardcorpus import READABLE_ITEMS
from _checkcases import canary_drc, compare, plain_drc, violations
from _corpus import CorpusItem
from _probes import run
from _projects import demo_project

from fenolite.backends.kicad.canary import strip_canary

pytestmark = pytest.mark.needs_kicad
DEMOS = [item for item in READABLE_ITEMS if not item.heavy]


def test_canary_fires() -> None:
    assert run("check-canary-fired") == "present"


def test_canary_neutral() -> None:
    assert run("check-canary-neutral") == "equal"


def test_canary_broken_rules() -> None:
    assert run("check-canary-broken") == "absent"


def test_canary_ignored() -> None:
    assert run("check-canary-ignored") == "absent"


def test_unparsed_drc() -> None:
    assert run("check-unparsed-drc") in {"present", "absent"}


@pytest.mark.needs_corpus
@pytest.mark.slow
@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("item", DEMOS, ids=lambda i: i.id)
def test_canary_neutral_demo_boards(item: CorpusItem, tmp_path: Path) -> None:
    """The stripped canary run of a demo board with a ``{}`` project and a ``(version 1)`` rules file
    reports what a plain run reports.

    On boards with many clearance violations, kicad-cli 10.0.6 names a different partner item, and
    sometimes reports another count, from one identical run to the next. A difference therefore stands
    only on a board whose plain report KiCad repeats over three more runs; otherwise neutrality cannot be
    judged there, and the case is skipped with that reason.
    """
    root = demo_project(tmp_path, item)
    staged = canary_drc(root).report
    stripped = None if staged is None else strip_canary(staged)[0]
    outcome = compare(stripped, lambda: plain_drc(root).report)
    if outcome == "different":
        first = plain_drc(root).report
        repeats = [plain_drc(root).report for _ in range(3)]
        if first is None or any(r is None or violations(r) != violations(first) for r in repeats):
            outcome = "inconclusive"
    if outcome == "inconclusive":
        pytest.skip(f"{item.id}: plain runs of kicad-cli differ, so neutrality cannot be judged")
    assert outcome == "equal"
