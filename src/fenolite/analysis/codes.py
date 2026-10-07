# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed table of the issue codes of the analyses (capability board-analyses, "Findings and issue
codes"; ``docs/cli-contract.md``, "analyze"). ``checks.codes`` is the table of ``fenolite check`` and is
not extended."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity

ISSUE_CODES: Mapping[str, tuple[Severity, ...]] = MappingProxyType(
    {
        "analysis.current-exceeded": ("error",),
        "analysis.clearance-below": ("error",),
        "analysis.clearance-undecided": ("warning",),
        "analysis.creepage-below": ("error",),
        "analysis.creepage-undecided": ("warning",),
        "analysis.embedded-below": ("error",),
        "analysis.fit-out-of-range": ("warning",),
        "analysis.input-missing": ("warning",),
        "analysis.item-unsupported": ("warning",),
        "analysis.requirement-unmatched": ("warning",),
        # power paths, insulation and conductors on the path ("Power and insulation codes")
        "analysis.path-unmatched": ("warning",),
        "analysis.path-open": ("warning",),
        "analysis.path-exceeded": ("error",),
        "analysis.path-undecided": ("warning",),
        "analysis.drop-above": ("error",),
        "analysis.drop-undecided": ("warning",),
        "analysis.insulation-below": ("error",),
        "analysis.insulation-undecided": ("warning",),
        "analysis.creepage-over": ("info",),
    }
)


def issue(
    code: str, message: str, *, severity: Severity | None = None, where: str = "", hint: str = ""
) -> Issue:
    """An ``Issue`` of a code of the table, with its severity; ``ValueError`` for a code or a severity
    outside it."""
    allowed = ISSUE_CODES.get(code)
    if allowed is None:
        raise ValueError(f"{code!r} is not an analysis issue code")
    chosen = severity if severity is not None else allowed[0]
    if chosen not in allowed:
        raise ValueError(f"{code!r} has no severity {chosen!r}")
    return Issue(code, chosen, message, where=where, hint=hint)


__all__ = ["ISSUE_CODES", "issue"]
