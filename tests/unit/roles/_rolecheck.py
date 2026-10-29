# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The reference variants checked as the tests check them (change c0222): the roles their scripts declare
(stored by the build in ``.fenolite/rules.json``), the inferred roles and groups confirmed, and the board's
requirements file."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path

from _roleboards import EXAMPLES, Built, judge

from fenolite.analysis.requirements import load_requirements
from fenolite.model.rules import RoleSet
from fenolite.roles.judge import Judged
from fenolite.roles.measure import Inputs


def confirmed(judged: Judged) -> RoleSet:
    """The inferred roles and groups of a run, as the user confirms them all (``--accept-all``)."""
    roles = judged.resolved.roles
    return RoleSet(
        nets=tuple(replace(role, source="confirmed") for role in roles.nets if role.source == "inferred"),
        loops=tuple(
            replace(group, origin="confirmed") for group in roles.loops if group.origin == "inferred"
        ),
        kelvins=tuple(replace(g, origin="confirmed") for g in roles.kelvins if g.origin == "inferred"),
        gates=tuple(
            replace(group, origin="confirmed") for group in roles.gates if group.origin == "inferred"
        ),
    )


def inputs(board: str) -> Inputs:
    path = EXAMPLES / board / "requirements.toml"
    if not path.is_file():
        return Inputs()
    return Inputs(requirements=load_requirements(path.read_text(encoding="utf-8"), file=path.name))


_RUNS: dict[tuple[str, str, Path], Judged] = {}


def checked(reference: Callable[..., Built], board: str, variant: str) -> Judged:
    built = reference(board, variant)
    key = (board, variant, built.out)
    if key not in _RUNS:
        found = judge(built, check=False)
        _RUNS[key] = judge(built, stored=confirmed(found), inputs=inputs(board))
    return _RUNS[key]


def findings(judged: Judged) -> set[tuple[str, str, str]]:
    return {(i.code, i.severity, i.where) for i in judged.issues if i.severity in ("warning", "error")}


def loops(judged: Judged) -> dict[str, Mapping[str, object]]:
    return {m.subject: m.values for m in judged.measured.measures if m.kind == "loop"}
