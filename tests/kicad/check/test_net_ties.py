# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What KiCad's DRC reports on a footprint with ``net_tie_pad_groups`` (``H-K-NETTIE-DRC``; capability
kicad-oracle, "Net-tie facts are probed"; change c0114).

The bench of ``_tiebench.py`` runs once per session on the running ``kicad-cli``, and the DRC is judged
only from its JSON report. A report without the control pair's ``clearance`` violation fails the test.
``tests/kicad/test_probe_results.py`` pins every outcome per version.
"""

from __future__ import annotations

import _tiebench as tb
import pytest
from _probes import run

from fenolite.backends.kicad.pcb import read_board

pytestmark = pytest.mark.needs_kicad


def test_net_tie_control_pair_fires() -> None:
    """The control pair proves that the DRC judged the board."""
    assert tb.judged_report().violations


def test_net_tie_written_token_loads() -> None:
    """Scenario "The written token loads": the board that Fenolite wrote for the running major loads in
    ``pcb drc``, and reading it back gives the declared groups of every footprint."""
    bench = tb.tie_bench(tb.running_target())
    assert tb.kicad_report() is not None
    design = read_board(bench.text)
    assert design.board is not None
    refs = {component.id: component.ref for component in design.circuit.components}
    by_ref = {refs[placed.component_id]: placed for placed in design.board.footprints}
    for label, ref in bench.refs.items():
        case, grouped = tb.case_of(label)
        assert by_ref[ref].net_ties == (case.groups if grouped else ()), label
    assert bench.text.count("(net_tie_pad_groups ") == len(tb.CASES)
    assert bench.text.count('(net_tie_pad_groups "1,2")') == 1  # the spelling case


@pytest.mark.parametrize("label", tb.LABELS)
def test_net_tie_facts(label: str) -> None:
    """Scenario "Net-tie facts on both majors": the DRC types between the items of each footprint are the
    expected ones, with its groups and in the copy without them."""
    assert tb.kicad_types(label) == tb.expected(label), label
    assert run(f"nettie-{label}") == "equal"


def test_net_tie_token_changes_the_verdict() -> None:
    """The copies without groups are reported, so a silent bench cannot pass for an exempt one."""
    for label in tb.LABELS:
        if label.endswith(tb.PLAIN):
            assert tb.kicad_types(label), label
            assert tb.kicad_types(label) != tb.kicad_types(label.removesuffix(tb.PLAIN)) or label.startswith(
                "track-near"
            )
