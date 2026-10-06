# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes of a design comparison (capability design-equivalence, "Differences are located").

A difference of kind ``net`` carries the code of the assignment comparison,
``netlist.assignment-differs`` (``checks.codes``); every other kind carries ``equiv.<kind>``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from types import MappingProxyType

from fenolite.checks import codes as check_codes
from fenolite.checks.equivalence.model import KINDS, NOTICE_SEVERITY, Difference, EquivalenceReport
from fenolite.core.errors import Issue, Severity

NET_CODE = "netlist.assignment-differs"
EQUIVALENCE_CODES: Mapping[str, tuple[Severity, ...]] = MappingProxyType(
    {
        **{f"equiv.{kind}": (NOTICE_SEVERITY.get(kind, "error"),) for _, kind, _ in KINDS if kind != "net"},
        "equiv.excluded": ("info",),
        "equiv.import-message": ("info",),
        "equiv.no-exclusion-profile": ("warning",),
        "equiv.oracle-failed": ("error",),
    }
)
"""Every ``equiv.*`` code with its severities. ``equiv.rotation`` is the rotation of a footprint; a pad's
is ``equiv.pad-rotation``."""
ISSUE_CODES = EQUIVALENCE_CODES
"""The same table under the name that ``fenolite explain`` finds issue-code tables by."""


def issue(code: str, message: str, *, where: str = "", hint: str = "") -> Issue:
    """An ``Issue`` of a code of ``EQUIVALENCE_CODES``, with its only severity."""
    return Issue(code, EQUIVALENCE_CODES[code][0], message, where=where, hint=hint)


def _shown(value: str) -> str:
    return repr(value) if value else "nothing"


def _message(difference: Difference) -> str:
    return (
        f"{difference.where}: {difference.field} is {_shown(difference.a)} on side a "
        f"and {_shown(difference.b)} on side b (level {difference.level}, {difference.kind})"
    )


def difference_issues(report: EquivalenceReport) -> tuple[Issue, ...]:
    """One error per difference that no rule excludes, in level order, then one warning or info per notice
    that no rule excludes, then one ``equiv.excluded`` info per rule that matched, with its count and
    reason."""
    found: list[Issue] = []
    for difference in report.differences:
        if difference.kind == "net":
            found.append(
                check_codes.issue(
                    NET_CODE,
                    f"{difference.where} is on {difference.a} on side a and on {difference.b} on side b",
                    where=difference.where,
                )
            )
        else:
            found.append(issue(f"equiv.{difference.kind}", _message(difference), where=difference.where))
    for notice in report.notices:
        found.append(issue(f"equiv.{notice.kind}", _message(notice), where=notice.where))
    counts = Counter(excluded.rule_id for excluded in report.excluded)
    reasons = {excluded.rule_id: excluded.reason for excluded in report.excluded}
    for rule_id, count in sorted(counts.items()):
        reason = f": {reasons[rule_id]}" if reasons[rule_id] else ""
        found.append(issue("equiv.excluded", f"rule {rule_id} excludes {count} difference(s){reason}"))
    return tuple(found)


__all__ = ["EQUIVALENCE_CODES", "ISSUE_CODES", "NET_CODE", "difference_issues", "issue"]
