# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes of ``fenolite export`` and ``fenolite render`` (capability manufacturing-exports,
"Export kinds and their arguments")."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "export.failed": "error",
        "export.kind-unavailable": "error",
        "render.failed": "warning",
    }
)


def issue(code: str, message: str, *, where: str = "", hint: str = "", retryable: bool = False) -> Issue:
    """An ``Issue`` of a code of the table, with its severity."""
    return Issue(code, ISSUE_CODES[code], message, where=where, hint=hint, retryable=retryable)


__all__ = ["ISSUE_CODES", "issue"]
