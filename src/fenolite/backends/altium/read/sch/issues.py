# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed set of findings of the schematic reader and a collector that keeps them in stream order."""

# evidence: none, issue codes of the schematic reader and their collector

from __future__ import annotations

from dataclasses import dataclass, field

from fenolite.core.errors import Issue, Severity

ISSUE_CODES: dict[str, Severity] = {
    "altium.sch.malformed-record": "warning",
    "altium.sch.bad-value": "warning",
    "altium.sch.unknown-record": "info",
    "altium.sch.unknown-stream": "info",
    "altium.sch.empty-stream": "warning",
    "altium.sch.weight-mismatch": "warning",
    "altium.sch.orphan-record": "warning",
    "altium.sch.no-sheet": "warning",
    "altium.sch.part-out-of-range": "warning",
    "altium.sch.text-undecodable": "warning",
    "altium.sch.pin-trailing-bytes": "info",
    "altium.sch.storage-opaque": "info",
    "altium.schlib.unlisted-component": "info",
    "altium.schlib.missing-component": "warning",
    "altium.schlib.no-component": "warning",
    "altium.schlib.side-stream-opaque": "info",
    "altium.schlib.side-stream-orphan": "warning",
}
"""Every issue code the reader reports, with its severity (capability ``altium-schematic-reader``)."""


@dataclass
class IssueLog:
    """Findings of one reading, in the order they were found."""

    items: list[Issue] = field(default_factory=list[Issue])

    def add(self, code: str, message: str, where: str, hint: str = "") -> None:
        self.items.append(Issue(code, ISSUE_CODES[code], message, where, hint))


__all__ = ["ISSUE_CODES", "IssueLog"]
