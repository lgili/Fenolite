# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The whole role check on the six reference variants (change c0222; capability net-roles, "Reference boards",
"Hot and gate loop checks", "Kelvin pair and switching distance"; hypotheses ``H-G-ROLE-LOOP-RATIO``,
``H-G-ROLE-KELVIN-PAIR`` and ``H-G-ROLE-NEAR-SW``).

Each variant is built for KiCad, its inferred roles and groups are confirmed, and the roles that its script
declares (currents, the bus's working voltage and via limit, the sensitive cell taps) are added. The ``good``
variants give no finding of warning or above; the ``bad`` variants give exactly their designed findings.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path

import pytest
from _boards import EXAMPLES, Built, judge

from fenolite.analysis.requirements import load_requirements
from fenolite.model.rules import NetRole, RoleLimit, RoleSet
from fenolite.roles.judge import Judged
from fenolite.roles.measure import Inputs
from fenolite.roles.profile import MM2

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
EXPECTED: Mapping[tuple[str, str], set[tuple[str, str, str]]] = {
    ("buck_shunt", "good"): set(),
    ("buck_shunt", "bad"): {
        ("roles.loop-area", "warning", "hot_SW"),
        ("roles.width-current", "warning", "/kicad_pcb/segment[60]"),
        ("roles.kelvin-outer", "error", "kelvin_R12:R12-1"),
        ("roles.kelvin-shared", "error", "kelvin_R12:R12-2"),
    },
    ("half_bridge", "good"): set(),
    ("half_bridge", "bad"): {
        ("roles.gate-loop", "warning", "gate_Q2"),
        ("roles.gate-return-shared", "error", "gate_Q1"),
        ("roles.near-switching", "warning", "kelvin_R1~SW"),
        ("roles.via-current", "error", "/kicad_pcb/via[9]"),
    },
    ("bms", "good"): set(),
    ("bms", "bad"): {
        ("roles.width-current", "warning", "/kicad_pcb/segment[21]"),
        ("roles.return-gap", "warning", "TAP0@/kicad_pcb/segment[27]"),
        ("roles.kelvin-shared", "error", "kelvin_R1:R1-2"),
        ("roles.kelvin-shared", "error", "kelvin_R1:R1-3"),
    },
}
"""The findings of warning or above of each variant: (code, severity, where)."""
CASES = sorted(EXPECTED)


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


@pytest.mark.parametrize(("board", "variant"), CASES)
def test_good_and_bad_variants(reference: Callable[..., Built], board: str, variant: str) -> None:
    judged = checked(reference, board, variant)
    assert findings(judged) == EXPECTED[board, variant]
    assert not [i for i in judged.issues if i.code == "roles.unconfirmed"]
    assert judged.evidence.level.value == "INFERRED"


def test_buck_loop(reference: Callable[..., Built]) -> None:
    """The bad buck's hot loop: an area within 10 % of 180 mm² and a ratio over 2000."""
    judged = checked(reference, "buck_shunt", "bad")
    hot = loops(judged)["hot_SW"]
    area = hot["area_nm2"]
    assert isinstance(area, int) and abs(area - 180 * MM2) <= 18 * MM2
    assert isinstance(hot["ratio_permille"], int) and hot["ratio_permille"] > 2000
    (found,) = [i for i in judged.issues if i.code == "roles.loop-area"]
    assert found.where == "hot_SW" and "loop_ratio_max=2000 (profile, H-G-ROLE-LOOP-RATIO)" in found.message


GOOD_LOOP_MAX = 2000
BAD_LOOPS = {("buck_shunt", "hot_SW"), ("half_bridge", "gate_Q2")}


@pytest.mark.parametrize("board", ["buck_shunt", "half_bridge", "bms"])
def test_loop_ratios(reference: Callable[..., Built], board: str) -> None:
    """``H-G-ROLE-LOOP-RATIO``: every good hot and gate loop at or under 2000 ‰ (or under the floor), every
    designed bad loop over it."""
    for variant in ("good", "bad"):
        for name, values in loops(checked(reference, board, variant)).items():
            if values["group"] == "kelvin":
                continue
            ratio = values["ratio_permille"]
            if variant == "bad" and (board, name) in BAD_LOOPS:
                assert isinstance(ratio, int) and ratio > GOOD_LOOP_MAX, (board, variant, name, ratio)
            else:
                assert ratio is None or (isinstance(ratio, int) and ratio <= GOOD_LOOP_MAX), (
                    board,
                    name,
                    ratio,
                )


@pytest.mark.parametrize("board", ["buck_shunt", "half_bridge", "bms"])
def test_kelvin_pairs(reference: Callable[..., Built], board: str) -> None:
    """``H-G-ROLE-KELVIN-PAIR``: the sense pairs of all variants are coupled (at or under 2000 ‰)."""
    for variant in ("good", "bad"):
        for name, values in loops(checked(reference, board, variant)).items():
            if values["group"] == "kelvin":
                ratio = values["ratio_permille"]
                assert isinstance(ratio, int) and ratio <= GOOD_LOOP_MAX, (board, variant, name, ratio)


def test_switching(reference: Callable[..., Built]) -> None:
    """``H-G-ROLE-NEAR-SW``: exactly the designed crossing of the half-bridge's sense pair, with its overlap
    length, and nothing on the good variants."""
    for board in ("buck_shunt", "half_bridge", "bms"):
        judged = checked(reference, board, "good")
        assert not [i for i in judged.issues if i.code == "roles.near-switching"], board
    judged = checked(reference, "half_bridge", "bad")
    (found,) = [i for i in judged.issues if i.code == "roles.near-switching"]
    assert found.where == "kelvin_R1~SW"
    assert "kelvin copper kelvin_R1 runs near the switch node SW" in found.message
    assert "4.256 mm over its fill on a neighbouring layer" in found.message
    near = [m.values for m in judged.measured.measures if m.kind == "near" and m.values["over_fill"]]
    assert {values["layer"] for values in near} == {"F.Cu"} and len(near) == 2
