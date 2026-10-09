# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawing kinds on the running ``kicad-cli`` (capability kicad-oracle, "Drawing facts are probed";
change c0117): both kinds of the bench are exported, the drill table agrees with KiCad's report, every
block's texts are drawn inside their block and outside the board box, and two exports give equal
content hashes."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from decimal import Decimal
from functools import cache
from pathlib import Path

import _drawbench
import _probes
import pytest
from _drawdesign import NAME

from fenolite.backends.kicad.cli import CliRun, KicadCli
from fenolite.backends.kicad.drawing import default_sheet_obstacles
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import parse
from fenolite.exports.drawing_layout import AUTO_PAPERS, Box, mirror
from fenolite.exports.drawing_spec import DEFAULT, AssemblySpec, FabSpec
from fenolite.exports.drawings import (
    DrawingResult,
    Page,
    default_sheet,
    fab_board_box,
    run_assembly_drawing,
    run_fab_drawing,
)
from fenolite.exports.manifest import content_sha256

pytestmark = pytest.mark.needs_kicad
MM = Decimal(1_000_000)
SLACK = Decimal("0.05")
SPEC = dataclasses.replace(
    DEFAULT,
    fab=FabSpec(notes=("Board ${TITLE}, revision ${REVISION}.", _drawbench.NOTE)),
    assembly=AssemblySpec(notes=("Fit the header last.",)),
)


class Recording(KicadCli):
    """The runner of the probes, keeping the plot copy of every page it plots."""

    def __init__(self, cli: KicadCli) -> None:
        super().__init__(cli.path, timeout=cli.timeout)
        self.copies: dict[str, str] = {}

    def run(
        self,
        args: Sequence[str],
        *,
        files: Mapping[str, Path | bytes],
        env: Mapping[str, str] | None = None,
        folders: Sequence[str] = (),
    ) -> CliRun:
        if list(args[:3]) == ["pcb", "export", "pdf"]:
            source = files[f"{NAME}.kicad_pcb"]
            assert isinstance(source, bytes)  # a page is plotted from a copy, never from the board file
            self.copies[args[args.index("-o") + 1]] = source.decode("utf-8")
        return super().run(args, files=files, env=env, folders=folders)


@cache
def drawn() -> tuple[DrawingResult, DrawingResult, dict[str, str]]:
    cli = Recording(_probes.runner())
    board = _drawbench.bench_file()
    design = read_board(board)
    fab = run_fab_drawing(cli, board, {}, design=design, spec=SPEC, sheet=default_sheet())
    assembly = run_assembly_drawing(cli, board, {}, design=design, spec=SPEC, sheet=default_sheet())
    return fab, assembly, cli.copies


def _box(box: Box) -> tuple[Decimal, ...]:
    return tuple(Decimal(value) / MM for value in box)


def _inside(x0: Decimal, x1: Decimal, y: Decimal, box: Sequence[Decimal]) -> bool:
    return box[0] - SLACK <= x0 and x1 <= box[2] + SLACK and box[1] - SLACK <= y <= box[3] + SLACK


def _cells(copy: str) -> list[str]:
    """Every line of every cell of the tables of a plot copy."""
    found: list[str] = []
    for table in parse(copy).nodes("table"):
        cells = table.find("cells")
        assert cells is not None
        for cell in cells.nodes("table_cell"):
            found += [line for line in cell.atoms()[0].value.split("\n") if line]
    return found


