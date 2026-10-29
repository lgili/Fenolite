# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generated STEP models in a build (change c0260, scenario "Model written beside the library")."""

from __future__ import annotations

from pathlib import Path

from _buildhelp import build
from _outlinehelp import definitions, variant

from fenolite.model.board import outward_height

RECORD = Path(__file__).resolve().parents[2] / "data" / "packages" / "chip0603.toml"
GENERATED = f"""
from pathlib import Path
from fenolite.dsl import Footprint, Part
chip = Footprint.from_package(Path({str(RECORD)!r}).read_text())
design.add_footprint(chip)
r9 = Part("R9", "Mini:Mini_R", footprint=chip.lib_id, value="10k")
design.add(r9)
r9.place(mm(40), mm(20))
"""


def test_model_written_beside_the_library() -> None:
    design = variant(append=GENERATED)
    output = build(design, 10, **definitions(design))
    assert "lib/Local.pretty/CHIP0603_B1.6x0.8.kicad_mod" in output.files
    step = output.files["lib/Local.3dshapes/CHIP0603_B1.6x0.8.step"]
    assert step.startswith(b"ISO-10303-21;") and b"MANIFOLD_SOLID_BREP('body'" in step
    library = output.files["lib/Local.pretty/CHIP0603_B1.6x0.8.kicad_mod"].decode("utf-8")
    assert '(model "${KIPRJMOD}/lib/Local.3dshapes/CHIP0603_B1.6x0.8.step"' in library
    board = output.design.board
    assert board is not None
    r9 = next(fp for fp in board.footprints if fp.lib_ref == "Local:CHIP0603_B1.6x0.8")
    assert [body.name for body in r9.bodies] == ["body"] and outward_height(r9) == 550_000
    again = build(variant(append=GENERATED), 10, **definitions(variant(append=GENERATED)))
    assert again.files["lib/Local.3dshapes/CHIP0603_B1.6x0.8.step"] == step


def test_catalog_only_design_keeps_its_files() -> None:
    plain = variant()
    output = build(plain, 10, **definitions(plain))
    assert not [path for path in output.files if ".3dshapes/" in path]
    board = output.design.board
    assert board is not None and all(not fp.bodies for fp in board.footprints)
