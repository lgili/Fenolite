# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fabrication files through ``kicad-cli`` and the manifest that describes them (capability
manufacturing-exports; user guide ``docs/exports.md``).

Fenolite writes no Gerber: every file is KiCad's, produced on a copy of the project. Fenolite claims the
set of files, their hashes and the board they came from.
"""

from __future__ import annotations

from fenolite.core.evidence import Evidence, Level
from fenolite.exports.codes import ISSUE_CODES

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-EXPORT-FILES", "H-K-EXPORT-REPEAT"))
"""``KICAD-VERIFIED``: both hypotheses hold on 9.0.9 and 10.0.6 (c0024 task 6.2). The level covers the
file set and the hashes, never the fabrication data."""

__all__ = ["EVIDENCE", "ISSUE_CODES"]
