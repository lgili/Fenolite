# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Models of a built project in an Altium target (capability design-dsl, "Footprints of every row origin are
vendored"; capability design-conversion, "Model paths read as KiCad reads them"; change c0458).

The design is the blink example beside a project library: a copy of ``tests/data/libs/Mini_v9.pretty`` whose
``Mini_R_0603`` names ``${KIPRJMOD}/m.3dshapes/box.step``, a box that ``backends.step`` writes in the test,
and whose ``Mini_LED_THT_3mm`` keeps its official ``${KICAD10_3DMODEL_DIR}`` model."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _buildhelp import LIBS, blink_text

from fenolite.api import run
from fenolite.api.conversion import convert
from fenolite.backends.step import Prism, write_solids
from fenolite.convert import models

MM = 1_000_000
STAMP = "2026-11-06T00:00:00Z"
BOX = write_solids("box", [Prism(((0, 0), (MM, 0), (MM, MM // 2), (0, MM // 2)), 0, MM // 2)])
OFFICIAL = '"${KICAD10_3DMODEL_DIR}/Mini.3dshapes/Mini_R_0603.step"'
PROJECT = '"${KIPRJMOD}/m.3dshapes/box.step"'


def _design(folder: Path) -> Path:
    """The blink script, its project library with the resistor's model, and the model file beside it."""
    folder.mkdir(parents=True)
    script = folder / "design.py"
    script.write_text(blink_text(), encoding="utf-8")
    library = folder / "lib" / "Mini.pretty"
    shutil.copytree(LIBS / "Mini_v9.pretty", library)
    resistor = library / "Mini_R_0603.kicad_mod"
    text = resistor.read_text(encoding="utf-8")
    assert OFFICIAL in text
    resistor.write_text(text.replace(OFFICIAL, PROJECT), encoding="utf-8")
    (folder / "m.3dshapes").mkdir()
    (folder / "m.3dshapes" / "box.step").write_bytes(BOX)
    (folder / "fp-lib-table").write_text(
        '(fp_lib_table\n\t(version 7)\n\t(lib (name "Mini") (type "KiCad")'
        ' (uri "${KIPRJMOD}/lib/Mini.pretty") (options "") (descr ""))\n)\n',
        encoding="utf-8",
    )
    symbols = (LIBS / "Mini_v9.kicad_sym").as_posix()
    (folder / "sym-lib-table").write_text(
        f'(sym_lib_table\n\t(version 7)\n\t(lib (name "Mini") (type "KiCad") (uri "{symbols}") (options "")'
        ' (descr ""))\n)\n',
        encoding="utf-8",
    )
    return script


def test_build_copies_the_project_model_and_convert_embeds_it(tmp_path: Path) -> None:
    """Scenario "A built project keeps its own models": the built folder holds the box at the path the
    footprint names and no official model; the conversion of the built board embeds the box and loses the
    official models (the LED's and the controller's) under their variable."""
    script = _design(tmp_path / "design")
    reply = run("build", script.name, "--out", "built", "--confirm", cwd=script.parent, timestamp=STAMP)
    assert reply.exit_code == 0, reply.error
    built = script.parent / "built"
    assert (built / "m.3dshapes" / "box.step").read_bytes() == BOX
    assert not list(built.rglob("Mini.3dshapes"))
    (board,) = built.glob("*.kicad_pcb")
    assert PROJECT in board.read_text(encoding="utf-8")
    result = convert(board, to="altium", allow_lossy=True)
    (row,) = [r for r in result.conversion.report.rows if r.kind == models.KIND]
    assert row.written == 1
    assert {r.reason for r in row.reasons if r.outcome == "lost"} == {models.VARIABLE}


def test_build_without_the_model_file_copies_nothing(tmp_path: Path) -> None:
    """A model the script's folder does not hold is not invented: the build copies nothing and the
    conversion counts it ``MISSING``."""
    script = _design(tmp_path / "design")
    (script.parent / "m.3dshapes" / "box.step").unlink()
    reply = run("build", script.name, "--out", "built", "--confirm", cwd=script.parent, timestamp=STAMP)
    assert reply.exit_code == 0, reply.error
    built = script.parent / "built"
    assert not (built / "m.3dshapes").exists()
    (board,) = built.glob("*.kicad_pcb")
    result = convert(board, to="altium", allow_lossy=True)
    (row,) = [r for r in result.conversion.report.rows if r.kind == models.KIND]
    assert row.written == 0 and {r.reason for r in row.reasons} == {models.MISSING, models.VARIABLE}


@pytest.fixture
def tree(tmp_path: Path) -> tuple[Path, Path]:
    """A project folder and, beside it, a shared model folder holding the box."""
    project = tmp_path / "project"
    project.mkdir()
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "box.step").write_bytes(BOX)
    return project, shared / "box.step"


def test_paths_read_as_kicad_reads_them(tree: tuple[Path, Path]) -> None:
    """Scenario "Model paths outside the project": an absolute path and a path that climbs out of the
    folder name the file KiCad reads."""
    project, box = tree
    found = box.resolve()
    assert models.model_path(box.as_posix(), project) == found
    assert models.model_path("${KIPRJMOD}/../shared/box.step", project) == found
    assert models.model_path("$(KIPRJMOD)/../shared/box.step", project) == found
    assert models.model_path("../shared/box.step", project) == found


def test_paths_that_name_no_file(tree: tuple[Path, Path]) -> None:
    """An absent file is ``MISSING`` inside the folder and ``NOT_FOUND`` elsewhere; a Windows path read on
    another system, a variable and a KiCad embedded file keep their reasons."""
    project, box = tree
    assert models.model_path("${KIPRJMOD}/m.3dshapes/none.step", project) == models.MISSING
    assert models.model_path("${KIPRJMOD}", project) == models.MISSING
    assert models.model_path("${KIPRJMOD}/../shared/none.step", project) == models.NOT_FOUND
    assert models.model_path((box.parent / "none.step").as_posix(), project) == models.NOT_FOUND
    if not Path("C:/").is_absolute():
        assert models.model_path("C:/models/box.step", project) == models.NOT_FOUND
    assert models.model_path("${KICAD10_3DMODEL_DIR}/box.step", project) == models.VARIABLE
    assert models.model_path("kicad-embed://box.step", project) == models.KICAD_EMBEDDED
