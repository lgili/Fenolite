# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawing kinds against the fake ``kicad-cli`` (capability manufacturing-exports, "Fabrication
drawing kind" and "Assembly drawing kind"; change c0117). Hermetic."""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from _drawdesign import SHOWN_REF, bench_text
from _fakecli import DRILL, EXPORT_FILES, PDF, calls, drill_report, fake_kicad_cli

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.drawing import read_drill_report
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.exports.drawing_spec import DEFAULT, AssemblySpec, DrawingSpec, FabSpec, PageSpec
from fenolite.exports.drawing_tables import drill_rows
from fenolite.exports.drawings import (
    DRAWING_KINDS,
    EVIDENCE,
    DrawingResult,
    check_drill,
    default_sheet,
    run_assembly_drawing,
    run_fab_drawing,
)
from fenolite.exports.manifest import content_sha256
from fenolite.exports.plan import VOLATILE_PREFIXES, KindResult

PLATED = {"0.300": 3, "1.000": 3}
UNPLATED = {"3.200": 1}
PAIRS = {("F.Cu", "In1.Cu"): {"0.100": 1, "0.200": 1}}


def _files(report: str) -> dict[str, Mapping[str, str]]:
    maps = {
        "{stem}-PTH.drl": DRILL,
        "{stem}-NPTH.drl": DRILL,
        "{stem}-PTH-drl_map.pdf": PDF,
        "{stem}-NPTH-drl_map.pdf": PDF,
        "{stem}-drill.rpt": report,
    }
    return {**EXPORT_FILES, "drill-map": maps}


@pytest.fixture
def board(tmp_path: Path) -> Path:
    path = tmp_path / "project" / "b.kicad_pcb"
    path.parent.mkdir()
    path.write_text(bench_text(10), encoding="utf-8", newline="\n")
    return path


def _cli(tmp_path: Path, report: str | None = None, **options: Any) -> tuple[KicadCli, Path]:
    text = drill_report("b", PLATED, UNPLATED, PAIRS) if report is None else report
    script = fake_kicad_cli(tmp_path / "bin", export_files=_files(text), **options)
    return KicadCli(script), script


def _fab(
    tmp_path: Path, board: Path, spec: DrawingSpec = DEFAULT, **options: Any
) -> tuple[DrawingResult, Path]:
    cli, script = _cli(tmp_path, **options)
    design = read_board(board)
    return run_fab_drawing(cli, board, {}, design=design, spec=spec, sheet=default_sheet()), script


def _assembly(tmp_path: Path, board: Path, spec: DrawingSpec = DEFAULT) -> tuple[DrawingResult, Path]:
    cli, script = _cli(tmp_path)
    design = read_board(board)
    return run_assembly_drawing(cli, board, {}, design=design, spec=spec, sheet=default_sheet()), script


def _runs(script: Path, word: str) -> list[dict[str, Any]]:
    return [call for call in calls(script) if call["args"][:3] == ["pcb", "export", word]]


def _value(args: list[str], flag: str) -> str:
    return args[args.index(flag) + 1]


# -- fabrication drawing


def test_fab_files_of_the_kind(tmp_path: Path, board: Path) -> None:
    before = hashlib.sha256(board.read_bytes()).hexdigest()
    result, script = _fab(tmp_path, board)
    assert isinstance(result, KindResult)
    assert [a.path for a in result.artifacts] == [
        "drawings/b-NPTH-drl_map.pdf",
        "drawings/b-PTH-drl_map.pdf",
        "drawings/b-drill.rpt",
        "drawings/b-fab.pdf",
    ]
    assert {(a.kind, a.layer, a.repeatable) for a in result.artifacts} == {("fab-drawing", None, False)}
    assert not any(a.path.endswith(".drl") for a in result.artifacts)
    assert [i.code for i in result.issues] == []  # the board text holds the stack-up of the bench (c0101)
    assert hashlib.sha256(board.read_bytes()).hexdigest() == before
    (page,) = result.pages
    assert (page.kind, page.path, page.sheet, page.side) == (
        "fab-drawing",
        "drawings/b-fab.pdf",
        "kicad-default",
        None,
    )
    assert [block.name for block in page.blocks] == ["board", "stackup", "drill"] and page.paper == "A3"
    (plot,) = _runs(script, "pdf")
    assert plot["args"][3:] == [
        "--mode-single",
        "--layers",
        "Edge.Cuts,Dwgs.User",
        "--include-border-title",
        "--drill-shape-opt",
        "0",
        "-D",
        "FENOLITE_DRAWING=Fabrication drawing",
        "-o",
        "drawings/b-fab.pdf",
        "b.kicad_pcb",
    ]
    (drill,) = _runs(script, "drill")
    assert drill["args"][3:] == [
        "-o",
        "drawings/",
        "--format",
        "excellon",
        "--excellon-units",
        "mm",
        "--excellon-separate-th",
        "--drill-origin",
        "absolute",
        "--generate-map",
        "--map-format",
        "pdf",
        "--generate-report",
        "b.kicad_pcb",
    ]
    for call in (plot, drill):
        assert not {"--check-zones", "--board-plot-params", "--scale"} & set(call["args"])
    assert drill["files"]["b.kicad_pcb"] == board.read_text(encoding="utf-8")  # the drill run sees the board


