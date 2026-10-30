# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Role copper in the DSL (change c0243, decision 9; capability design-dsl, "Role copper in the DSL",
scenario "Recorded and built")."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import fenolite.dsl as dsl
from fenolite.dsl import Design, DslError, mm
from fenolite.dsl.rolecopper import RoleCopperIntent

ROLES = Path(__file__).resolve().parents[1] / "roles"


def _design(copper: int = 2) -> Design:
    design = Design("rc")
    design.board(mm(30), mm(20), copper=copper)
    return design


def test_recorded() -> None:
    design = _design(4)
    assert dsl.role_copper(design) is None
    design.role_copper(
        kinds=("power", "ground"),
        layers={"power": ("F.Cu", "B.Cu")},
        ground_layers=("In1.Cu",),
        ground_fill="all",
        connection={"ground": "solid"},
        stitch_pitch=mm(4),
        temp_rise=10,
        widen=1500,
        corridors=False,
        keep=("role.power.VIN.F.Cu",),
        requirements="requirements.toml",
    )
    found = dsl.role_copper(design)
    assert isinstance(found, RoleCopperIntent)
    assert found.kinds == ("power", "ground") and found.layers == {"power": ("F.Cu", "B.Cu")}
    assert found.ground_layers == ("In1.Cu",) and found.ground_fill == "all"
    assert found.connection == {"ground": "solid"} and found.stitch_pitch == 4_000_000
    assert found.temp_rise == 10_000 and found.widen == 1500 and not found.corridors
    assert found.keep == ("role.power.VIN.F.Cu",) and found.requirements == "requirements.toml"
    with pytest.raises(DslError, match="twice"):
        design.role_copper()


@pytest.mark.parametrize(
    ("arguments", "match"),
    [
        ({"kinds": ("motor",)}, "motor"),
        ({"connection": {"ground": "spokes"}}, "spokes"),
        ({"ground_fill": "some"}, "ground_fill"),
        ({"ground_layers": ("In1.Cu",)}, "no copper layer"),
        ({"layers": {"power": ("In3.Cu",)}}, "no copper layer"),
        ({"widen": 500}, "widen"),
        ({"temp_rise": "-1"}, "temp_rise"),
        ({"corridors": "yes"}, "corridors"),
    ],
)
def test_refused(arguments: dict[str, object], match: str) -> None:
    with pytest.raises(DslError, match=match):
        _design().role_copper(**arguments)  # type: ignore[arg-type]


def test_needs_a_board() -> None:
    with pytest.raises(DslError, match="board"):
        Design("rc").role_copper()


def test_built(tmp_path: Path) -> None:
    """The KiCad build of ``examples/roles/buck_shunt/good_roles.py`` holds locked role zones."""
    if str(ROLES) not in sys.path:
        sys.path.insert(0, str(ROLES))
    from _roleboards import EXAMPLES, read
    from _rolecopper import build_role

    built = build_role(EXAMPLES / "buck_shunt" / "good_roles.py", tmp_path / "out")
    design, _ = read(built)
    assert design.board is not None
    zones = [z for z in design.board.zones if z.name.startswith("role.")]
    assert zones and all(z.locked for z in zones)
    assert {z.name.split(".")[1] for z in zones} >= {"power", "switch_node", "ground"}
