# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Issue codes of the Altium import and the census of what it maps (capability altium-import, "Import
issue codes" and "Unmapped records are counted"; change c0043).

Every issue of the adapter carries a code of the closed table ``IMPORT_ISSUE_CODES``. The prefix
``altium.import.`` keeps the table apart from the build's codes (``altium.*``) and the readers'
(``altium.sch.*``, ``altium.schlib.*``, ``altium.pcb-read.*``, ``altium.project.*``, ``altium.rule.*``).
"""

# evidence: none, issue codes of the import and the counters of its census

from __future__ import annotations

from collections import Counter

from fenolite.core.errors import Issue, Severity

IMPORT_ISSUE_CODES: dict[str, Severity] = {
    "altium.import.bad-stack": "error",
    "altium.import.sheet-loop": "error",
    "altium.import.bad-length": "warning",
    "altium.import.bad-geometry": "warning",
    "altium.import.layer-outside-stack": "warning",
    "altium.import.duplicate-net": "warning",
    "altium.import.unknown-member": "warning",
    "altium.import.padstack-unknown": "warning",
    "altium.import.via-span": "warning",
    "altium.import.no-designator": "warning",
    "altium.import.sheet-missing": "warning",
    "altium.import.repeated-sheet": "warning",
    "altium.import.channels": "info",
    "altium.import.channel-naming": "warning",
    "altium.import.scope-unknown": "warning",
    "altium.import.duplicate-net-name": "warning",
    "altium.import.duplicate-sheet-name": "warning",
    "altium.import.bus-width": "warning",
    "altium.import.harness-nested": "warning",
    "altium.import.pcb-only-component": "warning",
    "altium.import.document-skipped": "warning",
    "altium.import.zone-hole-outside": "warning",
    "altium.import.inexact": "info",
    "altium.import.multi-class": "info",
    "altium.import.zone-arc": "info",
    "altium.import.copper-shape": "info",
    "altium.import.scope": "info",
    "altium.import.option-ignored": "info",
    "altium.import.pin-map": "info",
    "altium.import.bus-member": "info",
    "altium.import.harness-entry": "info",
    "altium.import.extra-board": "info",
    "altium.import.linked-by-designator": "info",
    "altium.import.pcb-only-net": "info",
    "altium.import.rule-unmapped": "info",
    "altium.import.unmapped": "info",
}
"""Every issue code of the adapter and its one severity (``docs/cli-contract.md`` lists the table)."""


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    """An issue of the adapter; ``KeyError`` for a code outside the table."""
    return Issue(code, IMPORT_ISSUE_CODES[code], message, where, hint)


class Census:
    """What one import read and mapped. ``mapped`` counts, per record kind, the records that gave a model
    entity; ``unmapped`` counts, per record kind and category, those that gave none; ``extra`` counts
    things that are no record of their own (region holes, storages kept as bytes). The mapped and the
    unmapped counts of a kind add up to the reader's record count."""

    def __init__(self) -> None:
        self.mapped: Counter[str] = Counter()
        self.unmapped: Counter[tuple[str, str]] = Counter()
        self.extra: Counter[str] = Counter()
        self.inexact_lengths = 0
        self.inexact_angles = 0

    def map(self, kind: str, count: int = 1) -> None:
        self.mapped[kind] += count

    def skip(self, kind: str, category: str, count: int = 1) -> None:
        if count:
            self.unmapped[(kind, category)] += count

    def note(self, category: str, count: int = 1) -> None:
        if count:
            self.extra[category] += count

    def total(self, kind: str) -> int:
        """Mapped plus unmapped records of ``kind``."""
        return self.mapped[kind] + sum(n for (k, _), n in self.unmapped.items() if k == kind)

    def categories(self) -> dict[str, int]:
        """Unmapped counts by category, sorted by category."""
        found: Counter[str] = Counter(self.extra)
        for (_, category), count in self.unmapped.items():
            found[category] += count
        return dict(sorted(found.items()))

    def issues(self, where: str = "") -> list[Issue]:
        """``altium.import.inexact`` and ``altium.import.unmapped``, each at most once."""
        out: list[Issue] = []
        if self.inexact_lengths or self.inexact_angles:
            out.append(
                issue(
                    "altium.import.inexact",
                    f"{self.inexact_lengths} length(s) and {self.inexact_angles} angle(s) were rounded; "
                    "the original values are in the entities' altium bags",
                    where,
                )
            )
        categories = self.categories()
        if categories:
            listed = ", ".join(f"{name} {count}" for name, count in categories.items())
            out.append(issue("altium.import.unmapped", f"records without a model entity: {listed}", where))
        return out


__all__ = ["IMPORT_ISSUE_CODES", "Census", "issue"]
