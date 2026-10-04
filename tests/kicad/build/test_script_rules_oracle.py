# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Script rule minimums are enforced by kicad-cli (capability kicad-oracle, "Script rule minimums are
enforced by kicad-cli"; hypothesis H-K-DSL-MINIMUM; change c0054).

Each case builds the routed blink twice, from scripts that differ in the value of one
``design.rules.minimum`` call: ``pcb drc`` must report the build that breaks the minimum and must not
report the build that respects it. The verdict comes from the DRC JSON report.
"""

from __future__ import annotations

import runpy
from functools import cache

import _buildcases as bc
import pytest
from _buildhelp import ROOT, build

from fenolite.backends.base import DrcViolation
from fenolite.dsl import Design, copper

pytestmark = pytest.mark.needs_kicad
TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]
ROUTED = ROOT / "examples" / "blink_routed"
BOARD = "blink_routed.kicad_pcb"
CLASS_NETS = ("[GND]", "[VIN]")
"""The nets of the class ``PWR`` of the routed blink, as a DRC item description names them."""

CASES: dict[str, tuple[str, str | None, str, str, str]] = {
    # case: (keyword, net class, breaking value, respecting value, DRC violation type)
    "board_track_width": ("track_width", None, "0.4mm", "0.3mm", "track_width"),
    "class_track_width": ("track_width", "PWR", "0.6mm", "0.5mm", "track_width"),
    "board_via_diameter": ("via_diameter", None, "0.7mm", "0.6mm", "via_diameter"),
    "board_via_drill": ("via_drill", None, "0.4mm", "0.3mm", "drill_out_of_range"),
    "board_clearance": ("clearance", None, "1mm", "0.15mm", "clearance"),
    "class_clearance": ("clearance", "PWR", "1mm", "0.2mm", "clearance"),
}


def routed(keyword: str, netclass: str | None, value: str) -> Design:
    design = runpy.run_path(str(ROUTED / "design.py"))["design"]
    assert isinstance(design, Design)
    design.rules.minimum(**{keyword: value}, netclass=netclass)  # type: ignore[arg-type]
    return design


@cache
def violations(target: int, keyword: str, netclass: str | None, value: str) -> tuple[DrcViolation, ...]:
    """The DRC violations of the routed blink built for ``target`` with one minimum."""
    design = routed(keyword, netclass, value)
    output = build(design, target, project_dir=ROUTED, copper_intents=copper(design))
    assert not [i for i in output.issues if i.severity == "error"], output.issues
    assert f"min_{keyword}" in output.files["blink_routed.kicad_dru"].decode("utf-8")
    report = bc.drc(bc._files(output), BOARD).report  # noqa: SLF001
    assert report is not None, "kicad-cli wrote no DRC report"
    return report.violations


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("case", sorted(CASES))
def test_minimum(case: str, target: int) -> None:
    keyword, netclass, breaking, respecting, kind = CASES[case]
    broken = [v for v in violations(target, keyword, netclass, breaking) if v.type == kind]
    kept = [v for v in violations(target, keyword, netclass, respecting) if v.type == kind]
    print(f"{case}, target {target}: {len(broken)} {kind} when broken, {len(kept)} when respected")
    assert broken, f"{case}: kicad-cli did not report the broken minimum"
    assert all(v.severity == "error" for v in broken)
    assert kept == [], f"{case}: kicad-cli reported a respected minimum"
    if case == "class_track_width":
        assert all("Track [GND]" in item.description for v in broken for item in v.items)
    if case == "class_clearance":
        assert all(any(net in item.description for item in v.items for net in CLASS_NETS) for v in broken)
