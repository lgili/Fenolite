# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The role measures come from the analyses (change c0222; capability net-roles, "Role measures come from
the analyses": "Measures name their analysis", "A missing input is the analysis's warning")."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

from _roleboards import Built, judge

from fenolite.roles.measure import ANALYSES, Inputs

ROLES = Path(__file__).resolve().parents[3] / "src" / "fenolite" / "roles"
STATES = {"saved_fill", "simulated", "outline", "tracks"}
CURRENTS = {"VOUT": 2000, "VL": 2000, "SW": 2000, "VIN": 1000}


def test_sources(reference: Callable[..., Built]) -> None:
    judged = judge(reference("buck_shunt", "bad"), currents=CURRENTS)
    kinds = {measure.kind for measure in judged.measured.measures}
    assert {"loop", "path", "attachment", "gate_return", "near"} <= kinds
    for measure in judged.measured.measures:
        assert measure.analysis in ANALYSES, measure
        assert measure.copper and set(measure.copper) <= STATES, measure
        assert measure.to_json()["analysis"] == measure.analysis
    assert judged.measured.analyses <= set(ANALYSES)


def test_no_measure_function_of_its_own() -> None:
    """``src/fenolite/roles/`` defines no loop area, section, capacity or gap function: those are the
    analyses'."""
    for path in sorted(ROLES.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                assert not any(word in node.name for word in ("area", "section", "capacity", "gap")), (
                    path.name,
                    node.name,
                )


def test_derived_inputs(reference: Callable[..., Built]) -> None:
    judged = judge(reference("buck_shunt", "good"), currents=CURRENTS)
    loops = {m.subject: m for m in judged.measured.measures if m.kind == "loop"}
    assert set(loops) == {"hot_SW", "gate_Q1", "gate_Q2", "kelvin_R12"}
    assert loops["hot_SW"].values["pads"] == ["C1-1", "Q1-3", "Q1-1", "Q2-3", "Q2-1", "C1-2"]
    assert loops["hot_SW"].analysis == "loop_areas" and loops["hot_SW"].copper == ("saved_fill",)
    paths = [m for m in judged.measured.measures if m.kind == "path"]
    assert {m.subject for m in paths} == {"VOUT", "VL", "SW", "VIN"}
    assert {m.values["path_source"] for m in paths} == {"derived"}
    (vout,) = {tuple(map(tuple, m.values["path"])) for m in paths if m.subject == "VOUT"}
    assert vout == (("J2-1",), ("R12-2",))


def test_a_missing_input_is_the_analysis_warning(reference: Callable[..., Built]) -> None:
    built = reference("buck_shunt", "bad")
    assert "stackup" not in built.board.read_text(encoding="utf-8")
    judged = judge(built, currents={"VOUT": 2000}, inputs=Inputs(temp_rise_mk=10_000))
    missing = [found for found in judged.issues if found.code == "analysis.input-missing"]
    assert missing and {found.where for found in missing} == {"copper thickness"}
    assert not [found for found in judged.issues if found.code == "roles.input-missing"]


def test_the_rule_of_thumb_needs_no_fit_input(reference: Callable[..., Built]) -> None:
    judged = judge(reference("buck_shunt", "bad"), currents={"VOUT": 2000})
    assert not [found for found in judged.issues if found.code == "analysis.input-missing"]
    assert not [found for found in judged.issues if found.code.startswith("analysis.path-")]
