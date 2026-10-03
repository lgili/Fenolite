# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The netlist oracle on ``kicad-cli`` (capability kicad-oracle, "Netlist oracle from IPC-D-356";
``H-K-NET-IPC``): the export's partition equals the board's on the authored built project, and two nets
whose names share their last 14 characters become coverage, never a short."""

from __future__ import annotations

import pytest
from _netcases import COLLIDING, authored, board, collision, netlist
from _probes import run

from fenolite.checks.assignment_compare import board_netlist, compare

pytestmark = pytest.mark.needs_kicad


def test_partition() -> None:
    assert run("netlist-partition") == "equal"
    outcome = netlist(authored())
    assert outcome.netlist is not None and outcome.netlist.uncovered == ()
    listed, unnumbered = board_netlist(board(authored()))
    result = compare(listed, outcome.netlist)
    assert result.differences == () and result.common == len({a.element for a in listed.assignments})
    assert unnumbered == 0 and outcome.evidence.oracle.startswith("kicad-cli ")


def test_collision() -> None:
    assert run("netlist-label-collision") in {"equal", "different"}
    outcome = netlist(collision())
    assert outcome.netlist is not None
    ambiguous = {u.element for u in outcome.netlist.uncovered if u.reason == "net-label-ambiguous"}
    assert ambiguous == set(COLLIDING)
    listed, _ = board_netlist(board(collision()))
    result = compare(listed, outcome.netlist)
    assert result.differences == ()
    assert {u.element for u in result.only_a if u.reason == "net-label-ambiguous"} == set(COLLIDING)
