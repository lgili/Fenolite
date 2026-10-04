# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The check canary on ``kicad-cli`` (``H-K-CHECK-CANARY-3``; capability kicad-oracle, "Check canary
injection"): it fires once and is silenced by a dropped rules file or an ignored ``clearance`` severity; on
the authored projects it changes nothing else (``check-canary-neutral``), and on the demo boards the
counted report comes from a plain run and two oracle runs repeat as measured (``H-K-DRC-REPEAT``, "DRC
repeatability on the demo boards"). Also records whether KiCad reports on a board Fenolite refuses
(``check-unparsed-drc``, supporting data for ``H-K-SEXPR-STRICT``)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _boardcorpus import READABLE_ITEMS
from _corpus import CorpusItem
from _drcrepeat import repeat_problems
from _probes import run, runner
from _projects import demo_project

from fenolite.backends.kicad.canary import CANARY_TWO_RUN
from fenolite.backends.kicad.oracle import KicadOracle
from fenolite.backends.kicad.projectset import project_set

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
def test_two_run_demo_boards(item: CorpusItem, tmp_path: Path) -> None:
    """Two ``KicadOracle.drc`` runs on a demo board with a ``{}`` project and a ``(version 1)`` rules file.

    Each counted report comes from a plain run, so it holds no canary item (``CANARY_TWO_RUN``, c0013
    Decision 6), and the canary fires. Only on the two boards whose report holds 499 ``clearance``
    violations can KiCad leave the canary's own violation out; the state is then ``inconclusive``
    (``clearance-limit``), never ``absent`` (``H-K-DRC-LIMIT``).

    KiCad does not repeat its report on large boards, so the two runs are compared as measured
    (``tests/_drcrepeat.py``): the report order never counts; on six named boards the entries of three
    named types may differ; everything else must be equal. There is no retry: a difference outside the
    named sets is a finding, to be measured (15 runs) and recorded before a set grows.
    """
    cli = runner()
    assert cli.major() in CANARY_TWO_RUN
    project = project_set(demo_project(tmp_path, item))
    oracle = KicadOracle(cli)
    first, second = oracle.drc(project), oracle.drc(project)
    assert repeat_problems(item.id, first, second) == []
