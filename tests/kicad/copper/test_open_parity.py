# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Open connections against KiCad's unconnected items (change c0108; capability kicad-oracle, "Open
connections agree with unconnected items"; ``H-K-CONN-PARITY``).

The hermetic half needs no tool: the query gives the expected count of every case. The KiCad half runs
``kicad-cli pcb drc`` on the bench written for the running major and compares, per case, the unconnected
items whose items all belong to the case's net.
"""

from __future__ import annotations

import _openbench as ob
import pytest


@pytest.mark.parametrize("target", [9, 10])
def test_hermetic_counts(target: int) -> None:
    """Scenario "Hermetic counts": the query gives the expected count of every case."""
    assert ob.query_counts(ob.open_bench(target)) == ob.EXPECTED


def test_hermetic_bench_holds_the_cases_of_the_design() -> None:
    assert len(ob.EXPECTED) == 19
    bench = ob.open_bench(10)
    assert set(bench.uuids) == set(ob.EXPECTED)
    report = ob.query(bench.design)
    assert report.issues == ()
    assert {net.name for net in report.nets} == {ob.net_name(case) for case in ob.EXPECTED}


@pytest.mark.needs_kicad
def test_kicad_counts_are_those_of_the_design() -> None:
    """Probe ``copper-open-kicad``: KiCad's count per case, without the query. A count that differs from
    the design's measurement stops the change."""
    found = ob.kicad_case_counts()
    assert found is not None, "kicad-cli wrote no DRC report for the bench"
    assert found == ob.EXPECTED
    assert found["stub"] == 1 and found["crossing"] == 0
    assert ob.kicad_outcome() == "equal"


@pytest.mark.needs_kicad
def test_kicad_parity_with_the_query() -> None:
    """Scenario "Parity on both majors": ``copper-open-parity`` is ``equal``."""
    assert ob.parity_outcome() == "equal"