def test_fab_copy_holds_the_blocks_and_the_dimensions(tmp_path: Path, board: Path) -> None:
    spec = dataclasses.replace(DEFAULT, fab=FabSpec(title="Fab ${REVISION}", notes=("Note ${TITLE}.",)))
    result, script = _fab(tmp_path, board, spec)
    (plot,) = _runs(script, "pdf")
    assert _value(plot["args"], "-D") == "FENOLITE_DRAWING=Fab ${REVISION}"
    copy = parse(plot["files"]["b.kicad_pcb"])
    (page,) = result.pages
    tables = copy.nodes("table")
    assert len(tables) == len(page.blocks) == 4  # board, stack-up, drill and notes
    for table, block in zip(tables, page.blocks, strict=True):
        first = table.find("cells").nodes("table_cell")[0]  # type: ignore[union-attr]
        start = [atom.to_nm() for atom in first.find("start").atoms()]  # type: ignore[union-attr]
        assert tuple(start) == block.at and '(layer "Dwgs.User")' in dumps(table, style="compact")
    assert "Note ${TITLE}." in dumps(tables[-1], style="compact")  # the variable is left to KiCad
    dimensions = [dumps(node, style="compact") for node in copy.nodes("dimension")]
    assert len(dimensions) == 2
    assert "(pts (xy 100 100) (xy 176 100)) (height -8) (orientation 0)" in dimensions[0]
    assert "(pts (xy 100 100) (xy 100 192)) (height -8) (orientation 1)" in dimensions[1]
    assert all("(precision 2)" in text for text in dimensions)
    assert dumps(copy.find("paper"), style="compact") == f'(paper "{page.paper}")'  # type: ignore[arg-type]
    plain = dataclasses.replace(DEFAULT, fab=FabSpec(dimensions=False, tables=("drill",)))
    _, second = _fab(tmp_path / "again", board, plain)
    again = parse(_runs(second, "pdf")[0]["files"]["b.kicad_pcb"])
    assert again.nodes("dimension") == () and len(again.nodes("table")) == 1


def test_fab_count_that_differs(tmp_path: Path, board: Path) -> None:
    report = drill_report("b", {**PLATED, "0.300": 4}, UNPLATED, PAIRS)
    result, _ = _fab(tmp_path, board, report=report)
    wrong = [i for i in result.issues if i.code == "drawing.drill-mismatch"]
    assert len(wrong) == 1 and wrong[0].severity == "error" and wrong[0].where == "b-PTH.drl"
    for word in ("b-PTH.drl", "0.300", "3", "4"):
        assert word in wrong[0].message


def test_fab_check_follows_the_report() -> None:
    rows = drill_rows(read_board(bench_text(10)))
    good = read_drill_report(drill_report("b", PLATED, UNPLATED, PAIRS))
    assert check_drill(rows, good) == ()
    nine = read_drill_report(drill_report("b", PLATED, UNPLATED, PAIRS, closing=")"))
    assert check_drill(rows, nine) == ()
    for plated, unplated, pairs, where in (
        ({"0.300": 3}, UNPLATED, PAIRS, "b-PTH.drl"),  # the three holes of 1 mm are missing
        (PLATED, {}, PAIRS, "b-NPTH.drl"),
        (PLATED, UNPLATED, {("F.Cu", "In1.Cu"): {"0.100": 2}}, "b-front-in1.drl"),
    ):
        found = check_drill(rows, read_drill_report(drill_report("b", plated, unplated, pairs)))
        assert found and {i.code for i in found} == {"drawing.drill-mismatch"} and found[0].where == where
    assert len(check_drill(rows, read_drill_report(drill_report("b", PLATED, UNPLATED)))) == 0  # no pair file


