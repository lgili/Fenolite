# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Helpers of the critical-route tests (change c0244): authored benches built like the reference boards, the
roles of a build with its inferred groups confirmed, and its critical plan."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from _roleboards import EXAMPLES, Built, build_script, judge
from _rolecheck import confirmed

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.pcb import read_board
from fenolite.cli import cmd_route
from fenolite.model.design import Design
from fenolite.model.rules import RoleSet
from fenolite.roles.routes import CriticalPlan, plan_critical

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


def class_clearance(design: Design) -> object:
    classes = {item.id: item for item in design.circuit.netclasses}
    of = {
        net.name: getattr(classes.get(net.netclass_id or ""), "clearance", None) or 0
        for net in design.circuit.nets
    }

    def clearance(a: str, b: str) -> int:
        return max(of.get(a, 0), of.get(b, 0))

    return clearance


def plan(built: Built, *, groups: Sequence[str] = (), roles: RoleSet | None = None) -> CriticalPlan:
    design, pads = board(built)
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
        clearance=class_clearance(design),  # type: ignore[arg-type]
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
