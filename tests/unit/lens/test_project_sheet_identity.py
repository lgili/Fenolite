# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0344: emitted root identities own project caches, so a native GUI cannot reset repeat refs."""

from __future__ import annotations

import json

import _drawn
import pytest

from fenolite.backends.kicad.sexpr import parse


@pytest.mark.parametrize("target", [9, 10])
@pytest.mark.parametrize("fixture", ["flat", "repeat"])
def test_project_cache_matches_actual_emitted_root(target: int, fixture: str) -> None:
    output = _drawn.build(fixture, target)
    assert not [i for i in output.issues if i.severity == "error"]
    name = _drawn.design(fixture).name
    root = parse(output.files[f"{name}.kicad_sch"].decode())
    uuid_node = root.find("uuid")
    assert uuid_node is not None
    root_uuid = uuid_node.atoms()[0].value
    project = json.loads(output.files[f"{name}.kicad_pro"])
    assert project["schematic"]["top_level_sheets"] == [
        {"filename": f"{name}.kicad_sch", "name": name, "uuid": root_uuid}
    ]
    assert [root_uuid, name] in project["sheets"]
    if fixture == "repeat":
        child = parse(output.files["sheets/channel.kicad_sch"].decode())
        resistor = next(
            s for s in child.nodes("symbol") if s.nodes("lib_id")[0].atoms()[0].value == "Mini:Mini_R"
        )
        instance_paths = resistor.nodes("instances")[0].nodes("project")[0].nodes("path")
        assert len(instance_paths) == 2
        assert all(p.atoms()[0].value.startswith(f"/{root_uuid}/") for p in instance_paths)
        assert len({p.nodes("reference")[0].atoms()[0].value for p in instance_paths}) == 2


@pytest.mark.parametrize("target", [9, 10])
def test_rebuild_binds_root_and_preserves_unmanaged_settings(target: int) -> None:
    from fenolite.dsl import placements, to_model
    from fenolite.lens.preserve import ExistingProject, prepare

    design = _drawn.design("repeat")
    initial = _drawn.build("repeat", target)
    project_file = f"{design.name}.kicad_pro"
    before = json.loads(initial.files[project_file])
    before["custom_user_settings"] = {"keep": ["authored", {"value": 17}]}
    before["schematic"]["custom_user_settings"] = "retained"
    before["schematic"]["top_level_sheets"] = [
        {"filename": "stale.kicad_sch", "name": "stale", "uuid": "stale"}
    ]
    before["sheets"] = [["stale", "stale"]]
    ready = prepare(
        to_model(design), placements(design), ExistingProject(project=json.dumps(before)), name=design.name
    )
    output = _drawn.build("repeat", target, prepared=ready)
    assert not [i for i in output.issues if i.severity == "error"]
    after = json.loads(output.files[project_file])
    expected = json.loads(initial.files[project_file])
    assert after["schematic"]["top_level_sheets"] == expected["schematic"]["top_level_sheets"]
    assert after["sheets"] == expected["sheets"]
    assert after["custom_user_settings"] == before["custom_user_settings"]
    assert after["schematic"]["custom_user_settings"] == "retained"


@pytest.mark.parametrize("target", [9, 10])
def test_skip_schematic_preserves_existing_identity_cache(target: int) -> None:
    from fenolite.backends.kicad.pro import template, write_project_text
    from fenolite.dsl import placements, to_model
    from fenolite.lens.preserve import ExistingProject, prepare

    design = _drawn.design("flat")
    before = template(target)
    before["schematic"]["top_level_sheets"] = [
        {"filename": "owned.kicad_sch", "name": "owned", "uuid": "authored"}
    ]
    before["sheets"] = [["authored", "owned"]]
    ready = prepare(
        to_model(design),
        placements(design),
        ExistingProject(project=write_project_text(before)),
        name=design.name,
    )
    output = _drawn.build("flat", target, prepared=ready, schematic="skip")
    assert not [i for i in output.issues if i.severity == "error"]
    assert not any(name.endswith(".kicad_sch") for name in output.files)
    after = json.loads(output.files[f"{design.name}.kicad_pro"])
    assert after["schematic"]["top_level_sheets"] == before["schematic"]["top_level_sheets"]
    assert after["sheets"] == before["sheets"]


def test_binder_refuses_missing_root_without_guessing_a_template_uuid() -> None:
    from fenolite.backends.kicad.pro import bind_schematic_identity

    with pytest.raises(ValueError, match="root filename"):
        bind_schematic_identity("{}", root_file="root.kicad_sch", schematics={})
    with pytest.raises(ValueError, match="one UUID"):
        bind_schematic_identity(
            "{}", root_file="root.kicad_sch", schematics={"root.kicad_sch": "(kicad_sch)"}
        )
