# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The net-class bench without KiCad (capability kicad-oracle, "Net-class rules are enforced by
kicad-cli", scenario "Canary missing"; change c0010)."""

from __future__ import annotations

import json

import _netclass_bench as nb
import pytest

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad.drc import read_drc_report
from fenolite.backends.kicad.triad import write_triad
from fenolite.core.errors import Issue
from fenolite.model.design import Design

DESIGN = nb.bench_design(target=10)


def report(design: Design, *pairs: tuple[str, str]) -> DrcReport:
    """An authored report text holding one clearance violation per uuid pair, read with read_drc_report."""
    violations = [
        {
            "type": "clearance",
            "description": "authored",
            "severity": "error",
            "items": [{"uuid": u, "description": "track", "pos": {"x": 1, "y": 2}} for u in pair],
        }
        for pair in pairs
    ]
    text = json.dumps(
        {
            "source": "bench.kicad_pcb",
            "date": "2026-10-02",
            "kicad_version": "10.0.6",
            "violations": violations,
            "unconnected_items": [],
            "schematic_parity": [],
            "coordinate_units": "mm",
        }
    )
    return read_drc_report(text)


CANARY = (nb.track_uuid(DESIGN, "CANARY_A"), nb.track_uuid(DESIGN, "CANARY_B"))
HV = tuple(nb.row_uuids(DESIGN, net) for net in nb.HV_NETS)


def test_bench_synthesises_without_issues() -> None:
    issues: list[Issue] = []
    files = write_triad(DESIGN, name="bench", target=10, issues=issues)
    assert issues == [] and sorted(files) == ["bench.kicad_dru", "bench.kicad_pcb", "bench.kicad_pro"]
    assert '"pattern": "+3V3"' in files["bench.kicad_pro"] and '"pattern": "SIG1"' in files["bench.kicad_pro"]
    assert "A.NetName == 'CANARY_A'" in files["bench.kicad_dru"]


def test_rows() -> None:
    assert len(nb.ROWS) == 12 and set(nb.ROWS.values()) == {"GND"}
    assert nb.watched("decoys") == nb.DECOYS and nb.watched("anchor") == ("SIG10",)
    assert nb.watched("patterns") == ("Net-(R1-Pad1)", "D[0]", "IN+", "VCC_3.3", "SW1_A")


def test_judge_outcomes() -> None:
    full = report(DESIGN, CANARY, *HV)
    assert nb.judge(full, case="full", design=DESIGN) == "present"
    assert nb.judge(report(DESIGN, CANARY), case="noclass", design=DESIGN) == "absent"
    assert nb.judge(report(DESIGN, CANARY, HV[0]), case="full", design=DESIGN) == "different"
    assert nb.judge(report(DESIGN, CANARY), case="noproject", design=DESIGN) == "absent"
    assert nb.judge(full, case="minimal", design=DESIGN, reference=full) == "equal"
    assert nb.judge(report(DESIGN, CANARY), case="minimal", design=DESIGN, reference=full) == "different"


def test_canary_missing() -> None:
    without = report(DESIGN, *HV)
    for case in ("full", "noproject"):
        outcome = nb.judge(without, case=case, design=DESIGN)
        assert outcome == "inconclusive"
        with pytest.raises(pytest.fail.Exception, match="rules file not loaded"):
            nb.assert_loaded(outcome, case)
    assert nb.judge(None, case="full", design=DESIGN) == "inconclusive"
    nb.assert_loaded("present", "full")
