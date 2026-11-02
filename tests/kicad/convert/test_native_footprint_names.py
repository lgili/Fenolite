# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Load safe native footprint names from authored conversion data (c0319 task 1.15)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import _a2kcases
import pytest
from _probes import runner

from fenolite.convert.direction import Options
from fenolite.convert.sources import read_source
from fenolite.convert.to_kicad import write_altium

pytestmark = pytest.mark.needs_kicad


def test_derived_space_and_underscore_names_load_independently() -> None:
    source = read_source(_a2kcases.SAMPLE)
    design = source.design
    assert design.board is not None
    selected = design.board.footprints[:2]
    names = {fp.component_id: name for fp, name in zip(selected, ("M Mount", "M_Mount"), strict=True)}
    board = replace(
        design.board,
        footprints=tuple(
            replace(fp, lib_ref=names.get(fp.component_id, fp.lib_ref)) for fp in design.board.footprints
        ),
    )
    circuit = replace(
        design.circuit,
        components=tuple(
            replace(c, lib_footprint_ref=names.get(c.id, c.lib_footprint_ref))
            for c in design.circuit.components
        ),
    )
    cli = runner()
    result = write_altium(
        replace(source, design=replace(design, board=board, circuit=circuit)),
        Options(kicad_version=cli.major(), name="authored"),
    )
    run = cli.run(
        ["fp", "export", "svg", "-o", "out", "authored.pretty"],
        files=result.files,
        folders=("out",),
    )
    assert run.returncode == 0, run.stderr
    assert {"M Mount.svg", "M_Mount.svg"} <= {Path(name).name for name in run.outputs}
