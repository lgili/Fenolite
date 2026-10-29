# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``package.*`` findings of the footprint generators (change c0260, design decision 18).

An unreadable record is not a finding: the reader raises ``FormatError`` (``FEN-3004``)."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "package.dimensions-inconsistent": "error",
        "package.land-impossible": "error",
        "package.land-override": "info",
        "package.missing-bound": "error",
        "package.name-mismatch": "error",
        "package.no-goals": "error",
        "package.pads-clipped": "warning",
        "package.pin-count": "error",
    }
)
"""Every code that ``fenolite.catalog.footprints`` reports, with its severity."""


def issue(code: str, message: str, *, where: str = "", hint: str = "") -> Issue:
    """An ``Issue`` of a code of the table, with its severity; ``ValueError`` for another code."""
    severity = ISSUE_CODES.get(code)
    if severity is None:
        raise ValueError(f"{code!r} is not a package issue code")
    return Issue(code, severity, message, where=where, hint=hint)


_ORDER = {"error": 0, "warning": 1, "info": 2}


def sort_issues(issues: list[Issue]) -> tuple[Issue, ...]:
    """Findings by severity (errors first), then code, place and message: a fixed order."""
    return tuple(sorted(issues, key=lambda i: (_ORDER[i.severity], i.code, i.where, i.message)))


__all__ = ["ISSUE_CODES", "issue", "sort_issues"]
