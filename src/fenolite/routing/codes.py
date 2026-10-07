# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Stable issue codes emitted by routing plugins and commands, mapped to their severity."""

from fenolite.core.errors import Severity

ISSUE_CODES: dict[str, Severity] = {
    "route.bad-item": "error",
    "route.budget-exhausted": "warning",
    "route.constraint-not-sent": "warning",
    "route.copper-removed": "warning",
    "route.fill-stale": "info",
    "route.incomplete": "error",
    "route.net-declared": "info",
    "route.no-layer": "warning",
    "route.optimizer-cut": "info",
    "route.option-ignored": "warning",
    "route.partial": "info",
    "route.plane-net": "info",
    "route.project-unread": "warning",
    "route.resumed": "info",
    "route.tool-failed": "error",
    "route.tool-missing": "error",
    "route.tool-unpinned": "warning",
    "route.unrouted": "warning",
    "route.zone-net-skipped": "info",
}

__all__ = ["ISSUE_CODES"]
