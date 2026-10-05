# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The container round-trip stages of a document check (capability verification-loop, "Document check
pipeline"; change c0044): one stage per level from the verdicts of every document of a set.

A verdict comes from the backend (``DocumentValidator.container_roundtrip``) with its own evidence; this
module decides the issue codes, the summary and the status, and names no backend.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping

from fenolite.backends.base import ContainerLevel, ContainerRoundTrip
from fenolite.checks.codes import issue
from fenolite.checks.stages import StageResult, StageSkip, ran
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence

FAILED: Mapping[str, str] = {"RT-A0": "check.rta0-failed", "RT-A1": "check.rta1-failed"}
"""The error code of a judged verdict that did not pass, per level."""
READ_REFUSED = "read-refused"
QUIET_REASONS = frozenset({"not-a-container", READ_REFUSED})
"""Reasons that are only counted: a text file has no container to copy, and a refused reading is already
an input issue (``check.read-refused``)."""
_WHAT: Mapping[str, str] = {
    "RT-A0": "a copy of the container lost or changed",
    "RT-A1": "the records differ after encoding and reading again at",
}


def container_stage(
    name: str, level: ContainerLevel, verdicts: Mapping[str, ContainerRoundTrip | None]
) -> StageResult:
    """One stage from the verdict of each document (``None`` for a document whose reading was refused).

    - A judged verdict that did not pass gives one ``check.rta0-failed`` or ``check.rta1-failed`` error at
      ``<document>:<difference>``, and the stage then carries ``UNVERIFIED``.
    - A verdict that is not judged is counted in ``summary.unjudged`` by reason and gives one
      ``check.roundtrip-unjudged`` info, except for ``not-a-container`` and ``read-refused``.
    - For ``RT-A1``, a document that passed with streams whose encoded bytes differ gives one
      ``check.rta1-normalised`` info.

    Without any judged document the stage is skipped: ``read-refused`` when every document was refused, else
    ``not-judged``; its summary still holds the counts.
    """
    issues: list[Issue] = []
    unjudged: Counter[str] = Counter()
    evidence: list[Evidence] = []
    judged = failed = streams = records = bytes_equal = opaque = 0
    for document in sorted(verdicts):
        verdict = verdicts[document]
        if verdict is None:
            unjudged[READ_REFUSED] += 1
            continue
        if verdict.level != level:
            raise ValueError(f"{document}: a {verdict.level} verdict in the {level} stage")
        if not verdict.judged:
            unjudged[verdict.reason] += 1
            if verdict.reason not in QUIET_REASONS:
                issues.append(
                    issue(
                        "check.roundtrip-unjudged",
                        f"{level} is not judged for this document: {verdict.reason}",
                        where=document,
                    )
                )
            continue
        judged += 1
        evidence.append(verdict.evidence)
        streams += verdict.streams
        records += verdict.records
        bytes_equal += verdict.bytes_equal
        opaque += verdict.opaque_count
        if not verdict.passed:
            failed += 1
            more = len(verdict.different) - 1
            also = f" (and {more} more)" if more > 0 else ""
            issues.append(
                issue(FAILED[level], f"{_WHAT[level]} {verdict.difference}{also}",
                      where=f"{document}:{verdict.difference}")
            )  # fmt: skip
        elif level == "RT-A1" and verdict.bytes_equal < verdict.streams:
            count = verdict.streams - verdict.bytes_equal
            issues.append(
                issue(
                    "check.rta1-normalised",
                    f"{count} stream(s) have equal records and other bytes after encoding",
                    where=document,
                )
            )
    summary: dict[str, object] = {
        "level": level,
        "documents": judged,
        "streams": streams,
        "failed": failed,
        "unjudged": dict(sorted(unjudged.items())),
    }
    if level == "RT-A1":
        summary |= {"records": records, "bytes_equal": bytes_equal, "opaque_count": opaque}
    if not judged:
        refused = bool(verdicts) and unjudged[READ_REFUSED] == len(verdicts)
        reason: StageSkip = READ_REFUSED if refused else "not-judged"
        return StageResult(name, "skipped", Evidence(), tuple(issues), summary, reason)
    return ran(name, issues, Evidence() if failed else Evidence.combine(*evidence), summary)


__all__ = ["FAILED", "QUIET_REASONS", "container_stage"]
