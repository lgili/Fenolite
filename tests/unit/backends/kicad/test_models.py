# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The model paths of a board and the plan of a STEP run (capability manufacturing-exports, "STEP export
with 3D models"; change c0116). Hermetic."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from _boards import FIXTURE
from _models import BOX, BOX_REL, MODELS, model_board, official, resolver, with_models

from fenolite.backends.kicad import models
from fenolite.backends.kicad.models import ModelRef, ModelUse
from fenolite.core.evidence import Level

SHA = hashlib.sha256(BOX.read_bytes()).hexdigest()


def test_board_models_in_board_order() -> None:
    text = model_board({"U2": [official(), "${KIPRJMOD}/m/a.wrl"], "U1": [official()]})
    assert models.board_models(text) == (
        ModelRef("U2", official()),
        ModelRef("U2", "${KIPRJMOD}/m/a.wrl"),
        ModelRef("U1", official()),
    )


def test_board_models_of_a_printed_board() -> None:
    text = with_models(FIXTURE.read_text(encoding="utf-8"), {"R1": official(), "D1": official(major=9)})
    assert models.board_models(text) == (ModelRef("R1", official()), ModelRef("D1", official(major=9)))
    assert models.board_models(FIXTURE.read_text(encoding="utf-8")) == ()


def test_board_models_of_a_text_that_is_no_board() -> None:
    assert models.board_models("not a board (") == ()
    assert models.board_models("") == ()


def test_plan_of_located_models(tmp_path: Path) -> None:
    refs = models.board_models(model_board({"U2": [official()], "U1": [official()]}))
    plan = models.plan_models(refs, resolver(tmp_path, env={"KICAD10_3DMODEL_DIR": str(MODELS)}))
    assert dict(plan.files) == {f"3dmodels/{BOX_REL}": BOX}
    assert dict(plan.env) == {"KICAD10_3DMODEL_DIR": "3dmodels"}
    assert plan.uses == (ModelUse(official(), "env", SHA, BOX.stat().st_size, ("U1", "U2")),)
    assert plan.issues == ()
    assert models.located_refs(plan.uses) == {"U1", "U2"}


def test_plan_sets_the_variable_of_every_major_named(tmp_path: Path) -> None:
    """Also for a major none of whose paths was located: ``kicad-cli`` never falls back on its install."""
    refs = models.board_models(model_board({"U1": [official()], "U2": [official("X.3dshapes/y.step", 9)]}))
    plan = models.plan_models(refs, resolver(tmp_path, env={"KICAD10_3DMODEL_DIR": str(MODELS)}))
    assert dict(plan.env) == {"KICAD10_3DMODEL_DIR": "3dmodels", "KICAD9_3DMODEL_DIR": "3dmodels"}
    assert [(use.path, use.source) for use in plan.uses] == [
        (official(), "env"),
        (official("X.3dshapes/y.step", 9), "missing"),
    ]
    (warning,) = plan.issues
    assert warning.code == "kicad.lib.missing-3d-model" and warning.severity == "warning"
    assert "U2" in warning.message and "X.3dshapes/y.step" in warning.message and "U1" not in warning.message
    assert models.located_refs(plan.uses) == {"U1"}


def test_plan_of_a_part_with_one_model_missing(tmp_path: Path) -> None:
    refs = models.board_models(model_board({"U1": [official(), official("X.3dshapes/y.step")]}))
    plan = models.plan_models(refs, resolver(tmp_path, env={"KICAD10_3DMODEL_DIR": str(MODELS)}))
    assert models.located_refs(plan.uses) == frozenset()  # U1 has a model that was not given


def test_plan_of_project_and_in_place_models(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    (project / "m").mkdir(parents=True)
    shutil.copyfile(BOX, project / "m" / "box.step")
    refs = models.board_models(model_board({"U1": ["${KIPRJMOD}/m/box.step"], "U2": [str(BOX)]}))
    plan = models.plan_models(refs, resolver(tmp_path, project_dir=project))
    assert dict(plan.files) == {"m/box.step": project / "m" / "box.step"}
    assert dict(plan.env) == {}
    by_source = {use.source: use for use in plan.uses}
    assert by_source["project"].path == "${KIPRJMOD}/m/box.step" and by_source["project"].sha256 == SHA
    # a path read in place is reported without its folder: no result holds a path of the machine
    assert by_source["in-place"] == ModelUse("Box_2x1.step", "in-place", None, None, ("U2",))
    assert str(tmp_path) not in repr(plan.uses) and str(BOX.parent) not in repr(plan.uses)


def test_plan_brings_the_step_siblings_of_a_vrml_model(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "L.3dshapes").mkdir(parents=True)
    (source / "L.3dshapes" / "a.wrl").write_text("#VRML V2.0 utf8\n", encoding="utf-8")
    shutil.copyfile(BOX, source / "L.3dshapes" / "a.step")
    shutil.copyfile(BOX, source / "L.3dshapes" / "a.stp")
    refs = models.board_models(model_board({"U1": [official("L.3dshapes/a.wrl")]}))
    plan = models.plan_models(refs, resolver(tmp_path, env={"KICAD10_3DMODEL_DIR": str(source)}))
    assert sorted(plan.files) == [
        "3dmodels/L.3dshapes/a.step",
        "3dmodels/L.3dshapes/a.stp",
        "3dmodels/L.3dshapes/a.wrl",
    ]
    assert len(plan.uses) == 1 and plan.uses[0].refs == ("U1",)


def test_unread_refs() -> None:
    said = (
        "Could not add 3D model for U1.\nFile not found: ${KICAD10_3DMODEL_DIR}/a.step\n"
        "Could not add 3D model for J2.\r\nCould not add 3D model for U1.\nSTEP file '3d/b.step' created.\n"
    )
    assert models.unread_refs(said) == ("U1", "J2")
    assert models.unread_refs("STEP file created.\n") == ()


def test_board_plan_reads_the_board_file(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    (project / "3dmodels" / "Fenolite.3dshapes").mkdir(parents=True)
    shutil.copyfile(BOX, project / "3dmodels" / BOX_REL)
    (project / "b.kicad_pcb").write_text(model_board({"U1": [official()]}), encoding="utf-8")
    plan = models.board_plan(project / "b.kicad_pcb")
    assert [(use.source, use.sha256) for use in plan.uses] == [("project", SHA)]


def test_evidence_and_report_form(tmp_path: Path) -> None:
    assert models.EVIDENCE.level is Level.KICAD_VERIFIED and models.EVIDENCE.hypotheses == (
        "H-K-EXPORT-MODELS",
    )
    use = ModelUse(official(), "env", SHA, 10, ("U1",))
    assert models.use_dict(use) == {
        "path": official(), "source": "env", "sha256": SHA, "bytes": 10, "refs": ["U1"],
    }  # fmt: skip
