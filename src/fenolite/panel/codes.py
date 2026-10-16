# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes of panels (capability board-panels, "Panel checks"; capability cli-contract, "Panel
command"; change c0173, design Decision 6): the checks of ``panel.checks``, the structural errors of the
layout, and the notes of the Altium forms."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Severity

ISSUE_CODES: Mapping[str, Severity | tuple[Severity, ...]] = MappingProxyType(
    {
        "panel.vscore-copper": "error",
        "panel.vscore-shape": "error",
        "panel.vscore-spacing": ("error", "warning"),
        "panel.vscore-thickness": ("error", "warning", "info"),
        "panel.tab-copper": "error",
        "panel.gap": ("error", "warning"),
        "panel.tab-count": ("error", "warning"),
        "panel.tab-spacing": "warning",
        "panel.fiducial-place": "warning",
        "panel.tooling-place": "warning",
        "panel.size": "warning",
        "panel.board-outline": "error",
        "panel.no-fit": "error",
        "panel.net-collision": "error",
        "panel.source-unreachable": "error",
        "panel.altium-cutout": "error",
        "altium.panel-flattened": "info",
    }
)
"""Code → severity, or the severities it takes."""

__all__ = ["ISSUE_CODES"]
