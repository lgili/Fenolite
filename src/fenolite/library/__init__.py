# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint libraries made from a board, and their drift (capability design-conversion, "Library made from
a board"; change c0223). ``fenolite library`` is the command."""

from __future__ import annotations

from fenolite.library.codes import ISSUE_CODES, issue
from fenolite.library.derive import (
    EVIDENCE,
    KINDS,
    MISSING,
    Derived,
    Footprint,
    derive_from_model,
    derive_library,
    differences,
    drift,
    drift_issues,
    nickname_of,
)

__all__ = [
    "EVIDENCE",
    "ISSUE_CODES",
    "KINDS",
    "MISSING",
    "Derived",
    "Footprint",
    "derive_from_model",
    "derive_library",
    "differences",
    "drift",
    "drift_issues",
    "issue",
    "nickname_of",
]
