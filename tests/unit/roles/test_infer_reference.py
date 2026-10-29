# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The inferred roles of the six reference variants against their expected tables (change c0222; capability
net-roles, "One role per net" and "Groups of the half-bridge"; hypothesis ``H-G-ROLE-INFER``).

Each variant is built for KiCad and its roles are inferred from the circuit of its ``.fenolite/`` model and
the pads of its board, with nothing confirmed or declared.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _boards import BOARDS, VARIANTS, build, read

from fenolite.model.canonical import load_dir
from fenolite.roles import ROLE_KINDS
from fenolite.roles.judge import Resolved, net_tie_parts, resolve

_BUCK = {
    "GH": ("gate", "GD-1", "high"),
    "GL": ("gate", "GD-1", "high"),
    "GND": ("ground", "GND-1", "high"),
    "ISNS": ("signal", "SIG-0", "low"),
    "PWM_H": ("signal", "SIG-0", "low"),
    "PWM_L": ("signal", "SIG-0", "low"),
    "SW": ("switch_node", "SW-1", "high"),
    "VB": ("power", "PWR-1", "medium"),
    "VDRV": ("power", "PWR-1", "medium"),
    "VIN": ("power", "PWR-1", "medium"),
    "VL": ("power", "PWR-1", "medium"),
    "VOUT": ("power", "PWR-1", "medium"),
}
_BUCK_GROUPS = {
    ("HotLoop", "hot_SW"): ("C1-1", "Q1-3", "Q1-1", "Q2-3", "Q2-1", "C1-2"),
    ("GateLoop", "gate_Q1"): ("U1-7", "Q1-2", "Q1-1", "U1-6"),
    ("GateLoop", "gate_Q2"): ("U1-5", "Q2-2", "Q2-1", "U1-4"),
    ("KelvinPair", "kelvin_R12"): ("R12-1", "U3-3", "U3-4", "R12-2"),
}
_HALF = {
    "GH": ("gate", "GD-1", "high"),
    "GL": ("gate", "GD-1", "high"),
    "GND": ("ground", "GND-1", "high"),
    "ISNS": ("signal", "SIG-0", "low"),
    "PWM_H": ("signal", "SIG-0", "low"),
    "PWM_L": ("signal", "SIG-0", "low"),
    "SRC": ("power", "PWR-1", "medium"),
    "SW": ("switch_node", "SW-3", "medium"),
    "VBOOT": ("power", "PWR-1", "medium"),
    "VBUS": ("power", "PWR-1", "medium"),
    "VDRV": ("power", "PWR-1", "medium"),
}
_HALF_GROUPS = {
    ("HotLoop", "hot_SW"): ("C1-1", "Q1-4", "Q1-3", "Q2-4", "Q2-3", "R1-1", "R1-2", "C1-2"),
    ("GateLoop", "gate_Q1"): ("U2-7", "Q1-1", "Q1-2", "U2-6"),
    ("GateLoop", "gate_Q2"): ("U2-5", "Q2-1", "Q2-2", "U2-4"),
    ("KelvinPair", "kelvin_R1"): ("R1-1", "U3-3", "U3-4", "R1-2"),
}
_BMS = {
    "BAT_P": ("power", "PWR-1", "medium"),
    "CHG_G": ("gate", "GD-1", "high"),
    "DSG_G": ("gate", "GD-1", "high"),
    "FET_S": ("power", "PWR-1", "medium"),
    "GND": ("ground", "GND-1", "high"),
    "PACK_N": ("power", "PWR-1", "medium"),
    "SHUNT_N": ("power", "PWR-1", "medium"),
    "TAP0": ("signal", "SIG-0", "low"),
    "TAP1": ("signal", "SIG-0", "low"),
    "TAP2": ("signal", "SIG-0", "low"),
    "TAP3": ("signal", "SIG-0", "low"),
}
_BMS_GROUPS = {
    ("GateLoop", "gate_Q1"): ("U1-9", "Q1-1", "Q1-2", "U1-10"),
    ("GateLoop", "gate_Q2"): ("U1-11", "Q2-1", "Q2-2", "U1-10"),
    ("KelvinPair", "kelvin_R1"): ("R1-2", "U1-7", "U1-8", "R1-3"),
}
EXPECTED: dict[
    tuple[str, str], tuple[dict[str, tuple[str, str, str]], dict[tuple[str, str], tuple[str, ...]]]
] = {
    ("buck_shunt", "good"): (_BUCK, _BUCK_GROUPS),
    ("buck_shunt", "bad"): (_BUCK, _BUCK_GROUPS),
    ("half_bridge", "good"): (_HALF, _HALF_GROUPS),
    ("half_bridge", "bad"): (_HALF, _HALF_GROUPS),
    # the good variant senses the shunt on its own sense nets; the bad one on its force pads' nets
    ("bms", "good"): (
        {**_BMS, "SNS_N": ("kelvin", "KS-1", "high"), "SNS_P": ("kelvin", "KS-1", "high")},
        _BMS_GROUPS,
    ),
    ("bms", "bad"): (_BMS, _BMS_GROUPS),
}
"""Each variant: net → (kind, rule, confidence), and (group type, name) → pads."""


