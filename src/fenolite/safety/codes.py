# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes of file safety (capability file-safety; ``docs/cli-contract.md``, "snapshot", "publish",
"refs" and "Open sessions")."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Severity

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "safety.unstable": "error",
        "safety.changed-since-receipt": "error",
        "safety.skipped": "warning",
        "safety.open-session": "warning",
        "safety.placeholder": "warning",
        "refs.outside": "warning",
        "refs.missing": "warning",
        "refs.not-writable": "warning",
        "refs.unresolved": "info",
    }
)

__all__ = ["ISSUE_CODES"]
