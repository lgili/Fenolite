# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Issue codes of the KiCad project file (``docs/formats/kicad/project.md``, "Issue codes").

A leaf module, so that ``lowering`` (net classes) and ``pro`` (project files) share one closed table.
"""

# evidence: none, issue codes of the project file

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kicad.project.below-floor": "warning",
        "kicad.project.pattern-unsafe": "error",
        "kicad.project.dropped-pattern": "warning",
        "kicad.project.too-new-key": "error",
        "kicad.project.dropped-too-new": "warning",
        "kicad.project.multiple-classes": "warning",
        "kicad.project.unknown-class": "warning",
        "kicad.project.pattern-conflict": "warning",
        "kicad.project.inexact-value": "info",
        "kicad.project.unlowered-field": "info",
        "kicad.project.unread-entry": "info",
        "kicad.project.reserved-variable": "error",
        "kicad.project.dropped-variable": "warning",
        "kicad.project.unread-variable": "info",
        "kicad.project.minimum-replaced": "info",
        "kicad.project.minimum-kept": "info",
        "kicad.project.rule-below-minimum": "warning",
        "kicad.project.class-shadowed": "warning",
        "kicad.project.default-over-rule": "warning",
        "kicad.project.unknown-check": "error",
        "kicad.project.dropped-check": "warning",
        "kicad.project.profile-reassigned": "warning",
    }
)


def project_issue(code: str, message: str, *, where: str = "", hint: str = "") -> Issue:
    """An issue of the project table, with the severity the table gives."""
    return Issue(code, ISSUE_CODES[code], message, where=where, hint=hint)


__all__ = ["ISSUE_CODES", "project_issue"]
