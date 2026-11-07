# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored chamfer flip canary and wrong-corner control (H-G-CHAMFER-FLIP; c0282).

The local mathematical mirror is tested independently of KiCad in test_embed_bottom.py. This
canary checks KiCad library parity on both supported majors; evidence is not promoted by unit tests.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _probes import runner

from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import read_footprint, write_footprint
from fenolite.backends.kicad.pcb import write_board
from fenolite.core.coords import Point
from fenolite.model.board import Outline
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad
FIXTURE = Path(__file__).resolve().parents[2] / "data/kicad/footprint/ExactChamfer.kicad_mod"


def test_bottom_chamfer_library_parity(tmp_path: Path) -> None:
    tool = runner()
    target = tool.major()
    assert target in (9, 10)
    print(f"KiCad {tool.version()}")
    definition = read_footprint(FIXTURE, library="Authored")
    components, footprints = [], []
    for index, rotation in enumerate((0, 30_000_000, 90_000_000, 180_000_000), start=1):
        component = Component(
            id=f"cmp_00000000-0000-4000-8000-{index:012d}",
            ref=f"U{index}",
            value=definition.name,
            lib_footprint_ref=definition.lib_id,
        )
        components.append(component)
        footprints.append(
            place_footprint(
                definition,
                component=component,
                at=Point(index * 10_000_000, 10_000_000),
                rotation=rotation,
                side="bottom",
                key=component.ref,
            )
        )
    design = Design.new("chamfer", seed=282)
    assert design.board is not None
    outline = Outline(
        id="out_00000000-0000-4000-8000-000000000282",
        points=(Point(0, 0), Point(50_000_000, 0), Point(50_000_000, 20_000_000), Point(0, 20_000_000)),
    )
    design = dataclasses.replace(
        design,
        circuit=Circuit(components=tuple(components)),
        board=dataclasses.replace(
            design.board, layers=created_layers(2), outline=outline, footprints=tuple(footprints)
        ),
    )
    library = tmp_path / "Authored.pretty"
    library.mkdir()
    (library / "ExactChamfer.kicad_mod").write_text(write_footprint(definition, target=target), "utf-8")
    table = tmp_path / "fp-lib-table"
    table.write_text(
        '(fp_lib_table (lib (name "Authored") (type "KiCad") '
        '(uri "${KIPRJMOD}/Authored.pretty") (options "") (descr "")))\n',
        "utf-8",
    )
    project = tmp_path / "chamfer.kicad_pro"
    project.write_text("{}\n", "utf-8")
    board = tmp_path / "chamfer.kicad_pcb"
    text = write_board(design, target=target).text
    assert text.count("bottom_left top_right") == 4
    extra = {table.name: table, project.name: project, library.name: library}
    for wrong in (False, True):
        board.write_text(
            text.replace("bottom_left top_right", "top_left bottom_right") if wrong else text, "utf-8"
        )
        result = tool.drc(board, files=extra)
        assert result.report is not None
        mismatch = result.report.of_type("lib_footprint_mismatch")
        label = "wrong-corner control" if wrong else "authored bottom chamfers"
        print(f"KiCad {target}: {label}: {len(mismatch)} mismatches")
        assert bool(mismatch) is wrong
