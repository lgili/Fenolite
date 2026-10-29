# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Helpers of the critical-route tests (change c0244): authored benches built like the reference boards, the
roles of a build with its inferred groups confirmed, and its critical plan."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

from _roleboards import EXAMPLES, Built, build_script, judge
from _rolecheck import confirmed

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import read_board
from fenolite.cli import cmd_route
from fenolite.cli._roleroute import job_nets, job_route, pair_clearance
from fenolite.model.design import Design
from fenolite.model.rules import RoleSet
from fenolite.roles.routes import CriticalPlan, plan_critical
from fenolite.routing.octilinear import OctilinearRouter
from fenolite.routing.protocol import RoutingJob, RoutingResult

HEADER = """\
# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as a test board; no file, value, name or layout comes from any other project.
"""


def bench(tmp: Path, name: str, body: str) -> Built:
    """Build the authored script ``body`` (after the CC0 header) as ``<name>.py`` in ``tmp``, with the
    library tables of the reference boards."""
    for table in ("sym-lib-table", "fp-lib-table"):
        text = (EXAMPLES / "buck_shunt" / table).read_text(encoding="utf-8")
        libs = (EXAMPLES.parents[1] / "tests" / "data" / "libs").as_posix()
        (tmp / table).write_text(text.replace("${KIPRJMOD}/../../../tests/data/libs", libs), encoding="utf-8")
    script = tmp / f"{name}.py"
    script.write_text(HEADER + body, encoding="utf-8")
    return build_script(script, tmp / f"{name}_out")


def board(built: Built) -> tuple[Design, tuple[BoardPad, ...]]:
    """The board of a build with its project's classes and rules, as ``fenolite route`` reads it, and its
    pads in the board frame."""
    design = read_board(built.board.read_text(encoding="utf-8"), file=built.board.name)
    rules = cmd_route._project_rules(design, built.board, [])  # pyright: ignore[reportPrivateUsage]
    return rules.design, tuple(board_pads(rules.design, issues=[]))


def roles_of(built: Built, *, accept: bool = True) -> RoleSet:
    """The roles in force on a build: its declared ones, and its inferred ones confirmed when ``accept``."""
    found = judge(built, check=False)
    if not accept:
        return found.resolved.roles
    return judge(built, stored=confirmed(found), check=False).resolved.roles


def plan(built: Built, *, groups: Sequence[str] = (), roles: RoleSet | None = None) -> CriticalPlan:
    design, pads = board(built)
    rules = cmd_route._project_rules(  # pyright: ignore[reportPrivateUsage]
        read_board(built.board.read_text(encoding="utf-8"), file=built.board.name), built.board, []
    )
    checks = cmd_route._job_checks(design, rules)  # pyright: ignore[reportPrivateUsage]
    layers = tuple(
        layer.name
        for layer in sorted(design.board.layers if design.board else (), key=lambda item: item.ordinal)
        if layer.kind == "copper"
    )
    return plan_critical(
        design,
        roles if roles is not None else roles_of(built),
        pads,
        layers=layers,
        clearance=pair_clearance(checks["clearance"], design),  # type: ignore[arg-type]
        default_width=cmd_route.DEFAULTS[0],
        groups=groups,
    )


def unconfirmed(roles: RoleSet) -> RoleSet:
    """``roles`` with every group made ``inferred`` again."""
    return replace(
        roles,
        gates=tuple(replace(g, origin="inferred") for g in roles.gates),
        kelvins=tuple(replace(k, origin="inferred") for k in roles.kelvins),
    )


def role_job(
    built: Built,
    *,
    options: Mapping[str, str] | None = None,
    role_check: object | None = None,
    groups: Sequence[str] = (),
) -> RoutingJob:
    """The routing job that ``fenolite route --roles critical`` gives the router for a build whose groups are
    declared or confirmed, with the copper check and clearance of the project (and ``role_check`` when
    given)."""
    design, pads = board(built)
    found = plan(built, groups=groups)
    rules = cmd_route._project_rules(  # pyright: ignore[reportPrivateUsage]
        read_board(built.board.read_text(encoding="utf-8"), file=built.board.name), built.board, []
    )
    checks = cmd_route._job_checks(design, rules)  # pyright: ignore[reportPrivateUsage]
    extra: dict[str, object] = {"board_pads": pads, "outline": board_outline(design).rings, **checks}
    if role_check is not None:
        extra["role_check"] = role_check
    layers = tuple(
        layer.name
        for layer in sorted(design.board.layers if design.board else (), key=lambda item: item.ordinal)
        if layer.kind == "copper"
    )
    return RoutingJob(
        design,
        job_nets(design, pads, found.routes, cmd_route.DEFAULTS),
        layers,
        dict(options or {}),
        extra,
        roles=tuple(job_route(route) for route in found.routes),
    )


def route_job(built: Built, **given: object) -> RoutingResult:
    """The result of the octilinear router on ``role_job(built, **given)``."""
    return OctilinearRouter().route(role_job(built, **given))  # type: ignore[arg-type]
