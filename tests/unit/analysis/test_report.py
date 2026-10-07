# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The analysis package as a whole: purity, no float, evidence (capability board-analyses, "Analysis
package and report" and "Analysis evidence"; change c0047)."""

from __future__ import annotations

import ast
import builtins
import subprocess
from pathlib import Path

import pytest
from _analysis import discs

import fenolite.analysis as analysis
from fenolite.analysis import analyze_current, analyze_distances
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.evidence import Level
from fenolite.model.findings import Findings

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
PACKAGE = ROOT / "src" / "fenolite" / "analysis"


def test_pure_and_repeatable(monkeypatch: pytest.MonkeyPatch) -> None:
    design = read_board(BOARD)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("an analysis opened a file or started a process")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(builtins, "open", refuse)
    first = analyze_current(design, temp_rise_mk=10_000, copper_thickness={"*": 35_000})
    second = analyze_current(design, temp_rise_mk=10_000, copper_thickness={"*": 35_000})
    assert first == second and first.rows
    assert analyze_distances(design, pads=None, boundary=None, within=500_000) == analyze_distances(
        design, pads=None, boundary=None, within=500_000
    )


def test_no_float_in_the_source() -> None:
    problems: list[str] = []
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                problems.append(f"{path.name}:{node.lineno}: float literal")
            if isinstance(node, ast.Name) and node.id == "float":
                problems.append(f"{path.name}:{node.lineno}: names float")
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "math"
                and node.attr in ("sqrt", "pow")
            ):
                problems.append(f"{path.name}:{node.lineno}: math.{node.attr}")
            if isinstance(node, ast.ImportFrom) and node.module == "math":
                for alias in node.names:
                    if alias.name in ("sqrt", "pow"):
                        problems.append(f"{path.name}:{node.lineno}: imports math.{alias.name}")
    assert not problems, "\n".join(problems)


def test_evidence_constant() -> None:
    assert analysis.EVIDENCE.level is Level.INFERRED
    ids = ("H-G-AN-EDGE", "H-G-AN-FIT", "H-G-AN-GAP", "H-G-AN-PATH", "H-G-AN-VIA")
    assert analysis.EVIDENCE.hypotheses == ids
    register = (ROOT / "docs" / "hypotheses.md").read_text(encoding="utf-8")
    for ident in ids:
        assert f"| {ident} |" in register, ident


def test_measured_report_keeps_the_level_and_gives_findings() -> None:
    report = analyze_distances(discs().build(), pads=None, boundary=None, pairs=(("A", "B"),))
    assert report.evidence.level is Level.INFERRED and report.issues == ()
    assert report.findings() == Findings(issues=())


def test_missing_pads_lower_the_level() -> None:
    made = discs()
    made.pad("R1", "1", "A")
    report = analyze_distances(made.build(), pads=None, boundary=None, within=1_000_000)
    (found,) = [issue for issue in report.issues if issue.code == "analysis.item-unsupported"]
    assert "pad" in found.message and found.where == "pad"
    assert report.evidence.level is Level.UNVERIFIED


def test_power_evidence_constants() -> None:
    """Scenario "Evidence constants" (change c0115)."""
    from fenolite.analysis import grooves, insulation, power, surface

    constants = {
        "power": (power.EVIDENCE, ("H-G-AN-NECKFIT", "H-G-AN-NETWORK", "H-G-AN-POUR", "H-G-AN-SECTION")),
        "insulation": (insulation.EVIDENCE, ("H-G-AN-INSUL",)),
        "grooves": (grooves.EVIDENCE, ("H-G-AN-GROOVE",)),
        "bridges": (surface.BRIDGE_EVIDENCE, ("H-G-AN-OVER",)),
    }
    register = (ROOT / "docs" / "hypotheses.md").read_text(encoding="utf-8")
    for name, (evidence, ids) in constants.items():
        assert evidence.level is Level.INFERRED and evidence.hypotheses == ids, name
        for ident in ids:
            assert f"| {ident} |" in register, ident
    assert analysis.EVIDENCE.hypotheses == (
        "H-G-AN-EDGE",
        "H-G-AN-FIT",
        "H-G-AN-GAP",
        "H-G-AN-PATH",
        "H-G-AN-VIA",
    )
    assert (
        power.PowerReport().evidence.level is Level.INFERRED and power.PowerReport().findings().issues == ()
    )
