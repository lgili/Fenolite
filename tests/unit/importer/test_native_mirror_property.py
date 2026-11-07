# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored symmetric native mirror ownership; no copied public board material."""

from pathlib import Path

import pytest
from _native_custom import source_project

from fenolite import api
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.importer.emit.fields import requests
from fenolite.importer.vendor import library_footprint


@pytest.mark.parametrize("target", [9, 10])
@pytest.mark.parametrize("side", ["top", "bottom"])
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("visible", [False, True])
@pytest.mark.parametrize("styled", [False, True])
def test_mirror_only_pose_is_native_owned(
    tmp_path: Path, target: int, side: str, rotation: int, visible: bool, styled: bool
):
    source = source_project(tmp_path / "source", target, side, rotation, visible, styled)
    design = read_board(source.with_suffix(".kicad_pcb"))
    assert design.board is not None
    (fp,) = design.board.footprints
    assert requests(fp, ["Author"], "r1", "R1") == []


def test_local_native_mirror_property_is_retained():
    node = parse(
        '(footprint "Authored" (property "Author" "CC0" (at 0 0) (layer "F.Fab") '
        "(effects (font (size 1 1) (thickness 0.15)) (justify mirror))))"
    )
    assert library_footprint(node) == node


@pytest.mark.parametrize(
    "defect", ["size", "thickness", "layer", "font", "justify", "duplicate-justify", "duplicate-name"]
)
def test_mirror_never_bypasses_other_refusals(tmp_path: Path, defect: str):
    source = source_project(tmp_path / "source", 10, "top", 180, True, True)
    board = source.with_suffix(".kicad_pcb")
    root = parse(board.read_text())
    (fp,) = root.nodes("footprint")
    prop = next(p for p in fp.nodes("property") if p.atoms()[0].value == "Author")
    substitutions = {
        "size": ("(size 1 1)", "(size 1 2)"),
        "thickness": ("(thickness 0.15)", ""),
        "layer": ('(layer "F.Fab")', '(layer "User.Drawings")'),
        "font": ("(thickness 0.15)", "(thickness 0.15) (unknown_style yes)"),
        "justify": ("right bottom mirror", "right bottom mirror future_justify"),
        "duplicate-justify": (
            "(justify right bottom mirror)",
            "(justify right bottom mirror) (justify left)",
        ),
    }
    if defect == "duplicate-name":
        changed = fp.with_children((*fp.children, prop))
    else:
        a, b = substitutions[defect]
        text = dumps(prop)
        assert a in text
        replacement = parse(text.replace(a, b))
        changed = fp.with_children(tuple(replacement if c is prop else c for c in fp.children))
    board.write_text(dumps(root.with_children(tuple(changed if c is fp else c for c in root.children))))
    before = board.read_bytes()
    result = api.run("import", str(source), "--to", "python", "--out", "refused", "--dry-run", cwd=tmp_path)
    assert result.exit_code == 3 and result.error and result.error["code"] == "FEN-3004"
    assert not result.result.get("plan") and not (tmp_path / "refused").exists()
    assert board.read_bytes() == before


def test_native_mirror_variants_preserve_distinct_values(tmp_path: Path):
    from _importcode import copy_project

    source = copy_project(tmp_path)
    board = source.with_suffix(".kicad_pcb")
    root = parse(board.read_text())
    changed = {}
    for fp in root.nodes("footprint"):
        ref = next(p.atoms()[1].value for p in fp.nodes("property") if p.atoms()[0].value == "Reference")
        if ref in {"R101", "R201"}:
            prop = parse(
                '(property "Author" "'
                + ref
                + ' authored CC0" (at 1 2 0) (layer "F.Fab") (hide yes) '
                + "(effects (font (size 1 1) (thickness 0.15)) (justify mirror)))"
            )
            changed[id(fp)] = fp.with_children((*fp.children, prop))
    assert len(changed) == 2
    board.write_text(dumps(root.with_children(tuple(changed.get(id(c), c) for c in root.children))))
    args = ("import", str(source), "--to", "python", "--out", "code", "--licence", "CC0-1.0")
    plan = api.run(*args, "--dry-run", cwd=tmp_path)
    assert plan.exit_code == 0, plan.error
    confirm = api.run(*args, "--confirm", "--plan", plan.result["plan_id"], cwd=tmp_path)
    assert confirm.exit_code == 0, confirm.error
    definitions = [p.read_text() for p in (tmp_path / "code/lib").rglob("*.kicad_mod")]
    for ref in ("R101", "R201"):
        assert sum(ref + " authored CC0" in text for text in definitions) == 1
    proof = api.run(
        "verify-source", "code/design.py", "--against", str(source), "--levels", "1,2,3,4,5,6,7", cwd=tmp_path
    )
    assert proof.exit_code == 0, (proof.error, proof.result.get("differences"))
    assert proof.result["differences"] == [] and proof.result["accepted"] == []
    (declaration,) = [p for p in (tmp_path / "code").rglob("*.py") if "R101 authored CC0" in p.read_text()]
    text = declaration.read_text()
    declaration.write_text(text.replace("R101 authored CC0", "Altered authored CC0"))
    conflict = api.run("build", "code/design.py", "--out", "conflicted", "--dry-run", cwd=tmp_path)
    assert conflict.exit_code == 5, conflict.error
    assert any(i["code"] == "build.property-conflict" for i in conflict.envelope["issues"])
    assert not conflict.result.get("plan")
