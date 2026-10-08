# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``roundtrip.rta3`` stage (capability altium-verification, "Round-trip level RT-A3"; change c0090):
a document is read, its model is written as new documents, and those are read again.

The backend makes the trip (``ModelWriter.model_roundtrip``) and this module turns its verdict into a
stage: one ``check.rta3-failed`` per difference inside the written scope, and one ``check.rta3-unwritten``
with the counts of what the write left out. The stage is opt-in and writes nothing under the input.
"""

from __future__ import annotations

from fenolite.backends.base import DiffReport, ModelRoundTrip, ModelScope
from fenolite.checks.codes import issue
from fenolite.checks.diff import Change, diff_designs
from fenolite.checks.stages import StageResult, ran, skipped
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

NAME = "roundtrip.rta3"
MAX_ISSUES = 50
"""The differences reported as issues; ``summary.differences`` holds the full count."""
PRESENTATION = "regenerated"
"""What a rewrite does with the schematic's drawing: the schematic is generated from the circuit."""
_SHOWN = 80


def compare(a: Design, b: Design, scope: ModelScope, /) -> DiffReport:
    """``diff_designs`` under ``scope``: the comparison handed to the backend (``base.ModelCompare``)."""
    return diff_designs(a, b, scope=scope)


def _short(text: str) -> str:
    return text if len(text) <= _SHOWN else text[: _SHOWN - 1] + "…"


def _message(change: Change) -> str:
    if change.change == "changed":
        return f"the document reads {_short(change.a)} and its rewrite reads {_short(change.b)}"
    if change.change == "removed":
        return f"the document holds {_short(change.a)}, and its rewrite does not"
    return f"the rewrite holds {_short(change.b)}, and the document does not"


def rta3_stage(trip: ModelRoundTrip) -> StageResult:
    """The stage of the verdict ``trip``. Not judged: skipped with the verdict's reason. The summary holds
    ``level``, ``holds``, ``differences``, ``unwritten``, ``written``, ``files`` and ``presentation``."""
    if not trip.judged:
        return skipped(NAME, "no-document")
    issues: list[Issue] = [
        issue("check.rta3-failed", _message(change), where=change.path)
        for change in trip.differences[:MAX_ISSUES]
    ]
    if trip.unwritten:
        listed = ", ".join(f"{kind} {count}" for kind, count in sorted(trip.unwritten.items()))
        issues.append(issue("check.rta3-unwritten", f"not in the rewritten documents: {listed}"))
    summary: dict[str, object] = {
        "level": "RT-A3",
        "holds": trip.equal,
        "differences": len(trip.differences),
        "unwritten": dict(sorted(trip.unwritten.items())),
        "written": dict(sorted(trip.written.items())),
        "files": sorted(trip.files),
        "presentation": PRESENTATION,
    }
    evidence = trip.evidence if trip.equal else Evidence(Level.UNVERIFIED)
    return ran(NAME, issues, evidence, summary)


__all__ = ["MAX_ISSUES", "NAME", "PRESENTATION", "compare", "rta3_stage"]
