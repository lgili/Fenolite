# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The role copper as the build takes it (change c0243, decision 9; capability design-dsl, "Role copper in
the DSL"; ``docs/roles.md``, "Role copper").

The lens may not import ``fenolite.roles`` (``package-layering``): the build takes the planner as a
callable from ``cli/cmd_build.py``, as ``checks.roles`` takes ``fenolite.roles.judge`` from ``cmd_check``.
``RoleCopperPlanner`` is that callable's protocol, ``RoleCopperPlanLike`` the plan it makes, and
``apply_plan`` the one way a plan reaches a design: the role items it replaces removed, its plain zones,
rule areas and rules added, and its c0224 records resolved by ``backends.kicad.generate.resolve_generated``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Protocol

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad import generate as generate_mod
from fenolite.backends.kicad.outline import BoardOutline
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.model.board import Keepout, Track, Zone
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet


class RoleCopperPlanLike(Protocol):
    """A plan of the role copper: c0224 records, plain zones and rule areas, model rules, the ids of the role
    items it replaces, and its issues."""

    @property
    def records(self) -> Sequence[generate_mod.GeneratedLike]: ...
    @property
    def zones(self) -> Sequence[Zone]: ...
    @property
    def keepouts(self) -> Sequence[Keepout]: ...
    @property
    def rules(self) -> Sequence[Rule]: ...
    @property
    def remove(self) -> Sequence[str]: ...
    @property
    def tracks(self) -> Sequence[Track]: ...


class RoleCopperOutcomeLike(Protocol):
    """What a planner returns: the design after (the input when refused), its issues, the summary of
    ``result.role_copper`` and its evidence."""

    @property
    def design(self) -> Design: ...
    @property
    def issues(self) -> Sequence[Issue]: ...
    @property
    def summary(self) -> Mapping[str, object]: ...
    @property
    def evidence(self) -> Evidence: ...


Apply = Callable[[Design, RoleCopperPlanLike], tuple[Design, list[Issue]]]


class RoleCopperPlanner(Protocol):
    """The planner the build is given (``fenolite.roles.copper.run`` with the stored roles bound): from the
    placed design, its pads in the board frame, the request and the way to apply a plan, to an outcome."""

    def __call__(
        self, design: Design, pads: Sequence[BoardPad], request: object, apply: Apply
    ) -> RoleCopperOutcomeLike: ...


def apply_plan(
    design: Design,
    plan: RoleCopperPlanLike,
    *,
    unplaced: Collection[str] = (),
    keepouts: Sequence[Keepout] = (),
    outline: BoardOutline | None = None,
    edge_floor: int = 0,
) -> tuple[Design, list[Issue]]:
    """``design`` with ``plan`` applied, in the order of decision 11: the items whose ids ``plan.remove``
    names taken out, the plan's rule areas (corridors) and rules added, then its plain zones (the ground
    planes), then its records resolved after them. The rule areas the design held keep their uuids (the
    resolution marks every rule area of a build, which a board read from a file must not see)."""
    board = design.board
    if board is None:
        return design, []
    gone = set(plan.remove)
    rules = design.rules if design.rules is not None else RuleSet(id="rules_role_copper")
    names = {rule.name for rule in plan.rules}
    trimmed = dataclasses.replace(
        board,
        zones=tuple(zone for zone in board.zones if zone.id not in gone) + tuple(plan.zones),
        keepouts=tuple(area for area in board.keepouts if area.id not in gone) + tuple(plan.keepouts),
        tracks=tuple(item for item in board.tracks if item.id not in gone) + tuple(plan.tracks),
        vias=tuple(item for item in board.vias if item.id not in gone),
    )
    staged = dataclasses.replace(
        design,
        board=trimmed,
        rules=dataclasses.replace(
            rules, rules=tuple(rule for rule in rules.rules if rule.name not in names) + tuple(plan.rules)
        ),
    )
    issues: list[Issue] = []
    after = generate_mod.resolve_generated(
        staged,
        tuple(plan.records),
        unplaced=unplaced,
        issues=issues,
        keepouts=keepouts,
        outline=outline,
        edge_floor=edge_floor,
    )
    after_board = after.board
    assert after_board is not None
    # the resolution marks every rule area, text, graphic and dimension of the design with a build's uuid;
    # the items the design held keep theirs (a board read from a file must stay as it was)
    restored: dict[str, tuple[object, ...]] = {}
    for name in ("keepouts", "texts", "graphics", "dimensions"):
        held = {item.id: item for item in getattr(trimmed, name)}
        restored[name] = tuple(held.get(item.id, item) for item in getattr(after_board, name))
    return dataclasses.replace(after, board=dataclasses.replace(after_board, **restored)), issues  # type: ignore[arg-type]


__all__ = ["Apply", "RoleCopperOutcomeLike", "RoleCopperPlanLike", "RoleCopperPlanner", "apply_plan"]
