# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes that ``checks`` emits (capability verification-loop, "Check issue codes").

``model.*`` findings and reader codes (``kicad.board.*``, ``kicad.version.*``) pass through unchanged and
are not in this table. Codes of an oracle start with its name, written ``<oracle>`` here.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity

ORACLE = "<oracle>"
ISSUE_CODES: Mapping[str, tuple[Severity, ...]] = MappingProxyType(
    {
        "check.read-refused": ("error",),
        "check.cache-unreadable": ("warning",),
        "check.footprint-unresolved": ("error",),
        "check.symbol-unresolved": ("error",),
        "check.rt1-failed": ("error",),
        "check.oracle-failed": ("error",),
        "check.copy-skipped": ("info",),
        f"{ORACLE}.drc.rules-not-loaded": ("error", "info"),
        f"{ORACLE}.drc.rules-unchecked": ("warning",),
        "erc.lite.output-conflict": ("warning",),
        "erc.lite.power-undriven": ("warning",),
        "erc.lite.floating-pin": ("warning",),
    }
)


def oracle_code(oracle: str, suffix: str) -> str:
    """The code ``<oracle name>.drc.<suffix>``, for example ``kicad.drc.rules-not-loaded``."""
    return f"{oracle}.drc.{suffix}"


def table_key(code: str) -> str:
    """The ``ISSUE_CODES`` key of ``code``: an oracle's ``.drc.`` codes with ``<oracle>`` for its name."""
    head, sep, rest = code.partition(".drc.")
    return f"{ORACLE}.drc.{rest}" if sep and "." not in head else code


def issue(
    code: str,
    message: str,
    *,
    severity: Severity | None = None,
    where: str = "",
    hint: str = "",
    retryable: bool = False,
) -> Issue:
    """An ``Issue`` of a code of the table, with its only severity unless one of its severities is given."""
    allowed = ISSUE_CODES.get(table_key(code))
    if allowed is None:
        raise KeyError(f"{code!r} is not a check issue code")
    chosen = severity if severity is not None else allowed[0]
    if chosen not in allowed:
        raise ValueError(f"{code!r} has no severity {chosen!r}")
    return Issue(code, chosen, message, where=where, hint=hint, retryable=retryable)


__all__ = ["ISSUE_CODES", "ORACLE", "issue", "oracle_code", "table_key"]
