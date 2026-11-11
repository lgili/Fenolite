# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Conservative directional channel estimates for placement, without routing."""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from fenolite.geometry import BBox

Interval = tuple[int, int]


@dataclass(frozen=True, slots=True)
class ChannelCut:
    """A cross-section through a known traversable board corridor, in integer nm."""

    key: str
    layer: str
    direction: Literal["x", "y"]
    at: int
    span: Interval

    def __post_init__(self) -> None:
        if not self.key or not self.layer or self.direction not in ("x", "y"):
            raise ValueError("a channel cut needs an identity, layer and direction")
        if any(type(v) is not int for v in (self.at, *self.span)) or self.span[0] >= self.span[1]:
            raise ValueError("a channel cut needs a positive integer span")


@dataclass(frozen=True, slots=True)
class ChannelDemand:
    """One connection or indivisible group crossing the given cuts.

    A coupled group supplies the full envelope width, including its internal gap. Clearance
    is charged once per demand as a conservative estimate of separation between lanes.
    """

    key: str
    cuts: tuple[str, ...]
    width_nm: int | None
    clearance_nm: int | None

    def __post_init__(self) -> None:
        if not self.key or not self.cuts:
            raise ValueError("channel demand needs an identity and at least one cut")
        for value, low in ((self.width_nm, 1), (self.clearance_nm, 0)):
            if value is not None and (type(value) is not int or value < low):
                raise ValueError("channel demand dimensions must be integer nm")


@dataclass(frozen=True, slots=True)
class ChannelMeasure:
    key: str
    intervals: tuple[Interval, ...]
    capacity_nm: int | None
    demand_nm: int
    overflow_nm: int | None
    unserved: tuple[str, ...]
    unknown: tuple[str, ...]


def _available(cut: ChannelCut, blocked: tuple[BBox, ...]) -> tuple[Interval, ...]:
    lo, hi = cut.span
    taken: list[Interval] = []
    for obstacle in blocked:
        x0, y0, x1, y1 = obstacle.as_tuple()
        if cut.direction == "y":
            x0, y0, x1, y1 = y0, x0, y1, x1
        if x0 <= cut.at <= x1 and max(lo, y0) < min(hi, y1):
            taken.append((max(lo, y0), min(hi, y1)))
    out: list[Interval] = []
    cursor = lo
    for start, end in sorted(taken):
        if start > cursor:
            out.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < hi:
        out.append((cursor, hi))
    return tuple(out)


def estimate_channels(
    cuts: tuple[ChannelCut, ...],
    blocked: Mapping[str, tuple[BBox, ...]],
    demands: tuple[ChannelDemand, ...],
    *,
    known_layers: frozenset[str],
) -> tuple[ChannelMeasure, ...]:
    """Charge each demand once per cut and pack its full width in one available interval.

    A cut is a supplied slice, not a proof that a path exists between successive slices.
    Unmodeled layers and missing dimensions stay unknown. Packing is deterministic and
    deliberately conservative, so unserved demand is a congestion signal.
    """
    keys = {cut.key for cut in cuts}
    if len(keys) != len(cuts) or len({demand.key for demand in demands}) != len(demands):
        raise ValueError("channel cut and demand identities must be distinct")
    by_cut: dict[str, list[tuple[int, str]]] = defaultdict(list)
    unknown: dict[str, list[str]] = defaultdict(list)
    for item in demands:
        for key in sorted(set(item.cuts)):
            if key not in keys:
                raise ValueError(f"unknown channel cut {key!r}")
            if item.width_nm is None or item.clearance_nm is None:
                unknown[key].append(item.key)
            else:
                by_cut[key].append((item.width_nm + item.clearance_nm, item.key))
    results: list[ChannelMeasure] = []
    for cut in sorted(cuts, key=lambda item: item.key):
        items = sorted(by_cut[cut.key], key=lambda item: (-item[0], item[1]))
        total = sum(width for width, _ in items)
        missing = unknown[cut.key]
        if cut.layer not in known_layers:
            results.append(
                ChannelMeasure(
                    cut.key, (), None, total, None, (), tuple(sorted(["layer:" + cut.layer, *missing]))
                )
            )
            continue
        intervals = _available(cut, blocked.get(cut.layer, ()))
        remaining = [end - start for start, end in intervals]
        capacity = sum(remaining)
        unserved: list[str] = []
        overflow = 0
        for width, ident in items:
            for index, available in enumerate(remaining):
                if available >= width:
                    remaining[index] -= width
                    break
            else:
                overflow += width
                unserved.append(ident)
        results.append(
            ChannelMeasure(
                cut.key,
                intervals,
                capacity,
                total,
                overflow if not missing else None,
                tuple(sorted(unserved)),
                tuple(sorted(missing)),
            )
        )
    return tuple(results)
