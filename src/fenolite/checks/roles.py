# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The stage ``roles.rules``: the net roles of a board judged against its copper (change c0222; capability
verification-loop, "Roles stage" and "Roles judge injected into the stage"; ``docs/roles.md``).

``checks`` imports neither ``roles`` nor ``analysis``: ``fenolite check`` passes the judge, a ``RolesJudge``
(``fenolite.roles.judge.judge``), as it passes the plotter and the fill oracle. The stage runs no tool. It is
skipped with ``no-roles`` when the board has no stored or declared role (no ``RuleSet.roles`` in the
``.fenolite/`` model of a built project, and no role document beside the board), so a board without roles
keeps its result, and with ``not-judged`` when no judge is given. A role document that cannot be read is
``check.roles-unreadable``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from typing import Protocol

from fenolite.backends.base import BoardFrame, BoardPad, ProjectSet
from fenolite.checks.codes import issue
from fenolite.checks.stages import StageResult, ran, skipped
from fenolite.checks.subjects import for_issues
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.model.design import Design

NAME = "roles.rules"
DOCUMENT_SUFFIX = ".roles.json"
"""The suffix of the role document beside a board (``fenolite.roles.store.SUFFIX``, which ``checks`` does
not import; a test keeps the two equal)."""


class RolesJudge(Protocol):
    """Judges the roles of a board: from the board model, the ``.fenolite/`` model (``None`` for a board that
    Fenolite did not build), the project and the board-frame pads, to the issues, the summary and the
    evidence. ``FormatError`` for a role document that cannot be read."""

    def __call__(
        self, design: Design, model: Design | None, project: ProjectSet, pads: Sequence[BoardPad] | None
    ) -> tuple[tuple[Issue, ...], Mapping[str, object], Evidence]: ...


def has_roles(model: Design | None, project: ProjectSet) -> bool:
    """Whether the board has stored or declared roles: ``RuleSet.roles`` of the ``.fenolite/`` model, or the
    role document beside the board."""
    if model is not None and model.rules is not None and model.rules.roles:
        return True
    board = project.root / project.board
    return board.with_name(board.stem + DOCUMENT_SUFFIX).is_file()


def roles_stage(
    design: Design,
    *,
    model: Design | None,
    project: ProjectSet,
    frame: BoardFrame | None,
    judge: RolesJudge | None,
) -> StageResult:
    """The stage on the board ``design`` of ``project``."""
    if judge is None:
        return skipped(NAME, "not-judged")
    if not has_roles(model, project):
        return skipped(NAME, "no-roles")
    pad_issues: list[Issue] = []
    pads = tuple(frame.board_pads(design, issues=pad_issues)) if frame is not None else None
    try:
        issues, summary, evidence = judge(design, model, project, pads)
    except FormatError as error:
        where = ":".join(part for part in (error.file, error.locator) if part)
        found = issue("check.roles-unreadable", f"the roles cannot be read: {error.message}", where=where)
        return ran(NAME, [found], Evidence(), {})
    result = ran(NAME, (*pad_issues, *issues), evidence, summary)
    return dataclasses.replace(result, subjects=for_issues(design, result.issues))


__all__ = ["DOCUMENT_SUFFIX", "NAME", "RolesJudge", "has_roles", "roles_stage"]
