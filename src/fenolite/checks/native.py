# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The comparison of Fenolite's findings with a tool's own DRC results (change c0498, design D3).

Backend-neutral: it takes the issues of the stages that ran and the ``NativeFinding`` rows of a
``NativeDrcSource``, with the backend's table of native rule kinds and the Fenolite codes each covers
(``backends.altium.rulemap.NATIVE_CODES``). Two findings match when their codes map to the same kind and
their item sets are equal; a native row without items (a text report line) matches a Fenolite finding of
its kind whose message places it within ``NEAR`` of the row's location. Each finding is used once, in
sorted order, so the result does not depend on input order. Waived native rows are counted, not paired.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence

from fenolite.backends.base import NativeFinding
from fenolite.checks.codes import issue
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.units import parse_length

STAGE = "altium.native-drc"
NEAR = 100_000
"""How close a report line's location must be to a Fenolite finding to match it (0.1 mm)."""
EDGE = "edge"
"""The name a native row gives the board outline."""
EDGE_CODES = frozenset({"copper.edge-clearance", "silk.edge-clearance"})
"""Codes whose second item is an edge ring, which a native row names ``edge``."""
_AT = re.compile(r" at \((-?[0-9.]+), (-?[0-9.]+)\) mm")


def _items(found: Issue) -> tuple[str, ...]:
    parts = [part.strip() for part in found.where.split(", ") if part.strip()]
    if found.code in EDGE_CODES and parts:
        parts = [parts[0], EDGE]
    return tuple(sorted(parts))


def _at(found: Issue) -> Point | None:
    match = _AT.search(found.message)
    if match is None:
        return None
    try:
        return Point(parse_length(match.group(1) + "mm"), parse_length(match.group(2) + "mm"))
    except ValueError:
        return None


def _near(a: Point | None, b: Point | None) -> bool:
    return a is not None and b is not None and (a.x - b.x) ** 2 + (a.y - b.y) ** 2 <= NEAR * NEAR


def compare(
    issues: Sequence[Issue],
    native: Sequence[NativeFinding],
    table: Mapping[str, tuple[str, ...]],
    *,
    source: str,
    file: str,
) -> tuple[list[Issue], dict[str, object]]:
    """The warnings and the ``result.native`` summary of pairing ``issues`` with ``native``."""
    kind_of = {code: kind for kind, codes in table.items() for code in codes}
    ours = sorted((f for f in issues if f.code in kind_of), key=lambda f: (f.code, f.where, f.message))
    theirs = sorted((f for f in native if not f.waived), key=lambda f: (f.kind, f.primitives, f.message))
    unjudged = Counter(f.kind for f in theirs if f.kind not in table)
    theirs = [f for f in theirs if f.kind in table]
    used: set[int] = set()
    pairs: list[tuple[str, int]] = []
    native_only: list[NativeFinding] = []
    for row in theirs:
        hit = next(
            (
                n
                for n, found in enumerate(ours)
                if n not in used
                and kind_of[found.code] == row.kind
                and (_items(found) == row.primitives if row.primitives else _near(_at(found), row.at))
            ),
            None,
        )
        if hit is None:
            native_only.append(row)
        else:
            used.add(hit)
            pairs.append((row.kind, hit))
    fenolite_only = [found for n, found in enumerate(ours) if n not in used]
    by_kind: dict[str, dict[str, int]] = {}
    for kind in sorted(table):
        counts = {
            "matched": sum(1 for k, _ in pairs if k == kind),
            "fenolite_only": sum(1 for f in fenolite_only if kind_of[f.code] == kind),
            "native_only": sum(1 for f in native_only if f.kind == kind),
        }
        if any(counts.values()):
            by_kind[kind] = counts
    stale = sum(1 for f in native if f.stale)
    warnings = [
        issue(
            "check.native-only",
            f"Altium's DRC reports a {row.kind} violation of rule {row.rule!r} that Fenolite does not"
            + (f": {row.message}" if row.message else ""),
            where=", ".join(row.primitives) or row.kind,
        )
        for row in native_only
    ]
    warnings += [
        issue(
            "check.fenolite-only",
            f"{found.code} has no {kind_of[found.code]} violation in Altium's DRC results",
            where=found.where,
        )
        for found in fenolite_only
    ]
    if stale:
        warnings.append(
            issue(
                "check.native-stale",
                f"{stale} violation(s) of Altium's DRC name a primitive the document does not hold: the DRC "
                "is older than the document; run DRC in Altium and save",
                where=file,
            )
        )
    summary: dict[str, object] = {
        "source": source,
        "file": file,
        "matched": len(pairs),
        "by_kind": by_kind,
        "fenolite_only": [{"code": f.code, "where": f.where} for f in fenolite_only],
        "native_only": [f.to_json() for f in native_only],
        "unjudged": dict(sorted(unjudged.items())),
        "waived": sum(1 for f in native if f.waived),
        "stale": stale,
    }
    return warnings, summary


__all__ = ["EDGE_CODES", "NEAR", "STAGE", "compare"]
