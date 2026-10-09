# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Escape requests: the parts whose pads a router escapes before it routes (capability routing, "Escape
requests for routing"; change c0110).

A request is explicit (``fenolite route --escape REF[=grid|perimeter]``): escaping every fine-pitch part
would make worse routes for parts a router escapes well by itself, and a pitch threshold would be a shipped
value. The kind tells a grid of pads (a BGA) from a perimeter (QFN, QFP, SOIC) by the centres of the
part's pads without a drill, in integer arithmetic, so it holds for a part turned by any angle.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isqrt

from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.units import Nm
from fenolite.routing.protocol import JobEscape

KINDS = ("grid", "perimeter")
TOLERANCE: Nm = 1_000
"""1 µm: how far a distance may differ from the pitch, and two neighbours from opposite or orthogonal."""


@dataclass(frozen=True, slots=True)
class PartPad:
    """One pad of a part in board coordinates: its centre, its net name (empty without a net) and its
    drill (``None`` for a surface pad)."""

    position: Point
    net: str = ""
    drill: Nm | None = None


def _square(dx: int, dy: int) -> int:
    return dx * dx + dy * dy


def pitch(points: Sequence[Point]) -> Nm:
    """The smallest distance between two of ``points``, rounded down to a nanometre; 0 for fewer than two."""
    best: int | None = None
    for index, first in enumerate(points):
        for second in points[index + 1 :]:
            found = _square(second.x - first.x, second.y - first.y)
            if found and (best is None or found < best):
                best = found
    return 0 if best is None else isqrt(best)


def _near(length_sq: int, step: int) -> bool:
    """Whether a vector of squared length ``length_sq`` is ``step`` long within ``TOLERANCE``."""
    low, high = max(0, step - TOLERANCE), step + TOLERANCE
    return low * low <= length_sq <= high * high


def escape_kind(points: Sequence[Point]) -> str:
    """``grid`` when one of ``points`` has, at the pitch ``p`` (within 1 µm), four neighbours on two
    orthogonal directions, both ways; ``perimeter`` otherwise."""
    step = pitch(points)
    if step == 0:
        return "perimeter"
    for centre in points:
        around = [
            (other.x - centre.x, other.y - centre.y)
            for other in points
            if other != centre and _near(_square(other.x - centre.x, other.y - centre.y), step)
        ]
        axes = [
            first
            for first in around
            if any(_square(first[0] + second[0], first[1] + second[1]) <= TOLERANCE**2 for second in around)
        ]
        for index, first in enumerate(axes):
            for second in axes[index + 1 :]:
                if abs(first[0] * second[0] + first[1] * second[1]) <= TOLERANCE * step:
                    return "grid"
    return "perimeter"


def _skipped(message: str, where: str, hint: str) -> Issue:
    return Issue("route.escape-skipped", "warning", message, where, hint=hint)


def parse(pattern: str) -> tuple[str, str | None]:
    """``REF`` or ``REF=grid|perimeter`` → the glob and the kind it overrides, or ``None``. Any other
    suffix raises ``ValueError``."""
    glob, separator, kind = pattern.partition("=")
    if not separator:
        return glob, None
    if kind not in KINDS or not glob:
        raise ValueError(
            f"invalid --escape {pattern!r}: the kind {kind!r} is not grid or perimeter"
            if glob
            else f"invalid --escape {pattern!r}: a reference pattern is needed"
        )
    return glob, kind


def requests(
    parts: Mapping[str, Sequence[PartPad]], patterns: Sequence[str], nets: Sequence[str]
) -> tuple[tuple[JobEscape, ...], tuple[Issue, ...]]:
    """One request per part that a pattern matches, in reference order, and one ``route.escape-skipped``
    per pattern that matches no part and per matched part without a job net. A part matched by several
    patterns takes the kind of the first."""
    parsed = [parse(pattern) for pattern in patterns]  # every pattern is checked before any is used
    job_nets = set(nets)
    chosen: dict[str, str | None] = {}
    issues: list[Issue] = []
    for pattern, (glob, kind) in zip(patterns, parsed, strict=True):
        matched = sorted(ref for ref in parts if fnmatch.fnmatchcase(ref, glob))
        if not matched:
            issues.append(
                _skipped(
                    f"--escape {pattern} matches no part of the board",
                    pattern,
                    "name parts by reference, for example U1 or U*",
                )
            )
        for ref in matched:
            chosen.setdefault(ref, kind)
    found: list[JobEscape] = []
    for ref in sorted(chosen):
        pads = parts[ref]
        on_part = sorted({pad.net for pad in pads if pad.net in job_nets})
        surface = [pad.position for pad in pads if pad.drill is None]
        if not on_part:
            issues.append(
                _skipped(
                    f"part {ref} has no pad on a net of the job, so it is not escaped",
                    ref,
                    "select a net of the part with --nets",
                )
            )
            continue
        if len(surface) < 2:
            issues.append(
                _skipped(
                    f"part {ref} has fewer than two surface pads, so it is not escaped",
                    ref,
                    "escape parts of surface pads: a BGA, a QFN, a QFP",
                )
            )
            continue
        kind = chosen[ref] or escape_kind(surface)
        found.append(JobEscape(ref, kind, pitch(surface), tuple(on_part)))
    return tuple(found), tuple(issues)


__all__ = ["KINDS", "TOLERANCE", "PartPad", "escape_kind", "parse", "pitch", "requests"]