def _check_page(page: Page, copy: str, layers: str, board_box: Box | None, *options: str) -> None:
    svg = _drawbench.svg_text(copy, layers, "--drill-shape-opt", "0", *options)
    assert svg, f"{page.path}: kicad-cli plotted no SVG of the copy"
    lines = _drawbench.lines(svg)
    wanted = [line for line in _cells(copy) if "${" not in line]  # KiCad resolves a variable itself
    strings = [line[3].replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&") for line in lines]
    assert set(wanted) <= set(strings), sorted(set(wanted) - set(strings))
    blocks = [_box(block.box) for block in page.blocks]
    width, height = AUTO_PAPERS[page.paper]
    obstacles = [_box(box) for box in default_sheet_obstacles(width, height)[1]]
    forbidden = [*obstacles, *([_box(board_box)] if board_box is not None else [])]
    cell_lines = set(wanted)
    checked = 0
    for (x, y, length, _), text in zip(lines, strings, strict=True):
        if text not in cell_lines:
            continue
        left, right = (x, x + length) if not options else (x - length, x)
        holders = [box for box in blocks if _inside(left, right, y, box)]
        if not holders:
            continue  # a footprint text of the same string, outside every block
        checked += 1
        assert not any(_inside(left, right, y, box) for box in forbidden), (page.path, text)
    assert checked >= len(cell_lines), (page.path, checked, len(cell_lines))


def test_both_kinds_are_exported_and_the_drill_check_passes() -> None:
    fab, assembly, _ = drawn()
    issues = [*fab.issues, *assembly.issues]
    print(f"kicad-cli {_probes.version()}: {[(i.code, i.where) for i in issues]}")
    assert not [i for i in issues if i.severity in ("error", "warning")], issues
    assert not [i for i in issues if i.code.startswith("drawing.drill")]
    assert [a.path for a in fab.artifacts] == [
        f"drawings/{NAME}-NPTH-drl_map.pdf",
        f"drawings/{NAME}-PTH-drl_map.pdf",
        f"drawings/{NAME}-drill.rpt",
        f"drawings/{NAME}-fab.pdf",
        f"drawings/{NAME}-front-in1-drl_map.pdf",
    ]
    assert [a.path for a in assembly.artifacts] == [
        f"drawings/{NAME}-assembly-bottom.pdf",
        f"drawings/{NAME}-assembly-top.pdf",
    ]
    assert all(
        a.data.startswith(b"%PDF") for a in (*fab.artifacts, *assembly.artifacts) if a.path.endswith(".pdf")
    )
    assert [(p.side, p.designators_added) for p in assembly.pages] == [("top", 4), ("bottom", 1)]


def test_block_texts_are_inside_their_blocks() -> None:
    fab, assembly, copies = drawn()
    design = read_board(_drawbench.bench_file())
    (page,) = fab.pages
    # the bench board holds its stack-up since c0101 reads it, so the table is drawn
    assert [block.name for block in page.blocks] == ["board", "stackup", "drill", "notes"]
    board_box = fab_board_box(design, _drawbench.bench(), SPEC)
    _check_page(page, copies[page.path], "Edge.Cuts,Dwgs.User", board_box)
    top, bottom = assembly.pages
    assert [block.name for block in top.blocks] == ["notes"] and bottom.blocks == ()
    _check_page(top, copies[top.path], "F.Fab,Edge.Cuts", None)
    mirrored = _drawbench.svg_text(copies[bottom.path], "B.Fab,Edge.Cuts", "--mirror")
    width = AUTO_PAPERS[bottom.paper][0]
    assert "R2" in _drawbench.strings(mirrored)
    assert mirror((160_000_000, 0, 160_000_000, 0), width)[0] == width - 160_000_000
    for x, _, _, text in _drawbench.lines(mirrored):
        if text == "R2":  # the added designator sits where the mirrored part is
            assert abs(x - Decimal(width - 160_000_000) / MM) <= Decimal(1)


def test_no_line_is_wider_than_its_column() -> None:
    fab, _, copies = drawn()
    (page,) = fab.pages
    copy = copies[page.path]
    lines = {
        text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"): length
        for _, _, length, text in _drawbench.lines(_drawbench.svg_text(copy, "Dwgs.User"))
    }
    checked = 0
    for table in parse(copy).nodes("table"):
        widths = [atom.to_nm() for atom in table.find("column_widths").atoms()]  # type: ignore[union-attr]
        cells = table.find("cells").nodes("table_cell")  # type: ignore[union-attr]
        for index, cell in enumerate(cells):
            inner = Decimal(widths[index % len(widths)] - 2_000_000) / MM
            for line in cell.atoms()[0].value.split("\n"):
                if line in lines:
                    checked += 1
                    assert lines[line] <= inner + SLACK, (line, lines[line], inner)
    assert checked > 20


def test_repeat_of_the_drawings() -> None:
    first = {a.path: a for result in _drawbench.exported(0) for a in result.artifacts}
    second = {a.path: a for result in _drawbench.exported(1) for a in result.artifacts}
    assert len(first) == 7 and set(first) == set(second)
    for path, artifact in first.items():
        other = second[path]
        assert content_sha256(artifact.data, artifact.kind) == content_sha256(other.data, other.kind), path
