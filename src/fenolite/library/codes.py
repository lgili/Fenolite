# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes of a library made from a board (capability design-conversion, "Library made from a board";
``docs/cli-contract.md``, "library"; change c0223)."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "library.drift": "error",
        "library.instances-differ": "warning",
        "library.not-local": "warning",
    }
)
"""Every code that ``fenolite.library`` and ``fenolite library`` report, with its severity."""


def issue(code: str, message: str, *, where: str = "", hint: str = "") -> Issue:
    """An ``Issue`` of a code of the table, with its severity; ``ValueError`` for another code."""
    severity = ISSUE_CODES.get(code)
    if severity is None:
        raise ValueError(f"{code!r} is not a library issue code")
    return Issue(code, severity, message, where=where, hint=hint)


__all__ = ["ISSUE_CODES", "issue"]
