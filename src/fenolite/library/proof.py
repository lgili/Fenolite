# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The proof gate of board items (change c0279, ``docs/library-repo.md``, "Proof gate"; change c0281,
"Skipped levels") and the benchmark table.

A board enters the library only when c0278's ``verify-source`` gives every level ``equal`` or
``accepted``, with the item's ``fidelity.accepted`` entries as exclusions, and the statuses equal those
recorded in ``fidelity.proof.levels``. A level may be ``skipped`` only with a recorded reason
(``fidelity.proof.skipped``) other than ``build-failed``. The derived result is ``pass`` (every level equal
or skipped with a reason), ``pass-with-accepted`` (some accepted) or ``fail``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from fenolite.core.errors import Issue
from fenolite.library.codes import issue

PASS = "pass"
PASS_ACCEPTED = "pass-with-accepted"
FAIL = "fail"
REFUSED_SKIP = frozenset({"build-failed"})
"""Skip reasons that never pass: no level ran."""


@dataclass(frozen=True)
class Gate:
    """The gate's ``result``, the ``skipped`` levels with their reasons and the ``issues``."""

    result: str
    skipped: Mapping[str, str] = field(default_factory=lambda: {})
    issues: tuple[Issue, ...] = ()


def _recorded(fidelity: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    proof = cast(Mapping[str, Any], fidelity.get("proof") or {})
    levels = {str(k): str(v) for k, v in cast(Mapping[str, Any], proof.get("levels") or {}).items()}
    skipped = {str(k): str(v) for k, v in cast(Mapping[str, Any], proof.get("skipped") or {}).items()}
    return levels, skipped


def derive(levels: Mapping[str, str], skipped: Mapping[str, str], where: str = "") -> Gate:
    """The gate over a status per level and the reasons of the skipped levels."""
    issues: list[Issue] = []
    shown: dict[str, str] = {}
    for level, status in sorted(levels.items()):
        if status in ("equal", "accepted"):
            continue
        if status == "skipped":
            reason = skipped.get(level, "")
            if reason and reason not in REFUSED_SKIP:
                shown[level] = reason
                continue
            said = "without a recorded reason" if not reason else f"because {reason}"
            issues.append(
                issue(
                    "library.proof-failed",
                    f"{where}level {level} was skipped {said}",
                    where=where.rstrip(": ") or level,
                    hint="record fidelity.proof.skipped with the reason, or make the level run",
                )
            )
            continue
        issues.append(
            issue(
                "library.proof-failed", f"{where}level {level} is {status}", where=where.rstrip(": ") or level
            )
        )
    if issues or not levels:
        if not levels:
            issues.append(
                issue("library.proof-failed", f"{where}no proof level is recorded", where=where.rstrip(": "))
            )
        return Gate(FAIL, shown, tuple(issues))
    result = PASS_ACCEPTED if any(status == "accepted" for status in levels.values()) else PASS
    return Gate(result, shown, ())


def recorded_result(fidelity: Mapping[str, Any] | None) -> str | None:
    """The result of the proof recorded in a ``fidelity`` member, or ``None`` without one."""
    if not isinstance(fidelity, Mapping):
        return None
    levels, skipped = _recorded(fidelity)
    return derive(levels, skipped).result if levels else None


def _key(difference: Mapping[str, Any]) -> str:
    return f"{difference.get('level')}:{difference.get('kind')}:{difference.get('where')}"


def gate(report: Mapping[str, Any], fidelity: Mapping[str, Any], *, item: str = "") -> Gate:
    """The gate of one board: ``report`` is the ``result`` of ``fenolite verify-source --json`` run with
    the item's provenance (levels, differences, accepted), ``fidelity`` the item's member."""
    where = f"{item}: " if item else ""
    recorded, recorded_skipped = _recorded(fidelity)
    rows = cast(Sequence[Mapping[str, Any]], report.get("levels") or [])
    levels = {str(row.get("level")): str(row.get("status")) for row in rows}
    skipped = {
        str(row.get("level")): str(row.get("reason") or "") for row in rows if row.get("status") == "skipped"
    }
    skipped = {level: reason or recorded_skipped.get(level, "") for level, reason in skipped.items()}
    found = derive(levels, skipped, where)
    issues = list(found.issues)
    for difference in cast(Sequence[Mapping[str, Any]], report.get("differences") or []):
        issues.append(
            issue(
                "library.proof-failed",
                f"{where}a new difference at level {difference.get('level')}: {_key(difference)}"
                f" ({difference.get('a')!r} -> {difference.get('b')!r})",
                where=item or _key(difference),
                hint="fix the cause, or add a reviewed entry to fidelity.accepted",
            )
        )
    for level in sorted(set(levels) | set(recorded)):
        if levels.get(level) != recorded.get(level):
            issues.append(
                issue(
                    "library.proof-failed",
                    f"{where}level {level} is {levels.get(level, 'absent')} but fidelity.proof records "
                    f"{recorded.get(level, 'nothing')}",
                    where=item or level,
                    hint="run verify-source --record and review the new statuses",
                )
            )
    if issues:
        return Gate(FAIL, found.skipped, tuple(issues))
    return found


def bench_table(
    runs: Sequence[Mapping[str, Any]], *, previous: Mapping[str, str] | None = None
) -> list[dict[str, Any]]:
    """The benchmark table: one row per board run (``id``, ``levels``, ``seconds``, ``differences`` and the
    ``fidelity`` member), sorted by id, with the gate result and ``issue`` true for a board that fails now
    and did not fail in ``previous`` (id → result of the last table)."""
    before = previous or {}
    rows: list[dict[str, Any]] = []
    for run in sorted(runs, key=lambda r: str(r.get("id"))):
        ident = str(run.get("id"))
        report = {"levels": run.get("levels", []), "differences": run.get("differences", [])}
        result = gate(report, cast(Mapping[str, Any], run.get("fidelity") or {}), item=ident)
        rows.append(
            {
                "id": ident,
                "levels": {
                    str(row.get("level")): row.get("status")
                    for row in cast(list[Mapping[str, Any]], run.get("levels", []))
                },
                "seconds": run.get("seconds"),
                "differences": len(cast(list[object], run.get("differences", []))),
                "result": result.result,
                "issue": result.result == FAIL and before.get(ident) != FAIL,
            }
        )
    return rows


__all__ = ["FAIL", "PASS", "PASS_ACCEPTED", "Gate", "bench_table", "derive", "gate", "recorded_result"]
