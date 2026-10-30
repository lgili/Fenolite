# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Back-solving land goals from cited manufacturer patterns (change c0260, decision 5).

A calibration record gives toleranced dimensions and a manufacturer ``[land]`` for the same package.
``sample`` returns its land class and the goals its pattern implies (``back_solve``); ``calibrate`` takes the
lower median of each goal over the records of a class and rounds it to 10 µm. A class with fewer than
``MIN_RECORDS`` records gets no goals. Ball ratios of grid arrays are the lower median of land diameter over
ball nominal, rounded to 1/100. ``tools/calibrate_lands.py`` writes the result into ``_table1``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction

from fenolite.catalog.footprints.gullwing import land_class
from fenolite.catalog.footprints.lands import Goals, RowLand, back_solve
from fenolite.catalog.footprints.record import Keys, Package
from fenolite.core.quantities import LengthRange

MIN_RECORDS = 3
"""A class needs at least this many calibration records to get goals."""
STEP = 10_000
"""Goals are rounded to this step (10 µm), half away from zero."""


@dataclass(frozen=True, slots=True)
class Sample:
    """What one calibration record implies: its class and its goals (or its ball ratio)."""

    name: str
    land_class: str
    goals: Goals | None = None
    ratio: Fraction | None = None


def _range(keys: Keys | None, key: str) -> LengthRange:
    value = keys.length(key) if keys is not None else None
    if value is None:
        raise ValueError(f"the calibration record has no {key}")
    return value


def _land(land: Keys, spacing_key: str) -> RowLand:
    pad = land.table("pad")
    spacing = land.length(spacing_key)
    length = _range(pad, "length").nominal
    width = _range(pad, "width").nominal
    centre = spacing.nominal if spacing is not None else None
    if length is None or width is None or centre is None:
        raise ValueError(f"the [land] needs pad and {spacing_key}")
    return RowLand(centre + length, centre - length, width)


def _shift(body: LengthRange, pull_back: LengthRange | None) -> LengthRange:
    if (
        pull_back is None
        or body.min is None
        or body.max is None
        or pull_back.min is None
        or pull_back.max is None
    ):
        return body
    return LengthRange(body.min - 2 * pull_back.max, None, body.max - 2 * pull_back.min)


def sample(package: Package) -> Sample:
    """The class and implied goals of one calibration record; ``ValueError`` when it cannot calibrate."""
    land = package.land
    if land is None:
        raise ValueError(f"{package.name} has no [land]")
    keys = package.keys
    family = package.family
    if family == "grid":
        ball = _range(keys.table("ball"), "diameter").nominal
        diameter = _range(land, "pad_diameter").nominal
        if not ball or not diameter:
            raise ValueError(f"{package.name} has no ball or land diameter")
        return Sample(package.name, f"grid-{keys.text('pad') or 'nsmd'}", ratio=Fraction(diameter, ball))
    if family == "chip":
        body = keys.table("body")
        goals = back_solve(
            _range(body, "length"),
            _range(keys.table("terminal"), "length"),
            _range(body, "width"),
            _land(land, "row_spacing"),
        )
        return Sample(package.name, "chip", goals)
    if family == "molded":
        lead = keys.table("lead")
        goals = back_solve(
            _range(keys, "span"), _range(lead, "length"), _range(lead, "width"), _land(land, "row_spacing")
        )
        return Sample(package.name, "molded", goals)
    if family == "gullwing":
        pitch = _range(keys, "pitch").nominal or 0
        lead = keys.table("lead")
        quad = keys.text("arrangement") == "quad"
        span = _range(keys, "span_x" if quad else "span")
        goals = back_solve(
            span,
            _range(lead, "length"),
            _range(lead, "width"),
            _land(land, "row_spacing_x" if quad else "row_spacing"),
        )
        return Sample(package.name, land_class(pitch), goals)
    if family == "nolead":
        terminal = keys.table("terminal")
        quad = keys.text("arrangement") == "quad"
        span = _shift(_range(keys.table("body"), "width"), keys.length("pull_back"))
        goals = back_solve(
            span,
            _range(terminal, "length"),
            _range(terminal, "width"),
            _land(land, "row_spacing_x" if quad else "row_spacing"),
        )
        return Sample(package.name, "nolead", goals)
    raise ValueError(f"the family {family!r} has no calibrated goals")


def lower_median(values: Iterable[int]) -> int:
    """The lower median: the middle value, or the lower of the two middle values."""
    ordered = sorted(values)
    return ordered[(len(ordered) - 1) // 2]


def to_step(value: int) -> int:
    """``value`` rounded to ``STEP``, half away from zero."""
    sign = -1 if value < 0 else 1
    return sign * ((abs(value) + STEP // 2) // STEP * STEP)


def ratio_step(value: Fraction) -> Fraction:
    """``value`` rounded to 1/100, half up."""
    return Fraction((value.numerator * 200 + value.denominator) // (2 * value.denominator), 100)


@dataclass(frozen=True, slots=True)
class Calibration:
    """The goals and ball ratios of a set of records, with the records used per class."""

    goals: Mapping[str, Goals]
    ball_ratio: Mapping[str, Fraction]
    used: Mapping[str, tuple[str, ...]]


def calibrate(samples: Iterable[Sample]) -> Calibration:
    """Lower medians per class of at least ``MIN_RECORDS`` samples, rounded (decision 5)."""
    by_class: dict[str, list[Sample]] = {}
    for found in samples:
        by_class.setdefault(found.land_class, []).append(found)
    goals: dict[str, Goals] = {}
    ratios: dict[str, Fraction] = {}
    used: dict[str, tuple[str, ...]] = {}
    for cls in sorted(by_class):
        group = by_class[cls]
        used[cls] = tuple(sorted(s.name for s in group))
        if len(group) < MIN_RECORDS:
            continue
        if cls.startswith("grid-"):
            ordered = sorted(s.ratio for s in group if s.ratio is not None)
            ratios[cls.removeprefix("grid-")] = ratio_step(ordered[(len(ordered) - 1) // 2])
            continue
        solved = [s.goals for s in group if s.goals is not None]
        goals[cls] = Goals(
            to_step(lower_median(g.toe for g in solved)),
            to_step(lower_median(g.heel for g in solved)),
            to_step(lower_median(g.side for g in solved)),
        )
    return Calibration(goals, ratios, used)


__all__ = [
    "MIN_RECORDS",
    "STEP",
    "Calibration",
    "Sample",
    "calibrate",
    "lower_median",
    "ratio_step",
    "sample",
    "to_step",
]
