# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What KiCad's DRC does with the pair values of a net class (capability kicad-oracle, "Net class pair
values are probed"; hypothesis H-K-PRO-PAIR; change c0104): a pair gap below the class clearance lowers
the clearance inside a pair where no custom clearance rule governs it, a board minimum above the gap is a
floor and adds a gap check, and the pair width, the via gap and the gap itself are no limits.

Every run carries the canary scoped to ``CANARY_A``; a report without it fails with "rules file not
loaded". ``tests/kicad/test_probe_results.py`` pins every outcome per version."""

from __future__ import annotations

import _pairclasses as pc
import _rulebench as rb
import pytest
from _probes import run

from fenolite.backends.kicad import _json
from fenolite.backends.kicad._json import JsonNumber

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("case", sorted(pc.CASES))
def test_pair_class_case(case: str) -> None:
    """Scenario "Class values on both majors"."""
    result = pc.RUNS[case]()
    rb.require_canary(result.report, result.bench)
    function, expected = pc.CASES[case]
    assert function() == expected, f"{case}: KiCad and the measured outcome differ"
    assert run(f"pro-pair-{case}") == expected


def test_written_project_holds_the_pair_values() -> None:
    """The bench's project is the one the triad path writes: each class entry holds its three pair
    values."""
    data = _json.loads(pc.classes().files[pc.PROJECT])
    entries = {entry["name"]: entry for entry in data["net_settings"]["classes"]}
    assert entries["DPA"]["diff_pair_gap"] == JsonNumber("0.1")
    assert entries["DPA"]["diff_pair_width"] == JsonNumber("0.3")
    assert entries["DPA"]["diff_pair_via_gap"] == JsonNumber("0.5")
    assert entries["DPC"]["clearance"] == JsonNumber("0.1")
