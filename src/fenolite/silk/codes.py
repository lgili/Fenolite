# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes of silkscreen layout (capability silkscreen-layout; ``docs/cli-contract.md``, "silk")."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "silk.check-failed": "error",
        "silk.drc-new": "error",
        "silk.no-place": "warning",
        "silk.no-outline": "warning",
        "silk.cut-by-other": "warning",
        "silk.clip-skipped": "warning",
        "silk.estimated": "info",
        "silk.item-skipped": "info",
        "silk.footprint-changed": "info",
    }
)
"""Every code that ``fenolite.silk`` and ``fenolite silk`` report, with its severity."""


def issue(code: str, message: str, *, where: str = "", hint: str = "") -> Issue:
    """An ``Issue`` of a code of the table, with its severity; ``ValueError`` for another code."""
    severity = ISSUE_CODES.get(code)
    if severity is None:
        raise ValueError(f"{code!r} is not a silk issue code")
    return Issue(code, severity, message, where=where, hint=hint)


__all__ = ["ISSUE_CODES", "issue"]
