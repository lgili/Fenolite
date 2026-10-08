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

DOCUMENTS_EVIDENCE = Evidence(
    Level.KICAD_VERIFIED,
    hypotheses=("H-K-EXPORT-DOCS", "H-K-EXPORT-DOCS-REPEAT", "H-K-EXPORT-MODELS", "H-K-EXPORT-SHEETS"),
)
"""The level of the six document kinds (IPC-2581, ODB++, STEP, board PDF and DXF, schematic PDF; change
c0116): ``KICAD-VERIFIED``, since the four hypotheses hold on 9.0.9 and 10.0.6 (c0116 task 9.2). As for
``EVIDENCE``, it covers the file set, the hashes and the source of each file, never the content of a
document."""

__all__ = ["DOCUMENTS_EVIDENCE", "EVIDENCE", "ISSUE_CODES"]
