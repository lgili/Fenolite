# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Stable issue codes emitted by routing plugins and commands, mapped to their severity. The ``route.role-*``
codes are those of the role mode (change c0244; ``docs/routing.md``, "Role mode"), the ``route.proposal-*``
codes those of the proposal mode (change c0280; ``docs/routing.md``, "Proposals")."""

from fenolite.core.errors import Severity

ISSUE_CODES: dict[str, Severity] = {
    "route.bad-item": "error",
    "route.budget-exhausted": "warning",
    "route.check-refused": "warning",
    "route.constraint-not-sent": "warning",
    "route.copper-removed": "warning",
    "route.escape-skipped": "warning",
    "route.fill-stale": "info",
    "route.incomplete": "error",
    "route.net-declared": "info",
    "route.no-layer": "warning",
    "route.optimizer-cut": "info",
    "route.option-ignored": "warning",
    "route.pair-not-routed": "warning",
    "route.pair-skipped": "warning",
    "route.pair-uncoupled": "info",
    "route.partial": "info",
    "route.plane-net": "info",
    "route.project-unread": "warning",
    "route.proposal-conflict": "error",
    "route.proposal-findings": "warning",
    "route.proposal-limit": "info",
    "route.proposal-none": "info",
    "route.proposal-open": "warning",
    "route.proposal-rejected": "info",
    "route.proposal-stale": "warning",
    "route.proposal-unknown": "error",
    "route.resumed": "info",
    "route.role-kept": "info",
    "route.role-none": "info",
    "route.role-placement": "info",
    "route.role-refused": "warning",
    "route.role-unconfirmed": "info",
    "route.role-unrouted": "warning",
    "route.tool-failed": "error",
    "route.tool-missing": "error",
    "route.tool-unpinned": "warning",
    "route.unrouted": "warning",
    "route.width-below-job": "warning",
    "route.zone-net-skipped": "info",
}

__all__ = ["ISSUE_CODES"]
