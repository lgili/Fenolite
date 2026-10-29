# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The reference variants checked as the tests check them (change c0222): what each board's scripts declare,
the inferred roles and groups confirmed, and the board's requirements file."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path

from _boards import EXAMPLES, Built, judge

from fenolite.analysis.requirements import load_requirements
from fenolite.model.rules import NetRole, RoleLimit, RoleSet
from fenolite.roles.judge import Judged
from fenolite.roles.measure import Inputs

AMP20 = 20_000
DECLARED: Mapping[str, RoleSet] = {
    "buck_shunt": RoleSet(
        nets=(
            NetRole("VIN", "power", "declared", milliamps=1000),
            NetRole("SW", "switch_node", "declared", milliamps=2000),
            NetRole("VL", "power", "declared", milliamps=2000),
            NetRole("VOUT", "power", "declared", milliamps=2000),
        )
    ),
    "half_bridge": RoleSet(
        nets=(NetRole("VBUS", "power", "declared", milliamps=AMP20, working_mv=400_000),),
        limits=(RoleLimit("milliamps_per_via", 4000, net="VBUS"),),
    ),
    "bms": RoleSet(
        nets=(
            *(NetRole(net, "power", "declared", milliamps=AMP20) for net in ("BAT_P", "PACK_N", "SHUNT_N")),
            NetRole("GND", "ground", "declared", milliamps=AMP20),
            *(NetRole(f"TAP{k}", "signal", "declared", sensitive=True) for k in range(4)),
        )
    ),
}
"""What each board's scripts declare."""


def confirmed(judged: Judged) -> RoleSet:
    """The resolved roles and groups of a run, as the user confirms them all."""
    roles = judged.resolved.roles
    return RoleSet(
        nets=tuple(replace(role, source="confirmed", milliamps=None) for role in roles.nets),
        loops=tuple(replace(group, origin="confirmed") for group in roles.loops),
        kelvins=tuple(replace(group, origin="confirmed") for group in roles.kelvins),
        gates=tuple(replace(group, origin="confirmed") for group in roles.gates),
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
        found = judge(built, declared=DECLARED[board], check=False)
        _RUNS[key] = judge(built, declared=DECLARED[board], stored=confirmed(found), inputs=inputs(board))
    return _RUNS[key]


def findings(judged: Judged) -> set[tuple[str, str, str]]:
    return {(i.code, i.severity, i.where) for i in judged.issues if i.severity in ("warning", "error")}


def loops(judged: Judged) -> dict[str, Mapping[str, object]]:
    return {m.subject: m.values for m in judged.measured.measures if m.kind == "loop"}
