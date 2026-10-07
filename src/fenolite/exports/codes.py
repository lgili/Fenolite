# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes of ``fenolite export`` and ``fenolite render`` (capability manufacturing-exports,
"Export kinds and their arguments"), of ``fenolite bom`` and ``fenolite pnp`` (capability
assembly-outputs, "Assembly issue codes and evidence"), and of the manifest (capability
manufacturing-exports, "Project manifest")."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity

ISSUE_CODES: Mapping[str, Severity | tuple[Severity, ...]] = MappingProxyType(
    {
        "export.failed": "error",
        "export.kind-unavailable": "error",
        "render.failed": "warning",
        "export.sheet-missing": "error",
        "export.model-unread": "warning",
        "export.page-too-small": "warning",
        "assembly.template-invalid": "error",
        "bom.property-missing": "info",
        "bom.field-unsupported": "error",
        "pnp.no-outline": "error",
        "manifest.unreadable": "error",
        "manifest.missing": ("warning", "error"),
        "manifest.changed": ("warning", "error"),
        "manifest.stale": "warning",
        "manifest.unlisted": "info",
    }
)
"""Code → severity. A code with two severities is a warning when ``fenolite manifest`` writes (the file is
left out, or listed as it is now) and an error under ``--verify`` (the folder is not what was listed)."""


def issue(
    code: str,
    message: str,
    *,
    where: str = "",
    hint: str = "",
    retryable: bool = False,
    severity: Severity | None = None,
) -> Issue:
    """An ``Issue`` of a code of the table, with its severity: the first of the table, or ``severity``
    when the table allows it."""
    allowed = ISSUE_CODES[code]
    choices = (allowed,) if isinstance(allowed, str) else allowed
    if severity is not None and severity not in choices:
        raise ValueError(f"{code} is never {severity}")
    return Issue(code, severity or choices[0], message, where=where, hint=hint, retryable=retryable)


__all__ = ["ISSUE_CODES", "issue"]
