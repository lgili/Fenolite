# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored source property presentation must survive real import/build (c0345)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from _custom_fields import original

from fenolite import api
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.dsl import Part
from fenolite.dsl.errors import DslError


@pytest.mark.parametrize(
    "target,rotation,visible,styled",
    [(9, 180, False, False), (10, 270, False, False), (10, 90, True, False), (10, 180, True, True)],
)
def test_custom_pose_survives_import_and_full_proof(
    tmp_path: Path, target: int, rotation: int, visible: bool, styled: bool
):
    source = original(tmp_path / "original", rotation, target, visible=visible, styled=styled)
    args = ("import", str(source), "--to", "python", "--out", "code", "--licence", "CC0-1.0")
    planned = api.run(*args, "--dry-run", cwd=tmp_path)
    assert planned.exit_code == 0, planned.error
    confirmed = api.run(*args, "--confirm", "--plan", planned.result["plan_id"], cwd=tmp_path)
    assert confirmed.exit_code == 0, confirmed.error
    proof = api.run("verify-source", "code/design.py", "--against", str(source.parent), cwd=tmp_path)
    assert proof.exit_code == 0, proof.result.get("differences")
    assert proof.result["differences"] == [] and proof.result["accepted"] == []
    assert all(row["status"] == "equal" for row in proof.result["levels"])


def test_declared_custom_field_request_is_valid():
    part = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", properties={"Author": "CC0"})
    part.field("Author", rot=0)
    assert part.field_requests["Author"].rotation == 0


def test_agent_guide_custom_field_line():
    from _importcode import ROOT

    line = 'r1.field("MPN", visible=True, layer="fab", rot=0)'
    assert line in (ROOT / "src/fenolite/agent/skill/references/placement.md").read_text()
    r1 = Part("R1", "Mini:Mini_R", properties={"MPN": "AUTHORED-1"})
    exec(line, {"r1": r1})
    assert r1.field_requests["MPN"].visible is True
    assert r1.field_requests["MPN"].layer == "fab"
    assert r1.field_requests["MPN"].rotation == 0


def test_unhashable_field_name_is_a_dsl_error():
    part = Part("R1", "Mini:Mini_R", properties={"Author": "CC0"})
    with pytest.raises(DslError):
        part.field(["Author"], rot=0)  # type: ignore[arg-type]


@pytest.mark.parametrize("name", ["Unknown", "author", "Datasheet", "fenolite.path"])
def test_only_declared_user_field_names_are_allowed(name: str):
    part = Part("R1", "Mini:Mini_R", properties={"Author": "CC0"})
    with pytest.raises(DslError):
        part.field(name, rot=0)


@pytest.mark.parametrize("defect", ["size", "layer", "mirror", "thickness", "font"])
def test_unrepresentable_custom_pose_refuses_before_plan(tmp_path: Path, defect: str):
    source = original(tmp_path / "original", 180, 10)
    board = source.with_suffix(".kicad_pcb")
    replacements = {
        "size": ("(size 1 1)", "(size 1 2)"),
        "layer": ('(layer "F.Fab")', '(layer "User.Drawings")'),
        "mirror": ("(thickness 0.15)", "(thickness 0.15)"),
        "thickness": ("(thickness 0.15)", ""),
        "font": ("(thickness 0.15)", "(thickness 0.15) (future_style yes)"),
    }
    root = parse(board.read_text())
    (fp,) = root.nodes("footprint")
    prop = next(p for p in fp.nodes("property") if p.atoms()[0].value == "Author")
    a, b = replacements[defect]
    changed = parse(dumps(prop).replace(a, b))
    if defect == "mirror":
        effects = changed.find("effects")
        assert effects is not None
        mirrored = effects.with_children((*effects.children, parse("(justify mirror)")))
        changed = changed.with_children(tuple(mirrored if c is effects else c for c in changed.children))
    assert isinstance(changed, Node)
    fp2 = fp.with_children(tuple(changed if c is prop else c for c in fp.children))
    board.write_text(dumps(root.with_children(tuple(fp2 if c is fp else c for c in root.children))))
    before = hashlib.sha256(board.read_bytes()).hexdigest()
    reply = api.run("import", str(source), "--to", "python", "--out", "refused", "--dry-run", cwd=tmp_path)
    assert reply.exit_code == 3 and reply.error and reply.error["code"] == "FEN-3004"
    assert "R1:Author" in reply.error.get("where", "")
    assert not reply.result.get("plan") and not (tmp_path / "refused").exists()
    assert hashlib.sha256(board.read_bytes()).hexdigest() == before
