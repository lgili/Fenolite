# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact native PCB spelling owns generated class patterns, not guessed slash rewrites (c0352)."""

from __future__ import annotations

import dataclasses

import pytest
from _prodesigns import design

from fenolite.backends.kicad import pro
from fenolite.backends.kicad.copperrules import design_rules_from_texts
from fenolite.backends.kicad.pcb import stored_net_name
from fenolite.core.errors import ConsistencyError
from fenolite.core.ids import derived_id


def test_generated_patterns_and_planner_class_resolution_follow_exact_board_names() -> None:
    made = design({"HV": 203_200}, {"/12Vext": "HV", "GND": None})
    project = pro.synthesize_project(made, target=9, board_name="own")
    data = pro.read_project_text(project)
    assert data["net_settings"]["netclass_patterns"] == [{"netclass": "HV", "pattern": "{slash}12Vext"}]
    applied = pro.apply_project(made, pro.read_project(project))
    classes = {cls.id: cls.name for cls in applied.circuit.netclasses}
    assert classes[next(net.netclass_id for net in applied.circuit.nets if net.name == "/12Vext")] == "HV"
    planned = design_rules_from_texts(made, project_text=project, rules_text=None, major=9)
    assert {n.name: classes.get(n.netclass_id) for n in planned.design.circuit.nets}["/12Vext"] == "HV"


def test_read_native_raw_spelling_is_preserved_and_user_patterns_are_untouched() -> None:
    made = design({"HV": 203_200}, {"/12Vext": "HV"})
    net = made.circuit.nets[0]
    read_net = dataclasses.replace(net, id=derived_id("net", "kicad", f"net:{net.name}"))
    native_read = dataclasses.replace(made, circuit=dataclasses.replace(made.circuit, nets=(read_net,)))
    assert stored_net_name(read_net) == "/12Vext"
    assert pro.read_project_text(pro.synthesize_project(native_read, target=9, board_name="own"))[
        "net_settings"
    ]["netclass_patterns"] == [{"netclass": "HV", "pattern": "/12Vext"}]
    baseline = pro.template(9)
    users = [{"netclass": "HV", "pattern": "USER/*"}, {"netclass": "HV", "pattern": "^USER[0-9]+$"}]
    baseline["net_settings"]["netclass_patterns"] = [{"netclass": "HV", "pattern": "/12Vext"}, *users]
    result = pro.read_project_text(pro.update_project(pro.write_project_text(baseline), made, target=9))
    assert result["net_settings"]["netclass_patterns"] == [
        {"netclass": "HV", "pattern": "{slash}12Vext"},
        *users,
    ]


def test_native_name_collision_refuses_instead_of_clobbering_even_same_class() -> None:
    made = design({"HV": 203_200}, {"/12Vext": "HV", "{slash}12Vext": "HV"})
    with pytest.raises(ConsistencyError, match="stored.*name|native.*name"):
        pro.synthesize_project(made, target=9, board_name="own")
