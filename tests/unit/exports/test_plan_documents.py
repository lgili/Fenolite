# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The six document kinds of the export plan against the fake ``kicad-cli`` (capability
manufacturing-exports, "Export kinds and their arguments", "STEP export with 3D models" and "Schematic
PDF export sheets"; change c0116). Hermetic."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from _boards import FIXTURE
from _fakecli import calls, fake_kicad_cli
from _models import BOX, BOX_REL, MODELS, model_board, official, resolver
from _projects import hierarchy_project

from fenolite.backends.kicad import models
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import read_board
from fenolite.exports.plan import (
    DOCUMENT_KINDS,
    FAB_KINDS,
    KINDS,
    VOLATILE_PREFIXES,
    arguments,
    dxf_layers,
    pdf_layers,
    run_kind,
)
from fenolite.model.design import Design

FORBIDDEN = ("--check-zones", "--board-plot-params", "--variant", "--drawing-sheet", "--define-var")


@pytest.fixture(scope="module")
def design() -> Design:
    return read_board(FIXTURE)


# --- the kinds table --------------------------------------------------------------------------------


def test_kinds_and_their_repeat_classes() -> None:
    assert tuple(KINDS) == (*FAB_KINDS, *DOCUMENT_KINDS)
    assert DOCUMENT_KINDS == ("ipc2581", "odb", "step", "pdf", "dxf", "sch-pdf")
    assert {kind: entry.repeat for kind, entry in KINDS.items()} == {
        "gerbers": "content",
        "drill": "content",
        "pos": "bytes",
        "ipcd356": "bytes",
        "ipc2581": "none",
        "odb": "none",
        "step": "none",
        "pdf": "content",
        "dxf": "bytes",
        "sch-pdf": "content",
    }
    for kind, entry in KINDS.items():
        assert entry.majors == (9, 10)
        assert entry.repeatable is (entry.repeat == "bytes")
        assert entry.source == ("schematic" if kind == "sch-pdf" else "board")
        # a kind whose runs share nothing has no date line to leave out; a `content` kind has one
        assert bool(VOLATILE_PREFIXES[kind]) is (entry.repeat == "content")
    assert VOLATILE_PREFIXES["pdf"] == VOLATILE_PREFIXES["sch-pdf"] == (b"/CreationDate",)


def test_arguments_of_the_document_kinds() -> None:
    assert arguments("ipc2581", stem="b") == [
        "pcb", "export", "ipc2581", "-o", "ipc2581/b.xml", "--version", "C", "--units", "mm",
        "--precision", "6",
    ]  # fmt: skip
    assert arguments("odb", stem="b") == [
        "pcb", "export", "odb", "-o", "odb/b.zip", "--compression", "zip", "--units", "mm",
    ]  # fmt: skip
    assert arguments("step", stem="b") == ["pcb", "export", "step", "-o", "3d/b.step", "--subst-models"]
    assert arguments("pdf", stem="b", layers=("F.Cu", "Edge.Cuts")) == [
        "pcb", "export", "pdf", "-o", "pdf/", "--mode-separate", "--layers", "F.Cu,Edge.Cuts",
        "--common-layers", "Edge.Cuts", "--include-border-title",
    ]  # fmt: skip
    assert arguments("dxf", stem="b", layers=("Edge.Cuts", "F.Fab")) == [
        "pcb", "export", "dxf", "-o", "dxf/", "--mode-multi", "--output-units", "mm", "--layers",
        "Edge.Cuts,F.Fab",
    ]  # fmt: skip
    assert arguments("sch-pdf", stem="b") == ["sch", "export", "pdf", "-o", "schematic/b.pdf"]


def test_forbidden_options_are_absent_from_every_kind() -> None:
    for kind in KINDS:
        assert not set(FORBIDDEN) & set(arguments(kind, stem="b", layers=("F.Cu",))), kind


