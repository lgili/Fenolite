# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes and the evidence of layout reuse (capability layout-reuse; ``docs/cli-contract.md``,
"reuse")."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "reuse.no-fit": "error",
        "reuse.unknown-part": "error",
        "reuse.check-failed": "error",
        "reuse.drc-new": "error",
        "reuse.mirror-suspected": "warning",
        "reuse.project-unread": "warning",
        "reuse.copper-dropped": "info",
        "reuse.fill-stale": "info",
    }
)
"""Every code that ``fenolite.reuse`` and ``fenolite place --strategy reuse`` report, with its severity."""

HYPOTHESIS = "H-G-REUSE-FIT"
"""The register row that a rigid fit over the pads with unique numbers places a copied part so that its
pads land on the reference pads, on either side and from a reference drawn with the Y axis up."""
EVIDENCE = Evidence(Level.INFERRED, hypotheses=(HYPOTHESIS,))
"""The evidence of a fit: the pads of the written board are measured against the fit, no tool runs."""
ZONE_HYPOTHESIS = "H-G-REUSE-ZONE"
"""The register row that a zone of the block copied with its fill (change c0227) joins the images of its
pads."""
ZONE_EVIDENCE = Evidence(Level.INFERRED, hypotheses=(ZONE_HYPOTHESIS,))
"""The evidence of a copied zone: its pads are checked on the board's copper groups, no filler runs."""


def issue(code: str, message: str, *, where: str = "", hint: str = "") -> Issue:
    """An ``Issue`` of a code of the table, with its severity; ``ValueError`` for another code."""
    severity = ISSUE_CODES.get(code)
    if severity is None:
        raise ValueError(f"{code!r} is not a reuse issue code")
    return Issue(code, severity, message, where=where, hint=hint)


__all__ = ["EVIDENCE", "HYPOTHESIS", "ISSUE_CODES", "ZONE_EVIDENCE", "ZONE_HYPOTHESIS", "issue"]
