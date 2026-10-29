# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Role copper on the reference boards, the acceptance gate of change c0243 (capability net-roles, "Role
copper on the reference boards", scenario "Copper findings cleared"; hypotheses ``H-G-ROLE-COPPER-CLEAN``,
``-REPAIR`` and ``-SW``).

Each ``<variant>_roles.py`` script leaves out the power, switch-node, ground and high-voltage copper of its
variant and calls ``design.role_copper()``. Its KiCad build is judged as the c0222 reference tests judge the
variants (every inferred role and group confirmed, the board's requirements file), on the simulated pour of
its new zones. The ``good`` scripts give no finding of warning or above; the ``bad`` scripts lose every
copper finding and keep exactly the routing findings of their ``bad`` variant.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from _roleboards import BOARDS, EXAMPLES, VARIANTS, Built
from _rolecheck import checked, loops
from _rolecheck import findings as variant_findings
from _rolecopper import board, cli, findings, judged, outcome

from fenolite.geometry.polygon import area2
from fenolite.roles.profile import MM2

COPPER_CODES = {
    "roles.width-current",
    "roles.section-current",
    "roles.via-current",
    "roles.return-gap",
    "roles.near-switching",
}
"""The findings that role copper answers."""
ROUTING_CODES = {"roles.kelvin-outer", "roles.kelvin-shared", "roles.gate-return-shared", "roles.gate-loop"}
"""The findings of the routes that phase 1 keeps as they are (the user's, and phase 2's)."""
CASES = [(name, variant) for name in BOARDS for variant in VARIANTS]


@pytest.mark.parametrize(("name", "variant"), CASES)
def test_build(role_copper: Callable[..., Built], name: str, variant: str) -> None:
    """Task 5.1: each script builds; its planner writes role zones and refuses nothing."""
    built = role_copper(name, variant)
    done = outcome(built)
    assert not [i for i in done.issues if i.severity == "error"], [i.code for i in done.issues]
    held = board(built)
    assert held.design.board is not None
    assert any(zone.name.startswith("role.") and zone.locked for zone in held.design.board.zones)


@pytest.mark.parametrize("name", BOARDS)
def test_good(role_copper: Callable[..., Built], name: str) -> None:
    """``H-G-ROLE-COPPER-CLEAN``: no role finding of warning or above on a ``good_roles`` board."""
    assert findings(judged(role_copper(name, "good"), name)) == set()


@pytest.mark.parametrize("name", BOARDS)
def test_bad(role_copper: Callable[..., Built], reference: Callable[..., Built], name: str) -> None:
    """``H-G-ROLE-COPPER-REPAIR``: the copper findings are gone, the routing findings are the ``bad``
    variant's (code, severity, subject)."""
    found = findings(judged(role_copper(name, "bad"), name))
    assert not {f for f in found if f[0] in COPPER_CODES}, found
    designed = {f for f in variant_findings(checked(reference, name, "bad")) if f[0] in ROUTING_CODES}
    assert found == designed  # nothing else either: the bad buck's hot loop is drawn small enough


def test_bad_buck_hot_loop(role_copper: Callable[..., Built]) -> None:
    """The bad buck's hot loop, drawn by the planner, at or under 2000 per-mille of its placement bound."""
    hot = loops(judged(role_copper("buck_shunt", "bad"), "buck_shunt"))["hot_SW"]
    ratio, bound = hot["ratio_permille"], hot["bound_nm2"]
    assert isinstance(ratio, int) and ratio <= 2000
    assert isinstance(bound, int) and 40 * MM2 <= bound <= 50 * MM2  # measured 46.1 mm² on 2026-10-29


def _switch_area(built: Built) -> int:
    held = board(built)
    assert held.design.board is not None
    names = {net.id: net.name for net in held.design.circuit.nets}
    return sum(
        abs(area2(zone.outline)) // 2
        for zone in held.design.board.zones
        if names.get(zone.net_id or "") == "SW" and len(zone.outline) >= 3
    )


@pytest.mark.parametrize("name", ["buck_shunt", "half_bridge"])
def test_switch_node(role_copper: Callable[..., Built], reference: Callable[..., Built], name: str) -> None:
    """``H-G-ROLE-COPPER-SW``: the generated switch node is no larger than the hand-drawn pour of the good
    variant, and nothing comes near it."""
    generated = _switch_area(role_copper(name, "good"))
    drawn = _switch_area(reference(name, "good"))
    assert 0 < generated <= drawn, (generated, drawn)
    for variant in VARIANTS:
        found = findings(judged(role_copper(name, variant), name))
        assert not [f for f in found if f[0] == "roles.near-switching"]


@pytest.mark.parametrize("name", BOARDS)
def test_copper_on_the_good_variant(reference: Callable[..., Built], tmp_path: Path, name: str) -> None:
    """``fenolite copper`` on an unchanged ``good`` variant whose roles are all confirmed plans nothing: each
    net with the user's copper is ``user-copper``, each other one lacks a current, and no file is planned."""
    out = tmp_path / "out"
    shutil.copytree(reference(name, "good").out, out)
    code, envelope = cli("roles", str(out), "--accept-all", "--dry-run")
    assert code == 0, envelope
    code, envelope = cli(
        "roles", str(out), "--accept-all", "--confirm", "--plan", envelope["result"]["plan_id"]
    )
    assert code == 0, envelope
    requirements = EXAMPLES / name / "requirements.toml"
    extra = ["--requirements", str(requirements)] if requirements.is_file() else []
    code, envelope = cli("copper", str(out), "--dry-run", *extra)
    assert code == 0, envelope
    result = envelope["result"]
    assert not result["changed"] and not result.get("plan_id")
    assert not result["corridors"]
    skipped = {row["net"]: row["skipped"] for row in result["nets"]}
    assert set(skipped.values()) <= {"user-copper", "current-missing"}, skipped
    assert "user-copper" in skipped.values()
    assert not [i for i in envelope["issues"] if i["severity"] == "error"]
