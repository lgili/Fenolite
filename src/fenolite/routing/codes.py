# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Stable issue codes emitted by routing plugins and commands, mapped to their severity."""

from fenolite.core.errors import Severity

ISSUE_CODES: dict[str, Severity] = {
    "route.bad-item": "error",
    "route.copper-removed": "warning",
    "route.fill-stale": "info",
    "route.incomplete": "error",
    "route.option-ignored": "warning",
    "route.partial": "info",
    "route.tool-failed": "error",
    "route.tool-missing": "error",
    "route.tool-unpinned": "warning",
    "route.unrouted": "warning",
    "route.zone-net-skipped": "info",
}

__all__ = ["ISSUE_CODES"]
