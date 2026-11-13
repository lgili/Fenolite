# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The free channel of a net between two points: a bracket of the widest track ``search`` routes there under
the clearances in force (capability routing, "Free channel width"; change c0501, design D5).

Each probe is one bounded ``search`` at a width; the bisection keeps the widest width with a path (``low``)
and the narrowest width a complete search refused (``high``). The resolution is an explicit search bound,
like the grid. ``World`` adds ``MARGIN`` to each clearance, so ``high`` may lie up to twice ``MARGIN`` below
the exact width a track of the board's rules could take."""

from __future__ import annotations

from dataclasses import dataclass
from math import isqrt
from typing import cast

from fenolite.core.coords import Point
from fenolite.model.rules import Selector
from fenolite.routing.octilinear import Polyline, World
from fenolite.routing.protocol import JobAttach, JobSubject, RoutingJob
from fenolite.routing.search import Gap, Limits, Outcome, search
from fenolite.routing.search_grid import Stop

RESOLUTION = 10_000
"""The default resolution of the bisection, 10 µm: a search bound, not a manufacturing value."""
FLOOR = 1_000
"""The default lower width when no board-wide ``track_width`` rule gives a minimum: 1 µm."""
_ALL = Selector("all")


@dataclass(frozen=True, slots=True)
class ChannelResult:
    """The bracket of the widest track: ``low`` the widest width with a path (``None``: none at the smallest
    width tried), ``high`` the narrowest width refused or the start bound, the path at ``low``, the
    ``pinch`` of the refusal that set ``high`` (its widest free gap), whether ``high`` is only the grid's
    (``grid_limited``), and ``undecided`` when a probe was cut by a bound."""

    low: int | None
    high: int
    runs: tuple[tuple[str, Polyline], ...] = ()
    vias: tuple[Point, ...] = ()
    pinch: Gap | None = None
    grid_limited: bool = True
    undecided: bool = False
    probes: int = 0
    refusal: Outcome | None = None


def floor_width(job: RoutingJob) -> int:
    """The largest ``min`` of the board-wide ``track_width`` rules of the job's design, else ``FLOOR``."""
    rules = job.design.rules.rules if job.design.rules is not None else ()
    return max(
        (
            rule.min
            for rule in rules
            if rule.kind == "track_width"
            and rule.severity != "ignore"
            and rule.min is not None
            and rule.selector_a == _ALL
            and rule.selector_b is None
        ),
        default=FLOOR,
    )


def subject_of(job: RoutingJob, net: str, a: JobAttach, b: JobAttach, width: int) -> JobSubject:
    """The connection of ``net`` from ``a`` to ``b`` at ``width``: the layers and the via of the job's net of
    that name, else every job layer and no via."""
    held = next((n for n in job.nets if n.name == net), None)
    layers = held.layers if held is not None and held.layers else job.layers
    via = (held.via_diameter, held.via_drill) if held is not None else (0, 0)
    return JobSubject(f"connection:{net}:{a.name}~{b.name}", "connection", net, a, b, width, layers, *via)


def widest(
    job: RoutingJob,
    net: str,
    a: JobAttach,
    b: JobAttach,
    *,
    limits: Limits,
    low: int | None = None,
    high: int | None = None,
    resolution: int = RESOLUTION,
    stop: Stop = lambda: None,
) -> ChannelResult:
    """Bisect the track width of ``net`` from ``a`` to ``b`` (design D5): a found path raises ``low``, a
    ``no-room`` refusal lowers ``high``, a probe cut by a bound stops with ``undecided``. ``low`` defaults to
    ``floor_width``, ``high`` to the distance between the two points."""
    if resolution < 1:
        raise ValueError("the resolution is at least 1 nm")
    pads = cast("tuple[object, ...]", job.extra.get("board_pads", ()))
    outline = cast("tuple[tuple[Point, ...], ...]", job.extra.get("outline", ()))
    world = World(job, pads, outline)
    reach = 1_000 * (abs(a.at.x - b.at.x) + abs(a.at.y - b.at.y) + 1)
    bottom = floor_width(job) if low is None else low
    top = max(bottom + 1, isqrt((a.at.x - b.at.x) ** 2 + (a.at.y - b.at.y) ** 2)) if high is None else high
    probes = 0

    def probe(width: int) -> Outcome:
        nonlocal probes
        probes += 1
        out = search(job, subject_of(job, net, a, b, width), world, limits, max_length=reach, stop=stop)
        if out.runs and not all(world.fits(net, layer, points, width) for layer, points in out.runs):
            return Outcome(reason="no-room", stats=out.stats)
        return out

    first = probe(bottom)
    if not first.runs:
        cut = first.reason != "no-room"
        return ChannelResult(None, bottom, (), (), first.widest, cut or not first.proven, cut, probes, first)
    best, refusal = first, None
    while top - bottom > resolution:
        width = (bottom + top) // 2
        out = probe(width)
        if out.runs:
            bottom, best = width, out
        elif out.reason == "no-room":
            top, refusal = width, out
        else:
            return ChannelResult(
                bottom,
                top,
                best.runs,
                best.vias,
                *_pinch(refusal),
                undecided=True,
                probes=probes,
                refusal=out,
            )
    return ChannelResult(bottom, top, best.runs, best.vias, *_pinch(refusal), probes=probes, refusal=refusal)


def _pinch(refusal: Outcome | None) -> tuple[Gap | None, bool]:
    if refusal is None:
        return None, True
    return refusal.widest, not refusal.proven


__all__ = ["FLOOR", "RESOLUTION", "ChannelResult", "floor_width", "subject_of", "widest"]
