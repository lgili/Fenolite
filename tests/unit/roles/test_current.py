# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The current checks of role copper on ``analyze_power`` and ``analyze_necks``, by both methods (change
c0222; capability net-roles, "Current capacity of role copper": "A thin track on a 2 A net", "No analysis
finding from the profile"; hypothesis ``H-G-ROLE-CURRENT``).

The authored board carries the 2 A net ``VOUT`` from the terminal ``J1`` on a pour of ``F.Cu``, through one
track and one via, to a pour of ``B.Cu`` and the terminal ``J2``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _roleboards import build_script, judge

from fenolite.core.errors import Issue
from fenolite.model.rules import NetRole, RoleSet
from fenolite.roles.judge import Judged
from fenolite.roles.measure import Inputs

SCRIPT = """\\
# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as a test board; no file, value, name or layout comes from any other project.
from fenolite.dsl import Design, Net, Part, connect, mm, via_step

design = Design("thin_track")
design.board(mm(30), mm(20))
j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="IN")
j2 = Part("J2", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="OUT")
design.add(j1, j2)
vout = Net("VOUT")
connect(vout, j1[1], j2[1])
j1.place(mm(5), mm(10))  # pin 1 at (5, 11.27), pin 2 (unused) at (5, 8.73)
j2.place(mm(25), mm(10))
p = lambda x, y: (mm(str(x)), mm(str(y)))  # noqa: E731
design.zone(vout, layers=("F.Cu",), name="IN", outline=tuple(p(x, y) for x, y in {pour}))
design.zone(vout, layers=("B.Cu",), name="OUT", outline=(p(14, 10.1), p(28.5, 10.1), p(28.5, 17), p(14, 17)))
via = via_step(*p(15, 14), to="B.Cu", diameter=mm(1), drill=mm("0.6"))
design.track("neck", p(11, 14), via, p(16, 14), width=mm("{width}"), net=vout)
"""
POUR = ((1.5, 10.1), (12, 10.1), (12, 17), (1.5, 17))
NECKED = ((1.5, 10.1), (7, 10.1), (7, 13.75), (9, 13.75), (9, 10.1), (12, 10.1), (12, 17), (9, 17),
          (9, 14.25), (7, 14.25), (7, 17), (1.5, 17))  # fmt: skip
"""The input pour whole, and cut to a 0.5 mm bridge between the terminal and the track."""
ROLES = RoleSet(nets=(NetRole("VOUT", "power", "declared", milliamps=2000),))
FIT = Inputs(temp_rise_mk=10_000, copper_thickness={"*": 35_000}, via_plating=25_000)


def _check(tmp_path: Path, width: str, inputs: Inputs | None = None, pour: object = POUR) -> Judged:
    script = tmp_path / "board.py"
    script.write_text(SCRIPT.format(width=width, pour=pour), encoding="utf-8")
    return judge(build_script(script, tmp_path / "out"), declared=ROLES, inputs=inputs)


def _codes(judged: Judged, prefix: str) -> list[Issue]:
    return [found for found in judged.issues if found.code.startswith(prefix)]


def test_a_thin_track_on_a_2a_net_by_the_rule_of_thumb(tmp_path: Path) -> None:
    judged = _check(tmp_path, "0.3")
    (width,) = [i for i in judged.issues if i.code == "roles.width-current"]
    assert "0.3 mm wide, below the 0.762 mm that the rule of thumb asks for 2000 mA" in width.message
    assert "width_per_amp_nm=381000 (profile, S-0851)" in width.message and width.severity == "warning"
    (via,) = [i for i in judged.issues if i.code == "roles.via-current"]
    assert "1 via(s), below the 10 vias that the rule of thumb asks for 2000 mA" in via.message
    assert "milliamps_per_via=200 (profile, S-0851)" in via.message
    assert sorted(i.code for i in _codes(judged, "roles.") if i.severity != "info") == [
        "roles.via-current",
        "roles.width-current",
    ]


def test_a_thin_track_on_a_2a_net_by_the_fit(tmp_path: Path) -> None:
    judged = _check(tmp_path, "0.3", FIT)
    (width,) = [i for i in judged.issues if i.code == "roles.width-current"]
    fit = "0.3 mm wide: it carries 999 mA at a rise of 10000 mK, below the 2000 mA by the capacity fit of "
    fit += "S-0269"
    assert fit in width.message
    assert width.severity == "error"  # the user's rise on a declared role
    assert not [i for i in judged.issues if i.code == "roles.via-current"]  # the 1 mm via carries 2 A
    paths = [m.values for m in judged.measured.measures if m.kind == "path"]
    assert {values["method"] for values in paths} == {"fit"}
    (track,) = [values for values in paths if values["element"] == "track"]
    assert isinstance(track["capacity_ma"], int) and track["capacity_ma"] < 2000


def test_a_1mm_track_passes_the_rule_of_thumb(tmp_path: Path) -> None:
    judged = _check(tmp_path, "1")
    assert not [i for i in judged.issues if i.code == "roles.width-current"]
    (via,) = [i for i in judged.issues if i.code == "roles.via-current"]
    assert "below the 10 vias" in via.message  # ceil(2000 mA / 200 mA)


def test_no_analysis_finding_from_the_profile(tmp_path: Path) -> None:
    judged = _check(tmp_path, "0.3")
    codes = {found.code for found in judged.issues}
    assert not codes & {"analysis.path-exceeded", "analysis.path-undecided", "analysis.neck-narrow"}
    assert not [found for found in judged.issues if found.code == "analysis.input-missing"]


@pytest.mark.parametrize(("milliamps", "vias"), [(200, 1), (201, 2), (2000, 10), (20_000, 100)])
def test_via_count_is_the_ceiling(tmp_path: Path, milliamps: int, vias: int) -> None:
    roles = RoleSet(nets=(NetRole("VOUT", "power", "declared", milliamps=milliamps),))
    script = tmp_path / "board.py"
    script.write_text(SCRIPT.format(width="8", pour=POUR), encoding="utf-8")
    judged = judge(build_script(script, tmp_path / "out"), declared=roles)
    (group,) = [
        m.values for m in judged.measured.measures if m.kind == "path" and m.values["element"] == "via-group"
    ]
    assert group["required_vias"] == vias


def test_a_neck_of_a_pour_is_one_finding(tmp_path: Path) -> None:
    """The 0.5 mm bridge of the input pour is the narrowest section of a fill in series on the path; the
    neck screen of ``analyze_necks`` finds the same place, and it is reported once."""
    judged = _check(tmp_path, "1", pour=NECKED)
    found = [i for i in judged.issues if i.code == "roles.section-current"]
    assert len(found) == 1 and "its narrowest section is 0.5 mm, below the 0.762 mm" in found[0].message
    necks = [m.values for m in judged.measured.measures if m.kind == "neck"]
    assert necks and all(values["zones"] for values in necks)
    assert not [i for i in judged.issues if i.code == "roles.width-current"]
