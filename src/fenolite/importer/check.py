# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The self-check of an import (change c0275, design decision 11): the design built from the emitted code
compared with the source at equivalence levels 1 to 5 under the profile ``import``. A difference that an
unexpressed kind explains is listed as explained; any other gives ``import.unequal`` (error).

Building the emitted code is the caller's step (``fenolite import`` runs ``fenolite build`` in a private
temporary folder); this module compares two models and runs nothing.
"""

from __future__ import annotations

import importlib.resources
from collections import Counter
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from fenolite.checks.equivalence import compare_designs, load_profiles, max_level
from fenolite.checks.equivalence.model import EXACT, Difference, Tolerances
from fenolite.core.errors import Issue
from fenolite.importer.codes import issue
from fenolite.importer.coverage import Unexpressed, explained
from fenolite.model.design import Design

PROFILE = "import"


@dataclass(frozen=True, slots=True)
class SelfCheck:
    """The levels compared, whether every difference is explained, the explained and the unexplained
    differences, and the issues."""

    levels: tuple[int, ...]
    equivalent: bool
    explained: tuple[Difference, ...] = ()
    unexplained: tuple[Difference, ...] = ()
    issues: tuple[Issue, ...] = ()

    def as_json(self) -> dict[str, object]:
        return {"levels": list(self.levels), "equivalent": self.equivalent}


def _tolerances() -> Tolerances:
    text = importlib.resources.files("fenolite").joinpath("convert/data/profiles.toml").read_text("utf-8")
    for profile in load_profiles(text, file="profiles.toml"):
        if profile.name == PROFILE:
            return Tolerances(profile.tolerance_nm, profile.tolerance_udeg, profile.tolerance_ppm)
    return EXACT


CopperItem = tuple[object, ...]


def _copper(design: Design) -> dict[str, Counter[CopperItem]]:
    """Every track, arc and via of ``design`` by net name, with its geometry, width or sizes, layers and
    lock flag."""
    names = {net.id: net.name for net in design.circuit.nets}
    board = design.board
    found: dict[str, Counter[CopperItem]] = {}
    if board is None:
        return found
    items: list[tuple[str, CopperItem]] = []
    for t in board.tracks:
        items.append((names.get(t.net_id or "", ""), ("track", t.start, t.end, t.width, t.layer, t.locked)))
    for a in board.arcs:
        shape = ("arc", a.start, a.mid, a.end, a.width, a.layer, a.locked)
        items.append((names.get(a.net_id or "", ""), shape))
    for v in board.vias:
        shape = ("via", v.position, v.diameter, v.drill, tuple(v.layers), v.via_type, v.protection, v.locked)
        items.append((names.get(v.net_id or "", ""), shape))
    for net, item in items:
        found.setdefault(net, Counter())[item] += 1
    return found


def copper_differences(source: Design, built: Design) -> tuple[Difference, ...]:
    """Level 5 of the import, item by item: the nets whose tracks, arcs and vias differ in count or in any
    field. ``equivalent`` judges a net by what its copper joins and how long it is; the import also proves
    that every item came through (a via that joins nothing included)."""
    one, other = _copper(source), _copper(built)
    out: list[Difference] = []
    for net in sorted(set(one) | set(other)):
        a, b = one.get(net, Counter()), other.get(net, Counter())
        if a != b:
            lost, extra = sum((a - b).values()), sum((b - a).values())
            out.append(
                Difference(
                    5,
                    "copper-items",
                    net or "(no net)",
                    "copper",
                    f"{lost} item(s) only here",
                    f"{extra} item(s) only here",
                )  # fmt: skip
            )
    return tuple(out)


def self_check(
    source: Design, built: Design, unexpressed: Sequence[Unexpressed], *, variants: Collection[str] = ()
) -> SelfCheck:
    """``built`` compared with ``source`` at every level both hold, up to 5, and item by item at level 5.
    A level-3 footprint name of a ref in ``variants`` (written as ``<name>_2``) is explained."""
    level = max_level(source, built)
    report = compare_designs(source, built, level=level, tolerances=_tolerances(), frame="absolute")
    levels = tuple(result.level for result in report.levels)
    said: list[Difference] = []
    unsaid: list[Difference] = []
    found = [d for result in report.levels for d in result.differences]
    if level >= 5:
        found += copper_differences(source, built)
    for difference in found:
        level_kind = (difference.level, difference.kind)
        renamed = level_kind == (3, "footprint-name") and difference.where in variants
        if renamed or explained(difference.level, difference.kind, unexpressed):
            said.append(difference)
        else:
            unsaid.append(difference)
    issues = tuple(
        issue(
            "import.unequal",
            f"level {d.level} {d.kind} at {d.where}: the source has {d.a or '-'}, the emitted code builds "
            f"{d.b or '-'}",
            where=f"level {d.level}: {d.where}",
            hint="report the board: the emitted code does not rebuild it",
        )
        for d in unsaid
    )
    return SelfCheck(levels, not unsaid, tuple(said), tuple(unsaid), issues)


__all__ = ["PROFILE", "SelfCheck", "self_check"]
