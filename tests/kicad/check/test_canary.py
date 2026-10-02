# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The check canary on ``kicad-cli`` (``H-K-CHECK-CANARY-2``; capability kicad-oracle, "Check canary
injection"): it fires once and is silenced by a dropped rules file or an ignored ``clearance`` severity; on
the authored projects it changes nothing else (``check-canary-neutral``), and on the demo boards the
counted report comes from a plain run. Also records whether KiCad reports on a board Fenolite refuses
(``check-unparsed-drc``, supporting data for ``H-K-SEXPR-STRICT``)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _boardcorpus import READABLE_ITEMS
from _corpus import CorpusItem
from _probes import run, runner
from _projects import demo_project

from fenolite.backends.kicad.canary import CANARY_TWO_RUN, CANARY_UUIDS
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
    """On a demo board with a ``{}`` project and a ``(version 1)`` rules file, the canary fires and the
    counted report comes from the plain run, so it holds no canary item.

    The canary is not neutral on such boards: with its tracks present, 9.0.9 and 10.0.6 name other partner
    items for some clearance violations, and sometimes report one violation more or less, run after run
    (``H-K-CHECK-CANARY``, refuted). Hence ``CANARY_TWO_RUN`` (c0013 Decision 6).
    """
    cli = runner()
    assert cli.major() in CANARY_TWO_RUN
    outcome = KicadOracle(cli).drc(project_set(demo_project(tmp_path, item)))
    assert (outcome.canary, outcome.canary_removed) == ("fired", 0)
    assert outcome.report is not None
    named = {i.uuid for v in (*outcome.report.violations, *outcome.report.unconnected_items) for i in v.items}
    assert not named & set(CANARY_UUIDS)
