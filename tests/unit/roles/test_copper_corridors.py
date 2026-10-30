# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Corridors of the critical routes (change c0243, decision 8, the interface with c0244 decided by the
maintainer on 2026-10-29; capability net-roles, "Corridors for critical routes" and "Phase 2 copper
kept")."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from _roleboards import Built
from _rolecopper import board, build_role, outcome, variant

from fenolite.geometry import Location, point_in_ring
from fenolite.roles.copper import with_simulated_fills

GOOD = (
    'design = make(Design("half_bridge_kept"), "good", power=False)\n'
    'gnd = design.nets["GND"]\n'
    'design.net_role(gnd, "ground")\n'
    'design.net_role(design.nets["SRC"], "power", current=amp(5))\n'
    'design.net_role(design.nets["SW"], "switch_node", current=amp(5))\n'
    "design.role_limits(net=gnd, milliamps_per_via=amp(4))\n"
    "{extra}"
    'design.role_copper(requirements="requirements.toml")'
)
PHASE_2 = (
    'design.rule_area("role.corridor.gate_Q1.GH", ((mm("29.6"), mm("10.4")), (mm("38.6"), mm("10.4")), '
    '(mm("38.6"), mm("11.6")), (mm("29.6"), mm("11.6"))), layers=("F.Cu",), forbid=("pours",))\n'
)


def _overlap(a: tuple[object, ...], b: tuple[object, ...]) -> bool:
    return any(point_in_ring(p, b) is Location.INSIDE for p in a) or any(  # type: ignore[arg-type]
        point_in_ring(p, a) is Location.INSIDE  # type: ignore[arg-type]
        for p in b
    )


def _no_pour_enters(built: Built) -> None:
    held = board(built)
    filled = with_simulated_fills(held.design, held.pads)
    assert filled.board is not None
    corridors = [k for k in filled.board.keepouts if k.name.startswith("role.corridor.")]
    assert corridors
    for zone in filled.board.zones:
        if not zone.name.startswith("role."):
            continue
        for fill in zone.fills:
            for area in corridors:
                if fill.layer in area.layers:
                    assert not _overlap(fill.polygon, area.outline), (zone.name, area.name)


def test_corridors_keep_pours_out(role_copper: Callable[..., Built]) -> None:
    built = role_copper("half_bridge", "good")
    found = outcome(built).plan.corridors
    keys = {(c.group, c.net) for c in found}
    # the gate returns (SW, GND) have copper roles of their own: their copper is planned, not kept clear
    assert keys == {("gate_Q1", "GH"), ("gate_Q2", "GL"), ("kelvin_R1", "SRC"), ("kelvin_R1", "GND")}
    assert all(c.origin == "provisional" and c.key.startswith("role.corridor.") for c in found)
    held = board(built)
    assert held.design.board is not None
    names = {k.name for k in held.design.board.keepouts}
    for corridor in found:
        assert corridor.key in names
    _no_pour_enters(built)


def test_kept(tmp_path: Path) -> None:
    """Scenario "Phase 2's corridors are kept": an area ``role.corridor.gate_Q1.GH`` that the run did not
    write stays as it is and no provisional corridor is written for that net."""
    script = variant(tmp_path, "half_bridge", GOOD.format(extra=PHASE_2))
    built = build_role(script, tmp_path / "out")
    held = board(built)
    assert held.design.board is not None
    areas = [k for k in held.design.board.keepouts if k.name.startswith("role.corridor.gate_Q1.GH")]
    assert [k.name for k in areas] == ["role.corridor.gate_Q1.GH"]
    assert len(areas[0].outline) == 4 and areas[0].no_copper_pour and not areas[0].no_tracks
    (found,) = [c for c in outcome(built).plan.corridors if (c.group, c.net) == ("gate_Q1", "GH")]
    assert found.origin == "found" and not found.pieces
    _no_pour_enters(built)
