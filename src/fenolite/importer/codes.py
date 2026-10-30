# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes of ``fenolite import`` (change c0275, design decision 15; ``docs/import.md``)."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "import.item-unexpressed": "warning",
        "import.unequal": "error",
        "import.unverified": "warning",
        "import.schematic-generated": "info",
        "import.footprint-variant": "info",
        "import.symbol-regenerated": "info",
        "import.sheet-renamed": "info",
        "import.upgraded": "info",
        "import.provenance-missing": "warning",
        "import.timestamp-missing": "info",
        "import.teardrops-regenerated": "info",
    }
)
"""Every code that ``fenolite.importer`` and ``fenolite import`` report, with its severity."""


def issue(code: str, message: str, *, where: str = "", hint: str = "") -> Issue:
    """An ``Issue`` of a code of the table, with its severity; ``ValueError`` for another code."""
    severity = ISSUE_CODES.get(code)
    if severity is None:
        raise ValueError(f"{code!r} is not an import issue code")
    return Issue(code, severity, message, where=where, hint=hint)


__all__ = ["ISSUE_CODES", "issue"]