def test_layers_of_the_document_kinds(tmp_path: Path, design: Design) -> None:
    pdf = pdf_layers(design)
    assert pdf[:2] == ("F.Cu", "B.Cu") and pdf[-3:] == ("F.Fab", "B.Fab", "Edge.Cuts")
    dxf = dxf_layers(design)
    assert dxf == ("Edge.Cuts", "F.Fab", "B.Fab", "F.CrtYd", "B.CrtYd")
    assert not any(name.endswith(".Cu") for name in dxf)
    script = fake_kicad_cli(tmp_path / "bin")
    with pytest.raises(ValueError, match="gerbers export takes no layer list"):
        run_kind(KicadCli(script), "gerbers", FIXTURE, {}, major=10, design=design, layers=("F.Cu",))
    assert calls(script) == []


def test_a_given_layer_list_replaces_the_default(tmp_path: Path, design: Design) -> None:
    script = fake_kicad_cli(tmp_path / "bin")
    run_kind(KicadCli(script), "pdf", FIXTURE, {}, major=10, design=design, layers=("F.Fab", "Edge.Cuts"))
    args = calls(script)[-1]["args"]
    assert args[args.index("--layers") + 1] == "F.Fab,Edge.Cuts"


def test_one_artefact_per_layer(tmp_path: Path, design: Design) -> None:
    files = {
        "pdf": {"{stem}-F_Cu.pdf": "%PDF\n", "{stem}-F_Fab.pdf": "%PDF\n"},
        "dxf": {"{stem}-Edge_Cuts.dxf": "0\nEOF\n", "{stem}-F_Courtyard.dxf": "0\nEOF\n"},
    }
    script = fake_kicad_cli(tmp_path / "bin", export_files=files, writes=("two_layer.kicad_prl",))
    cli = KicadCli(script)
    pdf = run_kind(cli, "pdf", FIXTURE, {}, major=10, design=design)
    dxf = run_kind(cli, "dxf", FIXTURE, {}, major=10, design=design)
    assert [(a.path, a.layer, a.repeatable) for a in pdf.artifacts] == [
        ("pdf/two_layer-F_Cu.pdf", "F.Cu", False),
        ("pdf/two_layer-F_Fab.pdf", "F.Fab", False),
    ]
    assert [(a.path, a.layer, a.repeatable) for a in dxf.artifacts] == [
        ("dxf/two_layer-Edge_Cuts.dxf", "Edge.Cuts", True),
        ("dxf/two_layer-F_Courtyard.dxf", "F.CrtYd", True),
    ]
    assert pdf.tool_writes == dxf.tool_writes == ("two_layer.kicad_prl",)
    assert pdf.models == dxf.models == ()
    seen = [c["args"] for c in calls(script) if c["args"][:2] == ["pcb", "export"]]
    assert seen[0][-1] == "two_layer.kicad_pcb" and "--include-border-title" in seen[0]
    assert seen[1][seen[1].index("--layers") + 1] == "Edge.Cuts,F.Fab,B.Fab,F.CrtYd,B.CrtYd"


def test_single_file_document_kinds(tmp_path: Path) -> None:
    cli = KicadCli(fake_kicad_cli(tmp_path / "bin"))
    for kind, path in (("ipc2581", "ipc2581/two_layer.xml"), ("odb", "odb/two_layer.zip")):
        (artifact,) = run_kind(cli, kind, FIXTURE, {}, major=9).artifacts
        assert (artifact.path, artifact.kind, artifact.layer, artifact.repeatable) == (
            path,
            kind,
            None,
            False,
        )


def test_the_preset_callback_never_reaches_a_document_kind(tmp_path: Path, design: Design) -> None:
    script = fake_kicad_cli(tmp_path / "bin")
    cli = KicadCli(script)

    def refuse(kind: str, stem: str, layers: object) -> list[str]:
        raise AssertionError(f"the preset callback was called for {kind}")

    for kind in ("ipc2581", "odb", "pdf", "dxf"):
        assert run_kind(cli, kind, FIXTURE, {}, major=10, design=design, args=refuse).issues == ()
    assert calls(script)[-1]["args"][:-1] == arguments("dxf", stem="two_layer", layers=dxf_layers(design))


