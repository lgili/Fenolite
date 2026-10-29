# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper tidy: prune dangling copper, straighten runs, chamfer right-angle joints, T-joints and zone
corners, each edit kept only when its net keeps its connected groups and the copper check finds nothing
new; and the style report (capability copper-tidy; ``docs/copper.md``, "Copper tidy"; command
``fenolite tidy``).

The package imports ``model``, ``geometry`` and ``backends.base`` only: the pads come as board-frame
records and the copper check as a function (``edits.Check``), both passed by the caller."""

from __future__ import annotations

from fenolite.tidy.chamfer import (
    Corner,
    Joint,
    Tee,
    apply_corners,
    chamfer,
    cut_zones,
    find_corners,
    find_joints,
)
from fenolite.tidy.codes import ISSUE_CODES
from fenolite.tidy.edits import Check, Clash, Edit, TidyResult, fresh_clashes
from fenolite.tidy.prune import prune
from fenolite.tidy.straighten import Run, find_runs, straighten
from fenolite.tidy.style import StyleReport, StyleRow, style

STEPS = ("prune", "straighten", "chamfer")
"""The steps of ``fenolite tidy``, in the order they run."""

__all__ = [
    "ISSUE_CODES",
    "STEPS",
    "Check",
    "Clash",
    "Corner",
    "Edit",
    "Joint",
    "Run",
    "StyleReport",
    "StyleRow",
    "Tee",
    "TidyResult",
    "apply_corners",
    "chamfer",
    "cut_zones",
    "find_corners",
    "find_joints",
    "find_runs",
    "fresh_clashes",
    "prune",
    "straighten",
    "style",
]
