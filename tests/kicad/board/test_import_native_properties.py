# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Actual native full mirror/TAB import proofs; unit jobs keep only pure controls."""

from pathlib import Path

import pytest
from _native_custom import source_project, tab_project

from fenolite import api
from fenolite.backends.kicad.sexpr import Atom, parse

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize(
    "target,side,rotation,visible,styled",
    [
        (9, "top", 90, True, False),
        (9, "bottom", 270, True, True),
        pytest.param(10, "top", 180, False, True, marks=pytest.mark.kicad_min_major(10)),
        pytest.param(10, "bottom", 0, True, False, marks=pytest.mark.kicad_min_major(10)),
    ],
)
def test_native_mirror_full_import_proof(
    tmp_path: Path, target: int, side: str, rotation: int, visible: bool, styled: bool
):
    source = source_project(tmp_path / "source", target, side, rotation, visible, styled)
    before = {p.name: p.read_bytes() for p in source.parent.iterdir() if p.is_file()}
    args = (
        "import",
        str(source),
        "--to",
        "python",
        "--out",
        "code",
        "--licence",
        "CC0-1.0",
        "--kicad-version",
        str(target),
    )
    planned = api.run(*args, "--dry-run", cwd=tmp_path)
    assert planned.exit_code == 0, planned.error
    confirmed = api.run(*args, "--confirm", "--plan", planned.result["plan_id"], cwd=tmp_path)
    assert confirmed.exit_code == 0, confirmed.error
    script = (tmp_path / "code/design.py").read_text()
    assert '"Author": "Fenolite CC0 control"' in script
    assert '.field("Author"' not in script
    proof = api.run(
        "verify-source",
        "code/design.py",
        "--against",
        str(source),
        "--target",
        str(target),
        "--levels",
        "1,2,3,4,5,6,7,8,S",
        "--kicad-version",
        str(target),
        cwd=tmp_path,
    )
    assert proof.exit_code == 0, (proof.error, proof.result.get("differences"))
    assert proof.result["differences"] == [] and proof.result["accepted"] == []
    assert all(row["status"] == "equal" for row in proof.result["levels"])
    assert {p.name: p.read_bytes() for p in source.parent.iterdir() if p.is_file()} == before


@pytest.mark.parametrize(
    "target,side,rotation,visible,styled",
    [
        (9, "top", 270, True, True),
        (9, "bottom", 180, True, False),
        pytest.param(10, "top", 90, False, True, marks=pytest.mark.kicad_min_major(10)),
        pytest.param(10, "bottom", 0, True, False, marks=pytest.mark.kicad_min_major(10)),
    ],
)
def test_native_tab_full_import_proof(
    tmp_path: Path, target: int, side: str, rotation: int, visible: bool, styled: bool
):
    from fenolite.backends.kicad.pcb import read_board

    source = tab_project(tmp_path / "original", target, side, rotation, visible, styled)
    board = source.with_suffix(".kicad_pcb")
    before = board.read_bytes()
    args = (
        "import",
        str(source),
        "--to",
        "python",
        "--out",
        "code",
        "--licence",
        "CC0-1.0",
        "--kicad-version",
        str(target),
    )
    plan = api.run(*args, "--dry-run", cwd=tmp_path)
    assert plan.exit_code == 0, plan.error
    written = api.run(*args, "--confirm", "--plan", plan.result["plan_id"], cwd=tmp_path)
    assert written.exit_code == 0, written.error
    assert all('"Author"' not in p.read_text() for p in (tmp_path / "code").rglob("*.py"))
    proof = api.run(
        "verify-source",
        "code/design.py",
        "--against",
        str(source),
        "--target",
        str(target),
        "--levels",
        "1,2,3,4,5,6,7,8,S",
        "--kicad-version",
        str(target),
        cwd=tmp_path,
    )
    assert proof.exit_code == 0, (proof.error, proof.result.get("differences"))
    assert proof.result["differences"] == [] and proof.result["accepted"] == []
    assert all(row["status"] == "equal" for row in proof.result["levels"])
    build_args = ("build", "code/design.py", "--out", "fresh", "--kicad-version", str(target))
    build_plan = api.run(*build_args, "--dry-run", cwd=tmp_path)
    assert build_plan.exit_code == 0, build_plan.error
    replay = api.run(*build_args, "--confirm", "--plan", build_plan.result["plan_id"], cwd=tmp_path)
    assert replay.exit_code == 0, replay.error
    (generated,) = (tmp_path / "fresh").glob("*.kicad_pcb")
    original_model = read_board(board.read_text())
    actual = read_board(generated.read_text())
    assert (
        actual.circuit.components[0].properties["Author"]
        == original_model.circuit.components[0].properties["Author"]
    )
    definitions = list((tmp_path / "code/lib").rglob("*.kicad_mod"))
    (definition,) = [p for p in definitions if 'property "Author"' in p.read_text()]
    native = parse(definition.read_text())
    (prop,) = [p for p in native.nodes("property") if p.atoms()[0].value == "Author"]
    assert prop.atoms()[1].value == "First\tauthored\nSecond\tline"
    unlocked = prop.find("unlocked")
    assert unlocked is not None and [atom.value for atom in unlocked.atoms()] == ["yes"]
    # Independent exact raw/native value guard: no L7 value-detection claim.
    tampered = prop.with_children(
        (prop.atoms()[0], Atom.string(prop.atoms()[1].value.replace("\t", " ")), *prop.children[2:])
    )
    assert tampered.atoms()[1].value != original_model.circuit.components[0].properties["Author"]
    assert board.read_bytes() == before
