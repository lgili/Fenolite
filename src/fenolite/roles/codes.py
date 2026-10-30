# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed table of the issue codes of the net roles (change c0222; capability net-roles, "Role issue
codes" and "Finding severities"; ``docs/roles.md``, "Codes").

The first severity of a code is its default. A finding against a default limit of the role profile is at
most a ``warning``; it is an ``error`` only when its limit is the user's and its role is ``confirmed`` or
``declared`` (``severity``). The topological findings (the Kelvin and gate-return attachments) are an
``error`` on a confirmed or declared group, since S-0850 and S-0852 state them as rules, not as numbers.
Every finding on an unconfirmed inferred role is at most a ``warning``. No ``FEN-`` code is added.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity

ISSUE_CODES: Mapping[str, tuple[Severity, ...]] = MappingProxyType(
    {
        "roles.loop-area": ("warning", "error"),
        "roles.loop-open": ("warning",),
        "roles.gate-loop": ("warning", "error"),
        "roles.gate-return-shared": ("warning", "error"),
        "roles.kelvin-outer": ("warning", "error"),
        "roles.kelvin-shared": ("warning", "error"),
        "roles.kelvin-apart": ("warning",),
        "roles.near-switching": ("warning",),
        "roles.width-current": ("warning", "error"),
        "roles.section-current": ("warning", "error"),
        "roles.via-current": ("warning", "error"),
        "roles.return-gap": ("warning",),
        "roles.limit-missing": ("warning",),
        "roles.current-missing": ("info",),
        "roles.ambiguous": ("warning",),
        "roles.unconfirmed": ("info",),
        "roles.declared-differs": ("info",),
        "roles.copper-skipped": ("info", "warning"),
        "roles.copper-blocked": ("warning",),
        "roles.copper-extra": ("warning",),
        "roles.copper-kept": ("info",),
        "roles.copper-worse": ("error",),
        "roles.copper-placement": ("warning",),
        "roles.copper-narrow": ("warning",),
        "roles.corridor-blocked": ("warning",),
    }
)
TOPOLOGICAL = frozenset({"roles.kelvin-outer", "roles.kelvin-shared", "roles.gate-return-shared"})
"""The codes of the attachment measures, which are rules of S-0850 and S-0852 rather than numbers."""
STATED = frozenset({"confirmed", "declared"})


def issue(
    code: str, message: str, *, severity: Severity | None = None, where: str = "", hint: str = ""
) -> Issue:
    """An ``Issue`` of a code of the table, with its severity; ``ValueError`` for a code or a severity
    outside it."""
    allowed = ISSUE_CODES.get(code)
    if allowed is None:
        raise ValueError(f"{code!r} is not a roles issue code")
    chosen = severity if severity is not None else allowed[0]
    if chosen not in allowed:
        raise ValueError(f"{code!r} has no severity {chosen!r}")
    return Issue(code, chosen, message, where=where, hint=hint)


def severity(code: str, *, source: str, limit_source: str) -> Severity:
    """The severity of a finding of ``code`` on a role or group of ``source`` (``inferred``, ``confirmed``,
    ``declared``) against a limit of ``limit_source`` (``profile``, ``override``, ``requirements``, or
    ``rule`` for a topological finding): ``error`` only for a stated role and a limit of the user, or for a
    topological finding on a stated group; else the code's first severity."""
    allowed = ISSUE_CODES[code]
    if "error" not in allowed or source not in STATED:
        return allowed[0]
    if code in TOPOLOGICAL or limit_source in ("override", "requirements"):
        return "error"
    return allowed[0]


__all__ = ["ISSUE_CODES", "STATED", "TOPOLOGICAL", "issue", "severity"]
