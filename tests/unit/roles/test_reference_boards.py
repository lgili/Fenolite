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
from pathlib import Path

import pytest
from _roleboards import EXAMPLES, Built, build_script, judge
from _rolecheck import checked, findings, loops

from fenolite.model.rules import KelvinPair, NetRole, RoleSet
from fenolite.roles.profile import MM2

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


PAIR = """\
# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as a test board; no file, value, name or layout comes from any other project.
from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("kelvin_pair")
design.board(mm(40), mm(30))
r1 = Part("R1", "Fenolite:Resistor", footprint="Roles:Roles_Shunt_2512", value="5m")
u1 = Part("U1", "Roles:Roles_Sense_Amplifier", footprint="Fenolite:SOT23_5", value="AMP")
design.add(r1, u1)
connect(Net("VA"), r1[1], u1["IN+"])
connect(Net("VB"), r1[2], u1["IN-"])
r1.place(mm(15), mm(8))  # pads at (12.1, 8) and (17.9, 8)
u1.place(mm(15), mm(20))  # IN+ at (13.7, 19.05), IN- at (16.3, 19.05)
w = mm("0.25")
p = lambda x, y: (mm(str(x)), mm(str(y)))  # noqa: E731
design.track("sense_p", r1.pad(1).at(mm("0.5")), p(12.6, 12), p(13.7, 17), u1.pad(3), width=w)
{sense_n}
"""
COUPLED = 'design.track("sense_n", r1.pad(2).at(mm("-0.5")), p(17.4, 12), p(16.3, 17), u1.pad(4), width=w)'
SPLIT = (
    'design.track("sense_n", r1.pad(2).at(mm("-0.5")), p(17.4, 3), p(35, 3), p(35, 19.05), u1.pad(4), '
    "width=w)"
)

PAIR_ROLES = RoleSet(
    nets=(NetRole("VA", "power", "declared"), NetRole("VB", "power", "declared")),
    kelvins=(KelvinPair("kelvin_R1", ("R1-1", "R1-2"), ("U1-3", "U1-4"), origin="declared"),),
)


@pytest.mark.parametrize(("sense_n", "apart"), [(COUPLED, False), (SPLIT, True)])
def test_kelvin_pair_split(tmp_path: Path, sense_n: str, apart: bool) -> None:
    """``H-G-ROLE-KELVIN-PAIR`` on an authored pair: the coupled pair at or under 2000 ‰, the split one over
    it (no reference variant has a split pair)."""
    for name in ("sym-lib-table", "fp-lib-table"):
        text = (EXAMPLES / "buck_shunt" / name).read_text(encoding="utf-8")
        libs = (EXAMPLES.parents[1] / "tests" / "data" / "libs").as_posix()
        (tmp_path / name).write_text(
            text.replace("${KIPRJMOD}/../../../tests/data/libs", libs), encoding="utf-8"
        )
    script = tmp_path / "pair.py"
    script.write_text(PAIR.format(sense_n=sense_n), encoding="utf-8")
    judged = judge(build_script(script, tmp_path / "out"), declared=PAIR_ROLES)
    (pair,) = loops(judged).values()
    ratio = pair["ratio_permille"]
    assert isinstance(ratio, int) and (ratio > 2000) == apart, ratio
    found = [i for i in judged.issues if i.code == "roles.kelvin-apart"]
    assert len(found) == int(apart)
    if apart:
        assert (
            found[0].severity == "warning"
            and "pair_ratio_max=2000 (profile, H-G-ROLE-KELVIN-PAIR)" in found[0].message
        )
    assert not [i for i in judged.issues if i.code in ("roles.kelvin-outer", "roles.kelvin-shared")]
