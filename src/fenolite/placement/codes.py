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
        "place.constraint": "error",
        "place.incomplete": "warning",
        "place.objective": "warning",
        "place.region-unassigned": "warning",
        "place.region-barrier": "warning",
        "place.region-crossing": "warning",
        "place.group-failed": "error",
        "place.fill-stale": "info",
    }
)
"""Every code that ``placement``, ``backends.kicad.replace`` and the ``place`` command emit."""
EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-PLACE-MOVE", "H-K-PLACE-TOUCH"))
"""``KICAD-VERIFIED`` while both rows are ``KICAD-VERIFIED`` on both majors, else ``INFERRED``. A placement
is never a verdict: KiCad's DRC judges the board."""


LAYOUT_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "layout.relative-cycle": "error",
        "layout.relative-unresolved": "warning",
        "layout.strategy-overflow": "warning",
        "layout.block-moved": "info",
    }
)
"""The codes of placement in code (change c0255, capability placement-in-code): the resolution of relative
requests and block poses, the layout strategies and the rigid move of a laid-out block. The build reports
them (``docs/cli-contract.md``, "Placement in code")."""
RELATIVE_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-REL-RESOLVE",))
"""A resolved position satisfies its request exactly, measured on the written board by the same box
function; no tool runs."""


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    """An issue of ``code`` with the severity of ``ISSUE_CODES``."""
    return Issue(code, ISSUE_CODES[code], message, where=where, hint=hint)


def layout_issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    """An issue of ``code`` with the severity of ``LAYOUT_ISSUE_CODES``."""
    return Issue(code, LAYOUT_ISSUE_CODES[code], message, where=where, hint=hint)


__all__ = ["EVIDENCE", "ISSUE_CODES", "LAYOUT_ISSUE_CODES", "RELATIVE_EVIDENCE", "issue", "layout_issue"]