def test_a_failed_document_kind(tmp_path: Path) -> None:
    cli = KicadCli(fake_kicad_cli(tmp_path / "bin", export_fail=("odb",)))
    result = run_kind(cli, "odb", FIXTURE, {}, major=10)
    assert result.artifacts == () and [i.code for i in result.issues] == ["export.failed"]
    assert result.issues[0].where == "odb"


# --- STEP with 3D models ----------------------------------------------------------------------------


def _step_board(tmp_path: Path, path: str) -> Path:
    board = tmp_path / "proj" / "b.kicad_pcb"
    board.parent.mkdir(parents=True, exist_ok=True)
    board.write_text(model_board({"U1": [path], "U2": [path]}), encoding="utf-8")
    return board


def _plan(tmp_path: Path, board: Path, folder: Path) -> models.ModelPlan:
    found = resolver(tmp_path, env={"KICAD10_3DMODEL_DIR": str(folder)}, project_dir=board.parent)
    return models.plan_models(models.board_models(board.read_text(encoding="utf-8")), found)


def test_step_models_located_go_into_the_run(tmp_path: Path) -> None:
    board = _step_board(tmp_path, official())
    script = fake_kicad_cli(tmp_path / "bin")
    result = run_kind(KicadCli(script), "step", board, {}, major=10, models=_plan(tmp_path, board, MODELS))
    assert result.issues == ()
    assert [a.path for a in result.artifacts] == ["3d/b.step"]
    call = calls(script)[-1]
    assert f"3dmodels/{BOX_REL}" in call["tree"]
    assert call["env"] == {"KICAD10_3DMODEL_DIR": "3dmodels"}
    assert call["args"] == ["pcb", "export", "step", "-o", "3d/b.step", "--subst-models", "b.kicad_pcb"]
    (use,) = result.models
    assert (use.path, use.source, use.refs) == (official(), "env", ("U1", "U2"))
    assert use.sha256 == hashlib.sha256(BOX.read_bytes()).hexdigest() and use.bytes == BOX.stat().st_size
    assert str(tmp_path) not in repr(result.models)


def test_step_models_plan_is_built_from_the_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without ``models=``, the kind locates the models itself, through the caller's environment."""
    board = _step_board(tmp_path, official())
    empty = tmp_path / "config-home"
    empty.mkdir()
    monkeypatch.setenv("KICAD10_3DMODEL_DIR", str(MODELS))
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(empty))
    script = fake_kicad_cli(tmp_path / "bin")
    result = run_kind(KicadCli(script), "step", board, {}, major=10)
    assert [(use.source, use.refs) for use in result.models] == [("env", ("U1", "U2"))]
    assert calls(script)[-1]["env"] == {"KICAD10_3DMODEL_DIR": "3dmodels"}


def test_step_models_missing_is_a_warning(tmp_path: Path) -> None:
    board = _step_board(tmp_path, official())
    empty = tmp_path / "empty-models"
    empty.mkdir()
    script = fake_kicad_cli(tmp_path / "bin")
    result = run_kind(KicadCli(script), "step", board, {}, major=10, models=_plan(tmp_path, board, empty))
    (warning,) = result.issues
    assert (warning.code, warning.severity) == ("kicad.lib.missing-3d-model", "warning")
    assert official() in warning.message and "U1" in warning.message and "U2" in warning.message
    assert [a.path for a in result.artifacts] == ["3d/b.step"]
    call = calls(script)[-1]
    assert call["env"] == {"KICAD10_3DMODEL_DIR": "3dmodels"}
    assert not any(name.startswith("3dmodels/") for name in call["tree"])
    (use,) = result.models
    assert (use.source, use.sha256, use.bytes, use.refs) == ("missing", None, None, ("U1", "U2"))


