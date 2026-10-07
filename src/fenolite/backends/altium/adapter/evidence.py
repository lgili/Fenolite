# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The evidence of an import, re-exported from ``fenolite.backends.altium.import_evidence`` (the backend
names it there without loading the adapter)."""

# evidence: see import_evidence

from __future__ import annotations

from fenolite.backends.altium.import_evidence import (
    EVIDENCE,
    HYPOTHESES,
    LEVELS,
    MAPPING_HYPOTHESES,
    READER_LEVELS,
)

__all__ = ["EVIDENCE", "HYPOTHESES", "LEVELS", "MAPPING_HYPOTHESES", "READER_LEVELS"]