def test_fab_unreadable_report(tmp_path: Path, board: Path) -> None:
    result, _ = _fab(tmp_path, board, report="Drill report\nCreated on 2026-10-07T00:00:00\n")
    unread = [i for i in result.issues if i.code == "drawing.drill-report-unread"]
    assert len(unread) == 1 and unread[0].severity == "warning"
    assert "drawings/b-fab.pdf" in [a.path for a in result.artifacts]  # the table stays
    assert [block.name for block in result.pages[0].blocks] == ["board", "stackup", "drill"]


def test_fab_no_room_runs_nothing(tmp_path: Path, board: Path) -> None:
    spec = dataclasses.replace(DEFAULT, page=PageSpec(paper="A5"))
    result, script = _fab(tmp_path, board, spec)
    assert [i.code for i in result.issues if i.severity == "error"] == ["drawing.no-room"]
    assert result.artifacts == () and result.pages == () and _runs(script, "pdf") == []


def test_fab_failed_plot(tmp_path: Path, board: Path) -> None:
    result, _ = _fab(tmp_path, board, export_fail=("pdf",))
    assert [i.code for i in result.issues if i.severity == "error"] == ["export.failed"]
    assert result.artifacts == ()


def test_fab_dates_do_not_change_the_content_hash() -> None:
    assert VOLATILE_PREFIXES["fab-drawing"] == (b"/CreationDate", b"Created on")
    assert VOLATILE_PREFIXES["assembly-drawing"] == (b"/CreationDate",)
    one, two = PDF.encode("latin-1"), PDF.replace("20261007", "20270101").encode("latin-1")
    report = drill_report("b", PLATED, UNPLATED, PAIRS).encode()
    later = report.replace(b"Created on 2026-10-07", b"Created on 2027-01-01")
    assert one != two and report != later
    for kind in DRAWING_KINDS:
        assert content_sha256(one, kind) == content_sha256(two, kind)
    assert content_sha256(report, "fab-drawing") == content_sha256(later, "fab-drawing")
    changed = report.replace(b"(3 holes))", b"(5 holes))")
    assert content_sha256(report, "fab-drawing") != content_sha256(changed, "fab-drawing")
    assert EVIDENCE.level.value == "KICAD-VERIFIED"
    assert set(EVIDENCE.hypotheses) == {"H-K-DRAW-ITEMS", "H-K-DRAW-PAGE", "H-K-DRAW-DRILL"}


# -- assembly drawings


def test_assembly_default_arguments(tmp_path: Path, board: Path) -> None:
    result, script = _assembly(tmp_path, board)
    assert [a.path for a in result.artifacts] == [
        "drawings/b-assembly-bottom.pdf",
        "drawings/b-assembly-top.pdf",
    ]
    assert {(a.kind, a.layer) for a in result.artifacts} == {("assembly-drawing", None)}
    top, bottom = _runs(script, "pdf")
    assert top["args"][3:] == [
        "--mode-single",
        "--layers",
        "F.Fab,Edge.Cuts",
        "--include-border-title",
        "--drill-shape-opt",
        "0",
        "-D",
        "FENOLITE_DRAWING=Assembly drawing, top side",
        "--exclude-value",
        "--crossout-DNP-footprints-on-fab-layers",
        "-o",
        "drawings/b-assembly-top.pdf",
        "b.kicad_pcb",
    ]
    assert _value(bottom["args"], "--layers") == "B.Fab,Edge.Cuts" and "--mirror" in bottom["args"]
    assert _value(bottom["args"], "-D") == "FENOLITE_DRAWING=Assembly drawing, bottom side"
    assert _value(bottom["args"], "-o") == "drawings/b-assembly-bottom.pdf"
    assert "--exclude-value" in bottom["args"] and "--crossout-DNP-footprints-on-fab-layers" in bottom["args"]
    assert [(p.side, p.designators_added) for p in result.pages] == [("top", 4), ("bottom", 1)]


