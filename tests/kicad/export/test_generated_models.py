# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad reads the generated STEP models (change c0260, scenario "KiCad reads the models";
H-K-STEP-MODELS).

A board built by Fenolite whose three parts use ``drawing = 1`` generated footprints (a chip, a molded diode
and a gull-wing SOIC) is exported with ``kicad-cli pcb export step``: each footprint's model, written by the
build under ``lib/Local.3dshapes/``, is added as one ``NEXT_ASSEMBLY_USAGE_OCCURRENCE`` named after its
reference, and no model is reported missing."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from _buildhelp import build
from _kicad import major, run_raw

from fenolite.dsl import Design, Footprint, Net, Part, connect, mm

pytestmark = pytest.mark.needs_kicad

PACKAGES = Path(__file__).resolve().parents[2] / "data" / "packages"
OCCURRENCE = re.compile(r"NEXT_ASSEMBLY_USAGE_OCCURRENCE\s*\(\s*'[^']*'\s*,\s*'([^']*)'")
REFS = ("D1", "R1", "U1")


def _design() -> Design:
    design = Design("generated")
    design.board(mm(30), mm(20))
    chip, diode, soic = (
        Footprint.from_package((PACKAGES / f"{stem}.toml").read_text(encoding="utf-8"))
        for stem in ("chip0603", "sod123", "soic8")
    )
    for footprint in (chip, diode, soic):
        design.add_footprint(footprint)
    r1 = Part("R1", "Mini:Mini_R", footprint=chip.lib_id, value="1k")
    d1 = Part("D1", "Mini:Mini_R", footprint=diode.lib_id, value="D")
    u1 = Part("U1", "Mini:Mini_R", footprint=soic.lib_id, value="U")
    design.add(r1, d1, u1)
    connect(Net("A"), r1[1], d1[1])
    connect(Net("B"), d1[2], u1[1])
    r1.place(mm(6), mm(10))
    d1.place(mm(14), mm(10))
    u1.place(mm(23), mm(10))
    return design


def test_kicad_reads_the_models(tmp_path: Path) -> None:
    design = _design()
    output = build(
        design, major(), authored_footprints={key: fp.definition for key, fp in design.footprints.items()}
    )
    models = sorted(path for path in output.files if path.startswith("lib/Local.3dshapes/"))
    assert len(models) == 3
    for path, data in output.files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    exported = tmp_path / "board.step"
    result = run_raw("pcb", "export", "step", "-o", exported, tmp_path / "generated.kicad_pcb")
    print(result.stdout)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Could not add 3D model" not in result.stdout + result.stderr
    names = OCCURRENCE.findall(exported.read_text(encoding="utf-8", errors="replace"))
    assert sorted(name for name in names if name in REFS) == list(REFS)
