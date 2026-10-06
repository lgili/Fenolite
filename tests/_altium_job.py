# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Shared cases of change c0087: Altium builds of the blink sample with an output job or a drawing sheet,
and the shipped sheet examples as drawing sheets."""

from __future__ import annotations

import dataclasses
import tempfile
from pathlib import Path

from _altium import blink, blink_resolver

from fenolite.backends.altium.read.sch import Parameter, read_schematic
from fenolite.core.errors import Issue
from fenolite.dsl import placements, to_model
from fenolite.lens.altium import build_altium
from fenolite.lens.build import BuildOutput
from fenolite.model.presentation import PAPER_SIZES, DrawingSheet, SheetFrameRef
from fenolite.templates import build_sheet, example_path, load_spec

SHEET_LINES = (
    'design.board(mm(50), mm(30))\ndesign.sheet("A4", drawing_sheet="frames/generic.sheet.toml")\n'
    'design.title_block(title="Blink", revision="B", variables={"PROJECT_CODE": "F-1"})'
)
"""What a blink script with a drawing sheet and a title block holds in place of its ``board()`` line."""
BOARD_LINE = "design.board(mm(50), mm(30))"
A4 = (PAPER_SIZES["A4"][1], PAPER_SIZES["A4"][0])
"""The A4 landscape page (width, height) in nm."""


def example_sheet(name: str = "iso5457_generic") -> DrawingSheet:
    """A shipped sheet example as the drawing sheet a build reads."""
    path = example_path(name)
    return build_sheet(load_spec(path.read_text(encoding="utf-8"), file=path.name), base_dir=path.parent)


def blink_output(*, framed: bool = False, paper: str | None = None, **kwargs: object) -> BuildOutput:
    """An Altium build of the blink sample. ``framed`` gives the script the sheet and the title block of
    ``SHEET_LINES``; ``paper`` replaces the paper of the model's sheet."""
    design = blink(BOARD_LINE, SHEET_LINES) if framed else blink()
    model = to_model(design)
    if paper is not None:
        assert model.board is not None
        frame = SheetFrameRef(paper)  # type: ignore[arg-type]
        model = dataclasses.replace(model, board=dataclasses.replace(model.board, sheet=frame))
    with tempfile.TemporaryDirectory() as folder:
        return build_altium(
            model,
            name=design.name,
            placed=tuple(placements(design)),
            placements=placements(design),
            resolver=blink_resolver(Path(folder)),
            **kwargs,  # type: ignore[arg-type]
        )


def kept_project_issues() -> tuple[Issue, ...]:
    """A build with a job into a folder whose project file is kept and does not list the job."""
    return blink_output(outjob=True, project_exists=True).issues


def grown_paper_issues() -> tuple[Issue, ...]:
    """A drawing sheet on an A5 sheet, which the layout of the blink schematic does not fit."""
    return blink_output(framed=True, paper="A5", drawing_sheet=example_sheet()).issues


def sheet_parameters(data: bytes) -> dict[str, str]:
    """The sheet parameters of a schematic document: name → value of every record 41 without an owner."""
    document = read_schematic(data)
    return {r.name: r.text for r in document.records if isinstance(r, Parameter) and r.owner is None}