def test_assembly_options_of_the_spec(tmp_path: Path, board: Path) -> None:
    spec = dataclasses.replace(DEFAULT, assembly=AssemblySpec(values=True, pads=True, dnp="hide"))
    result, script = _assembly(tmp_path, board, spec)
    runs = _runs(script, "pdf")
    assert len(runs) == 2
    for run in runs:
        assert "--exclude-value" not in run["args"]
        assert "--sketch-pads-on-fab-layers" in run["args"]
        assert "--hide-DNP-footprints-on-fab-layers" in run["args"]
        assert "--crossout-DNP-footprints-on-fab-layers" not in run["args"]
    assert result.pages[0].designators_added == 3  # the do-not-populate part gets none when it is hidden
    shown = dataclasses.replace(DEFAULT, assembly=AssemblySpec(dnp="show", sides=("top",)))
    _, second = _assembly(tmp_path / "again", board, shown)
    (only,) = _runs(second, "pdf")
    assert not [arg for arg in only["args"] if "DNP" in arg]


def test_assembly_no_part_on_the_bottom(tmp_path: Path) -> None:
    path = tmp_path / "project" / "b.kicad_pcb"
    path.parent.mkdir()
    path.write_text(bench_text(10, bottom=False), encoding="utf-8", newline="\n")
    result, script = _assembly(tmp_path, path)
    assert [a.path for a in result.artifacts] == ["drawings/b-assembly-top.pdf"]
    empty = [i for i in result.issues if i.code == "drawing.side-empty"]
    assert len(empty) == 1 and (empty[0].severity, empty[0].where) == ("info", "bottom")
    assert len(_runs(script, "pdf")) == 1
    top_only = dataclasses.replace(DEFAULT, assembly=AssemblySpec(sides=("top",)))
    again, _ = _assembly(tmp_path / "again", path, top_only)
    assert not [i for i in again.issues if i.code == "drawing.side-empty"]  # a side that was not asked for


def test_assembly_references_added_where_none_is_shown(tmp_path: Path, board: Path) -> None:
    result, script = _assembly(tmp_path, board)
    top, bottom = (parse(run["files"]["b.kicad_pcb"]) for run in _runs(script, "pdf"))

    def added(copy: Node) -> dict[str, str]:
        return {node.atoms()[0].value: dumps(node, style="compact") for node in copy.nodes("gr_text")}

    front = added(top)
    assert sorted(front) == ["H1", "J1", "R1", "R3"] and SHOWN_REF not in front
    assert '(at 120 120 0) (layer "F.Fab")' in front["R1"]  # the centre of the courtyard box of R1
    assert "(size 1 1)" in front["R1"] and "mirror" not in front["R1"]
    back = added(bottom)
    assert list(back) == ["R2"] and '(at 160 120 0) (layer "B.Fab")' in back["R2"]
    assert "(justify mirror)" in back["R2"]
    counts = [i for i in result.issues if i.code == "drawing.designators-added"]
    assert [(i.where, i.severity) for i in counts] == [("top", "info"), ("bottom", "info")]
    assert counts[0].message.startswith("4 references") and counts[1].message.startswith("1 references")
    off = dataclasses.replace(DEFAULT, assembly=AssemblySpec(designators=False, designator_size=2_000_000))
    quiet, second = _assembly(tmp_path / "again", board, off)
    assert not [i for i in quiet.issues if i.code == "drawing.designators-added"]
    assert parse(_runs(second, "pdf")[0]["files"]["b.kicad_pcb"]).nodes("gr_text") == ()


def test_assembly_notes_go_on_the_top_page(tmp_path: Path, board: Path) -> None:
    spec = dataclasses.replace(DEFAULT, assembly=AssemblySpec(notes=("Glue the header.",)))
    result, script = _assembly(tmp_path, board, spec)
    top, bottom = (parse(run["files"]["b.kicad_pcb"]) for run in _runs(script, "pdf"))
    (table,) = top.nodes("table")
    assert '(layer "F.Fab")' in dumps(table, style="compact") and "Glue the header." in dumps(table)
    assert bottom.nodes("table") == ()
    assert [[b.name for b in page.blocks] for page in result.pages] == [["notes"], []]
