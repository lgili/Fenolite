# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes of copper tidy (capability copper-tidy; ``docs/cli-contract.md``, "tidy")."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "tidy.check-failed": "error",
        "tidy.drc-new": "error",
        "tidy.acute": "warning",
        "tidy.net-skipped": "warning",
        "tidy.project-unread": "warning",
        "tidy.chamfer-undone": "info",
        "tidy.fill-stale": "info",
        "tidy.kept": "info",
        "tidy.straighten-skipped": "info",
    }
)
"""Every code that ``fenolite.tidy`` and ``fenolite tidy`` report, with its severity."""


def issue(code: str, message: str, *, where: str = "", hint: str = "") -> Issue:
    """An ``Issue`` of a code of the table, with its severity; ``ValueError`` for another code."""
    severity = ISSUE_CODES.get(code)
    if severity is None:
        raise ValueError(f"{code!r} is not a tidy issue code")
    return Issue(code, severity, message, where=where, hint=hint)


__all__ = ["ISSUE_CODES", "issue"]
