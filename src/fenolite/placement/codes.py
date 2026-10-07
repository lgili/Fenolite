# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes and the evidence of ``placement`` and of ``fenolite place`` (capability placement,
"Placement issue codes" and "Placement evidence"; ``docs/placement.md``)."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "place.courtyard-overlap": "error",
        "place.outside-outline": "error",
        "place.no-definition": "error",
        "place.locked": "error",
        "place.unknown-ref": "error",
        "place.keepout": "error",
        "place.edge-clearance": "warning",
        "place.no-room": "warning",
        "place.copper-left": "warning",
        "place.script-locked": "warning",
        "place.keepout-no-courtyard": "warning",
        "place.no-extent": "info",
        "place.no-outline": "info",
    }
)
"""Every code that ``placement``, ``backends.kicad.replace`` and the ``place`` command emit."""
EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-PLACE-MOVE", "H-K-PLACE-TOUCH"))
"""``KICAD-VERIFIED`` while both rows are ``KICAD-VERIFIED`` on both majors, else ``INFERRED``. A placement
is never a verdict: KiCad's DRC judges the board."""


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    """An issue of ``code`` with the severity of ``ISSUE_CODES``."""
    return Issue(code, ISSUE_CODES[code], message, where=where, hint=hint)


__all__ = ["EVIDENCE", "ISSUE_CODES", "issue"]
