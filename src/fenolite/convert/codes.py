# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes of a conversion (capability design-conversion; change c0159)."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity

ISSUE_CODES: Mapping[str, tuple[Severity, ...]] = MappingProxyType(
    {
        "convert.changed": ("info",),
        "convert.lossy": ("warning",),
        "convert.no-verify": ("warning",),
        "convert.schematic-unverified": ("warning",),
        "convert.unexplained": ("error",),
    }
)
"""Every ``convert.*`` code with its only severity: ``convert.lossy`` per ``refuse`` kind with losses
under ``allow_lossy``, ``convert.changed`` per kind with changes, ``convert.no-verify`` for a conversion
that was not read back, ``convert.schematic-unverified`` for a written schematic that could not be compared
with the source's (a KiCad downgrade whose sheets need ``kicad-cli`` for their netlist and found none), and
``convert.unexplained`` per difference of the read-back that no loss and no
rule explains."""


def issue(code: str, message: str, *, where: str = "", hint: str = "") -> Issue:
    """An ``Issue`` of a code of ``ISSUE_CODES``, with its only severity."""
    return Issue(code, ISSUE_CODES[code][0], message, where=where, hint=hint)


__all__ = ["ISSUE_CODES", "issue"]
