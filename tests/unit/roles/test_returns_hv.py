# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The return and high-voltage checks on ``analyze_returns`` and ``analyze_distances`` (change c0222;
capability net-roles, "Returns and high voltage": "A high-voltage bus without a requirement", "A cell tap
across a ground gap")."""

from __future__ import annotations

from collections.abc import Callable

from _roleboards import Built, judge
from _rolecheck import DECLARED, checked, confirmed

from fenolite.analysis.requirements import load_requirements
from fenolite.model.rules import RoleLimit, RoleSet
from fenolite.roles.measure import Inputs

TIGHT = """\
schema = "fenolite.requirements.v0"

[[distance]]
a = { net = "VBUS" }
b = { net = "*" }
clearance_nm = 2000000
creepage_nm = 2000000
"""


def _half_bridge(reference: Callable[..., Built], inputs: Inputs, declared: RoleSet | None = None) -> list:
    built = reference("half_bridge", "good")
    roles = declared if declared is not None else DECLARED["half_bridge"]
    stored = confirmed(judge(built, declared=roles, check=False))
    return list(judge(built, declared=roles, stored=stored, inputs=inputs).issues)


def test_a_high_voltage_bus_without_a_requirement(reference: Callable[..., Built]) -> None:
    issues = _half_bridge(reference, Inputs())
    (missing,) = [i for i in issues if i.code == "roles.limit-missing"]
    assert missing.where == "VBUS" and missing.severity == "warning"
    assert "Fenolite ships no creepage or clearance table" in missing.message
    assert not [
        i for i in issues if i.code.startswith("analysis.clearance") or i.code.startswith("analysis.creepage")
    ]


def test_the_rows_judge_the_bus_with_the_analysis_codes(reference: Callable[..., Built]) -> None:
    rows = load_requirements(TIGHT, file="tight.toml")
    issues = _half_bridge(reference, Inputs(requirements=rows))
    assert not [i for i in issues if i.code == "roles.limit-missing"]
    below = [i for i in issues if i.code == "analysis.clearance-below"]
    assert below and all("VBUS" in i.message for i in below)
    assert any("clearance between SW and VBUS is 1.6 mm on F.Cu" in i.message for i in below)
    assert not [i for i in issues if i.code.startswith("roles.") and "clearance" in i.code]


def test_a_threshold_above_the_working_voltage(reference: Callable[..., Built]) -> None:
    roles = DECLARED["half_bridge"]
    over = RoleSet(nets=roles.nets, limits=(*roles.limits, RoleLimit("high_voltage_mv", 500_000)))
    issues = _half_bridge(reference, Inputs(), over)
    assert not [i for i in issues if i.code == "roles.limit-missing"]


def test_a_cell_tap_across_a_ground_gap(reference: Callable[..., Built]) -> None:
    judged = checked(reference, "bms", "bad")
    (gap,) = [i for i in judged.issues if i.code == "roles.return-gap"]
    assert gap.where == "TAP0@/kicad_pcb/segment[27]"
    assert (
        "crosses a gap of its ground on F.Cu for 0.8 mm, from (166.4, 108.27) mm to (165.6, 108.27) mm"
        in gap.message
    )
    assert not [i for i in judged.issues if i.code == "analysis.return-split"]
    good = checked(reference, "bms", "good")
    assert not [i for i in good.issues if i.code in ("roles.return-gap", "analysis.return-split")]
    returns = {m.subject for m in good.measured.measures if m.kind == "return"}
    assert {"TAP0", "TAP1", "TAP2", "TAP3", "CHG_G", "DSG_G"} <= returns  # sensitive signals and gates
