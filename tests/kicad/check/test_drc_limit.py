# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad's clearance report limit and the canary verdict at it (``H-K-DRC-LIMIT``, ``H-K-CHECK-CANARY-3``;
capability kicad-oracle, "Clearance report limit"; change c0051).

``kicad-cli`` stops reporting ``clearance`` violations near 499 per run. On a board with more, the check
canary's own violation competes for a place, so it can be missing from a run that loaded the rules. The
oracle must then say ``inconclusive`` (``clearance-limit``), never ``absent``. The bench is authored
(``_limitbench.py``), so both oracle jobs run it without the corpus.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _limitbench import clearance_count, limit_project
from _resources import kicad_cli

from fenolite.backends.kicad.canary import CLEARANCE_REPORT_LIMIT
from fenolite.backends.kicad.cli import KicadCli, cli_for
from fenolite.backends.kicad.oracle import KicadOracle
from fenolite.backends.kicad.projectset import project_set

pytestmark = pytest.mark.needs_kicad
BELOW, ABOVE = 300, 700
"""Pairs of the bench: far below the limit, and far above it."""
RUNS = 5


def _cli() -> KicadCli:
    path = kicad_cli()
    assert path is not None  # the needs_kicad marker skips before this is reached
    return cli_for(Path(path), timeout=600)  # a binary, or a ``docker:<image>`` marker


def test_count_stops_near_the_limit(tmp_path: Path) -> None:
    cli = _cli()
    own = clearance_count(cli, limit_project(tmp_path / "none", 0))
    assert clearance_count(cli, limit_project(tmp_path / "below", BELOW)) == own + BELOW
    above = clearance_count(cli, limit_project(tmp_path / "above", ABOVE))
    assert CLEARANCE_REPORT_LIMIT <= above < ABOVE, above
    if cli.major() >= 10:  # 10.0.6 stops exactly at the limit; 9.0.9 a few violations later
        assert above == CLEARANCE_REPORT_LIMIT


def test_verdict_is_never_absent_at_the_limit(tmp_path: Path) -> None:
    oracle = KicadOracle(_cli())
    below = oracle.drc(project_set(limit_project(tmp_path / "below", BELOW)))
    assert (below.canary, below.canary_reason, below.canary_removed) == ("fired", "", 0)
    project = project_set(limit_project(tmp_path / "above", ABOVE))
    states = [(o.canary, o.canary_reason) for o in (oracle.drc(project) for _ in range(RUNS))]
    allowed = {("fired", ""), ("inconclusive", "clearance-limit")}
    assert set(states) <= allowed, states  # the rules load, so "absent" would be a false verdict
