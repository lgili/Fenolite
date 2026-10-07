# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Analyses of a board on the neutral model: current capacity, clearance and creepage (capability
board-analyses; user guide ``docs/analyses.md``). Fenolite measures; the user decides."""

from fenolite.analysis.boundary import board_boundary
from fenolite.analysis.current import analyze_current
from fenolite.analysis.distance import analyze_distances
from fenolite.analysis.power import PowerReport, analyze_power
from fenolite.analysis.report import EVIDENCE, AnalysisReport
from fenolite.analysis.requirements import load_requirements

__all__ = [
    "EVIDENCE",
    "AnalysisReport",
    "PowerReport",
    "analyze_current",
    "analyze_distances",
    "analyze_power",
    "board_boundary",
    "load_requirements",
]