@pytest.fixture(scope="module")
def inferred(tmp_path_factory: pytest.TempPathFactory) -> dict[tuple[str, str], Resolved]:
    found: dict[tuple[str, str], Resolved] = {}
    for board in BOARDS:
        for variant in VARIANTS:
            out: Path = tmp_path_factory.mktemp(f"{board}_{variant}")
            built = build(board, variant, out / "out", fill=False)
            design, pads = read(built)
            model = load_dir(built.out / ".fenolite")
            found[board, variant] = resolve(model.circuit, pads=pads, net_ties=net_tie_parts(design))
    return found


def _groups(resolved: Resolved) -> dict[tuple[str, str], tuple[str, ...]]:
    roles = resolved.roles
    return {
        (type(group).__name__, group.name): group.pads
        for group in (*roles.loops, *roles.gates, *roles.kelvins)
    }


@pytest.mark.parametrize(("board", "variant"), sorted(EXPECTED))
def test_roles_match_the_table(inferred: dict[tuple[str, str], Resolved], board: str, variant: str) -> None:
    resolved = inferred[board, variant]
    nets, groups = EXPECTED[board, variant]
    got = {role.net: (role.kind, role.rule, role.confidence) for role in resolved.roles.nets}
    assert got == nets
    assert _groups(resolved) == groups
    assert all(role.source == "inferred" for role in resolved.roles.nets)
    assert [found.code for found in resolved.issues] == ["roles.unconfirmed"]


@pytest.mark.parametrize("variant", VARIANTS)
def test_one_role_per_net_of_the_buck(inferred: dict[tuple[str, str], Resolved], variant: str) -> None:
    resolved = inferred["buck_shunt", variant]
    names = [role.net for role in resolved.roles.nets]
    assert len(names) == len(set(names))
    assert all(role.kind in ROLE_KINDS for role in resolved.roles.nets)


def test_groups_of_the_half_bridge(inferred: dict[tuple[str, str], Resolved]) -> None:
    roles = inferred["half_bridge", "good"].roles
    assert [loop.pads[0] for loop in roles.loops] == ["C1-1"]
    assert {pad for loop in roles.loops for pad in loop.pads} >= {"Q1-3", "Q1-4", "Q2-3", "Q2-4"}
    # each gate loop's source is the Kelvin-source pad (pad 2 of the four-pin package)
    assert sorted(gate.source for gate in roles.gates) == ["Q1-2", "Q2-2"]
    assert [pair.element for pair in roles.kelvins] == [("R1-1", "R1-2")]


def test_low_results_are_signal(inferred: dict[tuple[str, str], Resolved]) -> None:
    for resolved in inferred.values():
        for role in resolved.roles.nets:
            if role.confidence == "low":
                assert role.kind == "signal", role


def test_force_pads_of_the_four_pad_shunt(inferred: dict[tuple[str, str], Resolved]) -> None:
    for variant in VARIANTS:
        (pair,) = inferred["bms", variant].roles.kelvins
        assert pair.force == ("R1-1", "R1-4")
