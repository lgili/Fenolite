# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""ERC violations as located issues (capability verification-loop, "ERC findings as issues").

Every violation of an ERC report becomes one issue. Its code names the tool's check
(``<oracle>.erc.<type>``), its severity follows the report, and its location is the one the oracle found
for each item (``REF-PIN`` for a pin, ``REF`` for a symbol, the text of a label), or the sheet and the
position of the item when the oracle found none. A location is never guessed here: ``checks`` reads no
schematic and names no backend.
"""

from __future__ import annotations

from fenolite.backends.base import ErcItem, ErcReport, ErcViolation
from fenolite.checks.codes import erc_code, issue, type_suffix
from fenolite.checks.drc_json import format_position, sanitise
from fenolite.core.errors import Issue, Severity

RESERVED_SUFFIXES = ("position-unscaled",)
"""Suffixes that a reader of ERC reports uses for a code of its own; an ERC type that would give one of
them becomes ``type-<suffix>``."""


def type_code(oracle: str, type: str) -> str:  # noqa: A002 (the report's own key)
    """``<oracle>.erc.<suffix>``, the suffix by ``checks.codes.type_suffix``."""
    suffix = type_suffix(type)
    if suffix in RESERVED_SUFFIXES:
        suffix = f"type-{suffix}"
    return erc_code(oracle, suffix)


def issue_severity(violation: ErcViolation) -> Severity:
    """``info`` for an excluded entry; the report's ``error`` or ``warning``; ``error`` for anything else."""
    if violation.excluded:
        return "info"
    return "warning" if violation.severity == "warning" else "error"


def item_where(violation: ErcViolation, item: ErcItem) -> str:
    """The location the oracle found, or ``<sheet>@<x>,<y>``: the sheet path and the item's position in
    millimetres as exact decimals without trailing zeros."""
    return item.where or f"{violation.sheet}{format_position(item.position)}"


def finding_types(report: ErcReport, *, oracle: str) -> dict[str, str]:
    """Each emitted code mapped to the tool's raw type, sorted by code."""
    return dict(sorted({type_code(oracle, v.type): v.type for v in report.violations}.items()))


def finding_issues(report: ErcReport, *, oracle: str) -> tuple[Issue, ...]:
    """One issue per violation of ``report``, in report order."""
    issues: list[Issue] = []
    for violation in report.violations:
        where = ", ".join(item_where(violation, item) for item in violation.items)
        message = sanitise(f"{violation.type}: {violation.description}", source=report.source)
        issues.append(
            issue(type_code(oracle, violation.type), message, severity=issue_severity(violation), where=where)
        )
    return tuple(issues)


__all__ = [
    "RESERVED_SUFFIXES",
    "finding_issues",
    "finding_types",
    "issue_severity",
    "item_where",
    "type_code",
]
