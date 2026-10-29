# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The role loops on ``loop_areas``: the placement bound, the ratio and the open legs (change c0222;
capability net-roles, "Role loops": "A rectangle and its bound", "An unrouted leg").

The authored board holds two two-pad parts whose pads stand at the corners of a 10 mm by 5 mm rectangle: the
driver ``U1`` (output and return) and the switch ``Q1`` (gate and source), with the gate net along the top
long side and the return net along the bottom one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _boards import build_script, judge

from fenolite.model.rules import GateLoop, NetRole, RoleSet
from fenolite.roles.profile import MM2

SCRIPT = """\
# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as a test board; no file, value, name or layout comes from any other project.
from fenolite.dsl import Design, Net, Part, connect, mm

FOOTPRINT = "Fenolite:C_Film_Wima_MKS2_L7.2_W2.5_P5"
design = Design("gate_rectangle")
design.board(mm(30), mm(25))
u1 = Part("U1", "Fenolite:Capacitor", footprint=FOOTPRINT, value="DRIVER")
q1 = Part("Q1", "Fenolite:Capacitor", footprint=FOOTPRINT, value="SWITCH")
design.add(u1, q1)
connect(Net("OUT"), u1[1], q1[1])
connect(Net("RET"), q1[2], u1[2])
u1.place(mm(10), mm(10), rot=270)  # pads at (10, 7.5) and (10, 12.5)
q1.place(mm(20), mm(10), rot=270)  # pads at (20, 7.5) and (20, 12.5)
{out}
{ret}
"""
STRAIGHT = 'design.track("out", u1.pad(1), q1.pad(1), width=mm("0.25"))'
DETOUR = (
    'design.track("out", u1.pad(1), (mm(10), mm("2.5")), (mm(20), mm("2.5")), q1.pad(1), width=mm("0.25"))'
)
RETURN = 'design.track("ret", q1.pad(2), u1.pad(2), width=mm("0.25"))'
ROLES = RoleSet(
    nets=(NetRole("OUT", "gate", "declared"), NetRole("RET", "signal", "declared")),
    gates=(GateLoop("gate_Q1", drive="U1-1", gate="Q1-1", source="Q1-2", ret="U1-2", origin="declared"),),
)


def _measure(tmp_path: Path, out: str, ret: str) -> tuple[dict[str, object], list[tuple[str, str, str]]]:
    script = tmp_path / "board.py"
    script.write_text(SCRIPT.format(out=out, ret=ret), encoding="utf-8")
    judged = judge(build_script(script, tmp_path / "out"), declared=ROLES)
    (loop,) = [m for m in judged.measured.measures if m.kind == "loop"]
    found = [(i.code, i.severity, i.message) for i in judged.issues if i.code.startswith("roles.")]
    return dict(loop.values), found


@pytest.mark.parametrize(("out", "area", "ratio"), [(STRAIGHT, 50, 1000), (DETOUR, 100, 2000)])
def test_a_rectangle_and_its_bound(tmp_path: Path, out: str, area: int, ratio: int) -> None:
    values, found = _measure(tmp_path, out, RETURN)
    assert values["area_nm2"] == area * MM2
    assert values["bound_nm2"] == 50 * MM2
    assert values["ratio_permille"] == ratio
    assert all(isinstance(values[key], int) for key in ("area_nm2", "bound_nm2", "ratio_permille"))
    assert [leg[2] for leg in values["legs"]] == ["copper", "straight", "copper", "straight"]  # type: ignore[union-attr]
    assert values["open"] == []
    assert not [code for code, _, _ in found if code == "roles.gate-loop"]  # 2000 is not over 2000


def test_a_ratio_over_the_limit(tmp_path: Path) -> None:
    longer = DETOUR.replace('mm("2.5")', 'mm("1.5")')
    values, found = _measure(tmp_path, longer, RETURN)
    assert values["ratio_permille"] == 2200
    (gate,) = [(level, message) for code, level, message in found if code == "roles.gate-loop"]
    assert gate[0] == "warning"  # a profile default: a warning even on a declared group
    assert "110.00 mm², 2200‰ of its placement bound of 50.00 mm²" in gate[1]
    assert "gate_ratio_max=2000 (profile, H-G-ROLE-LOOP-RATIO)" in gate[1]


def test_an_unrouted_leg(tmp_path: Path) -> None:
    values, found = _measure(tmp_path, STRAIGHT, "")
    assert values["open"] == [["Q1-2", "U1-2"]]
    codes = [code for code, _, _ in found]
    assert codes.count("roles.loop-open") == 1 and "roles.gate-loop" not in codes
    (message,) = [message for code, _, message in found if code == "roles.loop-open"]
    assert "Q1-2 to U1-2" in message