def test_step_models_unread_by_kicad(tmp_path: Path) -> None:
    board = _step_board(tmp_path, official())
    said = "Could not add 3D model for U1.\nFile not found: x\nSTEP file '3d/b.step' created.\n"
    script = fake_kicad_cli(tmp_path / "bin", export_output={"step": said})
    result = run_kind(KicadCli(script), "step", board, {}, major=10, models=_plan(tmp_path, board, MODELS))
    (warning,) = result.issues
    assert (warning.code, warning.severity, warning.where) == ("export.model-unread", "warning", "U1")
    assert [a.path for a in result.artifacts] == ["3d/b.step"]


def test_step_models_unread_line_of_a_missing_model_is_not_reported_twice(tmp_path: Path) -> None:
    board = _step_board(tmp_path, official())
    empty = tmp_path / "empty-models"
    empty.mkdir()
    script = fake_kicad_cli(tmp_path / "bin", export_output={"step": "Could not add 3D model for U1.\n"})
    result = run_kind(KicadCli(script), "step", board, {}, major=10, models=_plan(tmp_path, board, empty))
    assert [i.code for i in result.issues] == ["kicad.lib.missing-3d-model"]


def test_step_models_vrml_brings_its_step_sibling(tmp_path: Path) -> None:
    source = tmp_path / "source" / "Fenolite.3dshapes"
    source.mkdir(parents=True)
    (source / "Box_2x1.wrl").write_text("#VRML V2.0 utf8\n", encoding="utf-8")
    shutil.copyfile(BOX, source / "Box_2x1.step")
    board = _step_board(tmp_path, official("Fenolite.3dshapes/Box_2x1.wrl"))
    script = fake_kicad_cli(tmp_path / "bin")
    plan = _plan(tmp_path, board, source.parent)
    result = run_kind(KicadCli(script), "step", board, {}, major=10, models=plan)
    tree = calls(script)[-1]["tree"]
    assert "3dmodels/Fenolite.3dshapes/Box_2x1.wrl" in tree
    assert "3dmodels/Fenolite.3dshapes/Box_2x1.step" in tree
    assert [use.path for use in result.models] == [official("Fenolite.3dshapes/Box_2x1.wrl")]


# --- schematic PDF ----------------------------------------------------------------------------------


def test_sch_pdf_takes_the_whole_hierarchy(tmp_path: Path) -> None:
    root = hierarchy_project(tmp_path / "proj", stem="b")
    script = fake_kicad_cli(tmp_path / "bin")
    board = root / "b.kicad_pcb"
    from fenolite.backends.kicad.projectset import project_set

    project = project_set(board)
    others = {name: path for name, path in project.files.items() if name != project.board}
    result = run_kind(KicadCli(script), "sch-pdf", board, others, major=10)
    assert result.issues == ()
    assert [(a.path, a.kind, a.layer, a.repeatable) for a in result.artifacts] == [
        ("schematic/b.pdf", "sch-pdf", None, False)
    ]
    call = calls(script)[-1]
    assert call["args"] == ["sch", "export", "pdf", "-o", "schematic/b.pdf", "b.kicad_sch"]
    assert {"b.kicad_sch", "child.kicad_sch"} <= set(call["tree"])


def test_sch_pdf_refuses_a_missing_sheet(tmp_path: Path) -> None:
    root = hierarchy_project(tmp_path / "proj", stem="b")
    (root / "child.kicad_sch").unlink()
    script = fake_kicad_cli(tmp_path / "bin")
    result = run_kind(KicadCli(script), "sch-pdf", root / "b.kicad_pcb", {}, major=10)
    assert result.artifacts == ()
    (refusal,) = result.issues
    assert (refusal.code, refusal.severity, refusal.where) == (
        "export.sheet-missing",
        "error",
        "child.kicad_sch",
    )
    assert calls(script) == []
