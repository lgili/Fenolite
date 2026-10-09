# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawing kinds of ``fenolite export``: a fabrication drawing and assembly drawings that
``kicad-cli`` plots from copies of the board (capability manufacturing-exports, "Fabrication drawing
kind" and "Assembly drawing kind"; change c0117; user guide ``docs/drawings.md``).

Each page is one ``pcb export pdf --mode-single`` run on a plot copy (``backends.kicad.drawing``) that
holds the page's tables, dimensions and added designators as board items. The fabrication kind also
runs ``pcb export drill`` for KiCad's drill maps and report, and compares its drill table with that
report on every run: a drawing never states a count the drill files do not hold.

The kinds are not rows of ``plan.KINDS``: each makes several runs, and no preset reaches them.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from fenolite.backends.base import PlotDimension, PlotItem, PlotText
from fenolite.backends.kicad import drawing
from fenolite.backends.kicad import versions as kicad_versions
from fenolite.backends.kicad.cli import CliRun, KicadCli
from fenolite.backends.kicad.frame import placed_extents
from fenolite.backends.kicad.sexpr import parse
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue
from fenolite.core.units import Nm
from fenolite.exports.codes import issue
from fenolite.exports.drawing_layout import (
    BOARD,
    Box,
    Obstacles,
    PageLayout,
    Placed,
    choose_paper,
    join,
    mirror,
)
from fenolite.exports.drawing_spec import AUTO, DrawingSpec
from fenolite.exports.drawing_tables import (
    Block,
    DrillRow,
    drill_rows,
    fab_blocks,
    mm_text,
    notes_block,
    outline_box,
)
from fenolite.exports.plan import Artifact, KindResult
from fenolite.model.design import Design

EVIDENCE = drawing.EVIDENCE
"""The level of both drawing kinds: ``INFERRED`` until ``H-K-DRAW-ITEMS``, ``H-K-DRAW-PAGE`` and
``H-K-DRAW-DRILL`` hold on 9.0.x and 10.0.x. It covers that KiCad draws the items Fenolite writes where
the layout puts them and that the drill table agrees with KiCad's report; the tables state model values."""
FAB, ASSEMBLY = "fab-drawing", "assembly-drawing"
DRAWING_KINDS = (FAB, ASSEMBLY)
"""The drawing kinds, in the order they run and are listed."""
REPEAT = "content"
"""The repeat class of both kinds: two exports share their bytes without the date lines."""
FOLDER = "drawings"
FAB_LAYERS = ("Edge.Cuts", "Dwgs.User")
SIDE_LAYER = {"top": "F.Fab", "bottom": "B.Fab"}
OUTLINE = "Edge.Cuts"
SHEET_FILE = "fenolite-drawing-sheet.kicad_wks"
"""The name of the specification's drawing sheet in the run folder."""
TITLE_VARIABLE = "FENOLITE_DRAWING"
DRILL_OPTIONS = (
    "--format",
    "excellon",
    "--excellon-units",
    "mm",
    "--excellon-separate-th",
    "--drill-origin",
    "absolute",
) + ("--generate-map", "--map-format", "pdf", "--generate-report")
MAP_SUFFIX = "-drl_map.pdf"
REPORT_SUFFIX = "-drill.rpt"
UM = 1_000


@dataclass(frozen=True, slots=True)
class Sheet:
    """The drawing sheet of the pages: where it comes from (``spec``, ``project`` or ``kicad-default``),
    what it takes of a page of a given size, and for a sheet of the specification its ``.kicad_wks``
    bytes. ``cmd_export`` builds it, so that this package needs no drawing-sheet code."""

    source: str
    obstacles: Callable[[Nm, Nm], Obstacles]
    data: bytes | None = None


@dataclass(frozen=True, slots=True)
class Page:
    """One page of a drawing, as ``result.drawings`` describes it."""

    kind: str
    path: str
    paper: str
    portrait: bool
    sheet: str
    blocks: tuple[Placed, ...] = ()
    side: str | None = None
    designators_added: int | None = None


@dataclass(frozen=True, slots=True)
class DrawingResult(KindResult):
    """A drawing kind's run: the artefacts and issues of a ``KindResult`` and the pages produced."""

    pages: tuple[Page, ...] = ()


def default_sheet() -> Sheet:
    """KiCad's own sheet, which a project that names none is plotted with."""

    def obstacles(width: Nm, height: Nm) -> Obstacles:
        margin, boxes = drawing.default_sheet_obstacles(width, height)
        return Obstacles(margin, boxes)

    return Sheet("kicad-default", obstacles)


def board_major(board_text: str, fallback: int) -> int:
    """The major of the board's format, which decides the nodes of its plot copies."""
    try:
        major = kicad_versions.inspect(parse(board_text)).major
    except (FormatError, ValueError):
        return fallback
    return fallback if major is None else max(9, min(major, 10))


def _box_text(box: Box) -> str:
    return f"({mm_text(box[0])}, {mm_text(box[1])}) to ({mm_text(box[2])}, {mm_text(box[3])}) mm"


def no_room(page: str, layout: PageLayout, requested: str) -> Issue:
    """``drawing.no-room`` for a page whose paper does not hold the board box or a block."""
    problem = layout.problem
    assert problem is not None
    what = "the board box" if problem.what == BOARD else f"the block {problem.what}"
    where = f" from {_box_text(problem.box)}" if problem.box is not None else ""
    if requested == AUTO:
        message = f"{page}: no paper from A4 to A0 holds {what}{where} at 1:1"
    else:
        smallest = (
            f"the smallest paper that holds the page is {problem.smallest}"
            if problem.smallest
            else "no paper from A4 to A0 holds it"
        )
        message = f"{page}: {layout.paper} does not hold {what}{where} at 1:1; {smallest}"
    hint = (
        "move the board onto the page in KiCad: a drawing is plotted at 1:1 where the board file puts it"
        if problem.what == BOARD and not problem.smallest
        else 'set [page] paper in the drawing specification, or leave it "auto"; a fixed corner (at) '
        "must be free of the board, the sheet and the other blocks"
    )
    return issue("drawing.no-room", message, where=problem.what, hint=hint)


def _first_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0].replace("<tmp>/", "").replace("<tmp>", ".") if lines else ""


def _failure(cli: KicadCli, run: CliRun, where: str, wrote: bool) -> Issue | None:
    if run.outcome == "timeout":
        message = f"kicad-cli timed out after {cli.timeout:g} s"
        return issue("export.failed", message, where=where, retryable=True)
    if run.returncode != 0 or not wrote:
        detail = _first_line(run.stderr or run.stdout) or "kicad-cli wrote no file"
        return issue("export.failed", f"exit {run.returncode}: {detail}", where=where)
    return None


def page_arguments(
    *, layers: Sequence[str], title: str, out: str, sheet: Sheet, options: Sequence[str] = ()
) -> list[str]:
    """The ``kicad-cli`` arguments of one page without the board's name. No scale option is passed (a
    page is 1:1), and neither ``--check-zones`` nor ``--board-plot-params``."""
    args = ["pcb", "export", "pdf", "--mode-single", "--layers", ",".join(layers), "--include-border-title"]
    args += ["--drill-shape-opt", "0", "-D", f"{TITLE_VARIABLE}={title}"]
    if sheet.data is not None:
        args += ["--drawing-sheet", SHEET_FILE]
    return [*args, *options, "-o", out]


def _plot(
    cli: KicadCli,
    board: Path,
    files: Mapping[str, Path],
    copy: str,
    args: Sequence[str],
    sheet: Sheet,
    kind: str,
    out: str,
) -> tuple[Artifact | None, Issue | None, set[str]]:
    given: dict[str, Path | bytes] = {name: Path(path) for name, path in files.items()}
    given[board.name] = copy.encode("utf-8")
    if sheet.data is not None:
        given[SHEET_FILE] = sheet.data
    run = cli.run([*args, board.name], files=given, folders=(FOLDER,))
    others = {name for name in run.outputs if name != out}
    failure = _failure(cli, run, kind, out in run.outputs)
    if failure is not None:
        return None, failure, others
    return Artifact(out, kind, None, run.outputs[out], False), None, others


def _micrometres(value: Nm) -> Nm:
    """``value`` rounded to the micrometre, half to even: the three decimals a report prints."""
    quotient, rest = divmod(value, UM)
    up = rest * 2 > UM or (rest * 2 == UM and quotient % 2 == 1)
    return (quotient + (1 if up else 0)) * UM


def check_drill(rows: Sequence[DrillRow], report: drawing.DrillReport) -> tuple[Issue, ...]:
    """The drill table against KiCad's report: per drill file, the hole count of each diameter must be
    the table's for that file's holes (plated through, unplated through, or one layer pair). The report
    counts a slot with the round holes of its width and prints three decimals, so the table's rows are
    joined the same way. A report without a drill file gives one warning, and the table stays."""
    if not report.files:
        return (
            issue(
                "drawing.drill-report-unread",
                "KiCad's drill report names no drill file: the drill table was not checked against it",
                where="drill",
                hint="open drawings/<board>-drill.rpt; a new kicad-cli may write the report another way",
            ),
        )
    issues: list[Issue] = []
    for found in report.files:
        if found.span is not None:
            pair = set(found.span)
            wanted = [row for row in rows if not row.through and {row.first, row.last} == pair]
        elif found.plated is None:
            continue
        else:
            wanted = [row for row in rows if row.through and row.plated == found.plated]
        table: Counter[Nm] = Counter()
        for row in wanted:
            table[_micrometres(row.drill)] += row.count
        tool: Counter[Nm] = Counter()
        for diameter, count in found.tools:
            tool[diameter] += count
        for diameter in sorted(set(table) | set(tool)):
            if table[diameter] != tool[diameter]:
                issues.append(
                    issue(
                        "drawing.drill-mismatch",
                        f"{found.name}: the drill table has {table[diameter]} holes of "
                        f"{mm_text(diameter)} mm, KiCad's drill report has {tool[diameter]}",
                        where=found.name,
                        hint="the drawing would state a count the drill files do not hold; report this "
                        "board to Fenolite",
                    )
                )
    return tuple(issues)


def fab_board_box(design: Design, board_text: str, spec: DrawingSpec) -> Box | None:
    """The board box of the fabrication page: the outline's box, grown at the top and at the left for
    the dimensions, joined with the extent of the root items on ``Dwgs.User``."""
    box = outline_box(design)
    if box is not None and spec.fab.dimensions:
        grow = spec.fab.dimension_offset + 2 * spec.page.text_size
        box = (box[0] - grow, box[1] - grow, box[2], box[3])
    return join(box, drawing.layer_extent(board_text, "Dwgs.User"))


def _dimensions(design: Design, spec: DrawingSpec) -> list[PlotItem]:
    box = outline_box(design)
    if box is None or not spec.fab.dimensions:
        return []
    offset, precision, size = -spec.fab.dimension_offset, spec.fab.dimension_precision, spec.page.text_size
    layer = "Dwgs.User"
    top_left, top_right, bottom_left = Point(box[0], box[1]), Point(box[2], box[1]), Point(box[0], box[3])
    return [
        PlotDimension("fab:width", layer, top_left, top_right, offset, "horizontal", precision, size),
        PlotDimension("fab:height", layer, top_left, bottom_left, offset, "vertical", precision, size),
    ]


def _tables(page: str, blocks: Sequence[Block], placed: Sequence[Placed], layer: str) -> list[PlotItem]:
    corners = {item.name: item.at for item in placed}
    return [
        _named(block, page).plot(Point(*corners[block.name]), layer)
        for block in blocks
        if block.name in corners
    ]


def _named(block: Block, page: str) -> Block:
    return Block(
        f"{page}:{block.name}", block.rows, block.column_widths, block.row_heights, block.text_size,
        block.border,
    )  # fmt: skip


def run_fab_drawing(
    cli: KicadCli,
    board: Path,
    files: Mapping[str, Path],
    *,
    design: Design,
    spec: DrawingSpec,
    sheet: Sheet,
) -> DrawingResult:
    """The fabrication drawing of ``board`` (``files`` are the rest of its copy set): the page, KiCad's
    drill maps and its drill report. A page that has no room, or a drill table that differs from the
    report, gives an error and the caller writes nothing."""
    board = Path(board)
    stem = board.stem
    text = board.read_text(encoding="utf-8")
    blocks, notes = fab_blocks(design, spec)
    issues: list[Issue] = list(notes)
    box = fab_board_box(design, text, spec)
    layout = choose_paper(
        blocks,
        paper=spec.page.paper,
        portrait=spec.page.portrait,
        board_box=lambda width: box,
        obstacles=sheet.obstacles,
        gap=spec.page.gap,
        fixed=dict(spec.fab.at),
    )
    if layout.problem is not None:
        issues.append(no_room("fabrication drawing", layout, spec.page.paper))
        return DrawingResult(issues=tuple(issues))
    items = [*_tables("fab", blocks, layout.placed, "Dwgs.User"), *_dimensions(design, spec)]
    copy = drawing.plot_copy(
        text,
        items,
        paper=layout.paper,
        portrait=layout.portrait,
        major=board_major(text, cli.major()),
        layers=("Dwgs.User",),
    )
    out = f"{FOLDER}/{stem}-fab.pdf"
    args = page_arguments(layers=FAB_LAYERS, title=spec.fab.title, out=out, sheet=sheet)
    page, failure, tool_writes = _plot(cli, board, files, copy, args, sheet, FAB, out)
    if page is None:
        assert failure is not None
        return DrawingResult(issues=(*issues, failure), tool_writes=tuple(sorted(tool_writes)))
    given: dict[str, Path | bytes] = {board.name: board, **{n: Path(p) for n, p in files.items()}}
    drill = ["pcb", "export", "drill", "-o", f"{FOLDER}/", *DRILL_OPTIONS, board.name]
    run = cli.run(drill, files=given, folders=(FOLDER,))
    report_name = f"{FOLDER}/{stem}{REPORT_SUFFIX}"
    kept = {
        name: data
        for name, data in run.outputs.items()
        if name.startswith(f"{FOLDER}/") and (name.endswith(MAP_SUFFIX) or name == report_name)
    }
    tool_writes |= {name for name in run.outputs if not name.startswith(f"{FOLDER}/")}
    failure = _failure(cli, run, FAB, bool(kept))
    if failure is not None:
        return DrawingResult(issues=(*issues, failure), tool_writes=tuple(sorted(tool_writes)))
    report = drawing.read_drill_report(kept.get(report_name, b"").decode("utf-8", "replace"))
    issues += check_drill(drill_rows(design), report)
    artifacts = [page, *(Artifact(name, FAB, None, data, False) for name, data in kept.items())]
    described = Page(FAB, out, layout.paper, layout.portrait, sheet.source, layout.placed)
    return DrawingResult(
        artifacts=tuple(sorted(artifacts, key=lambda a: a.path)),
        issues=tuple(issues),
        tool_writes=tuple(sorted(tool_writes)),
        pages=(described,),
    )


def assembly_options(spec: DrawingSpec) -> list[str]:
    """The plot options of both assembly pages."""
    options: list[str] = [] if spec.assembly.values else ["--exclude-value"]
    if spec.assembly.pads:
        options.append("--sketch-pads-on-fab-layers")
    if spec.assembly.dnp == "crossout":
        options.append("--crossout-DNP-footprints-on-fab-layers")
    elif spec.assembly.dnp == "hide":
        options.append("--hide-DNP-footprints-on-fab-layers")
    return options


def _ring_box(rings: Sequence[Sequence[Point]]) -> Box | None:
    points = [point for ring in rings for point in ring]
    if not points:
        return None
    return (min(p.x for p in points), min(p.y for p in points), max(p.x for p in points),
            max(p.y for p in points))  # fmt: skip


def side_content(design: Design, side: str, spec: DrawingSpec) -> tuple[list[PlotItem], Box | None, int]:
    """The designators a side's page adds, the box of its parts' courtyards, and how many parts it has.

    A footprint that shows no reference on the side's fabrication layer gets a text of its reference at
    the centre of its courtyard box, or at its position without a courtyard; under ``dnp = "hide"`` a
    do-not-populate part gets none."""
    board = design.board
    if board is None:
        return [], None, 0
    layer = SIDE_LAYER[side]
    refs = {component.id: component.ref for component in design.circuit.components}
    extents = {extent.footprint_id: extent for extent in placed_extents(design)}
    items: list[PlotItem] = []
    box: Box | None = None
    count = 0
    for footprint in board.footprints:
        if footprint.side != side:
            continue
        count += 1
        extent = extents.get(footprint.id)
        rings = () if extent is None else (extent.front if side == "top" else extent.back)
        court = _ring_box(rings)
        box = join(box, court)
        ref = refs.get(footprint.component_id, "")
        if not spec.assembly.designators or not ref or drawing.shows_reference(footprint, layer):
            continue
        if spec.assembly.dnp == "hide" and "dnp" in footprint.attributes:
            continue
        centre = (
            footprint.position
            if court is None
            else Point((court[0] + court[2]) // 2, (court[1] + court[3]) // 2)
        )
        name = f"assembly-{side}:designator:{footprint.id}"
        items.append(PlotText(name, ref, layer, centre, spec.assembly.designator_size))
    return items, box, count


def run_assembly_drawing(
    cli: KicadCli,
    board: Path,
    files: Mapping[str, Path],
    *,
    design: Design,
    spec: DrawingSpec,
    sheet: Sheet,
) -> DrawingResult:
    """The assembly drawings of ``board``: a top page and, when a part sits on the bottom, a mirrored
    bottom page. The notes of the specification go on the top page."""
    board = Path(board)
    stem = board.stem
    text = board.read_text(encoding="utf-8")
    outline = outline_box(design)
    options = assembly_options(spec)
    artifacts: list[Artifact] = []
    issues: list[Issue] = []
    pages: list[Page] = []
    tool_writes: set[str] = set()
    for side in ("top", "bottom"):
        if side not in spec.assembly.sides:
            continue
        layer = SIDE_LAYER[side]
        designators, courts, parts = side_content(design, side, spec)
        if side == "bottom" and parts == 0:
            issues.append(
                issue(
                    "drawing.side-empty",
                    "no part sits on the bottom: there is no bottom assembly drawing",
                    where="bottom",
                )
            )
            continue
        box = join(outline, courts, drawing.layer_extent(text, layer))
        mirrored = side == "bottom"
        note = notes_block(spec.assembly.notes, spec.page.notes_width, spec.page.text_size)
        blocks = [note] if note is not None and side == "top" else []

        def board_box(width: Nm, box: Box | None = box, mirrored: bool = mirrored) -> Box | None:
            return mirror(box, width) if box is not None and mirrored else box

        layout = choose_paper(
            blocks,
            paper=spec.page.paper,
            portrait=spec.page.portrait,
            board_box=board_box,
            obstacles=sheet.obstacles,
            gap=spec.page.gap,
            fixed=dict(spec.assembly.at) if side == "top" else None,
        )
        if layout.problem is not None:
            issues.append(no_room(f"assembly drawing, {side} side", layout, spec.page.paper))
            continue
        items = [*_tables(f"assembly-{side}", blocks, layout.placed, layer), *designators]
        copy = drawing.plot_copy(
            text,
            items,
            paper=layout.paper,
            portrait=layout.portrait,
            major=board_major(text, cli.major()),
            layers=(layer,),
        )
        out = f"{FOLDER}/{stem}-assembly-{side}.pdf"
        title = spec.assembly.title_top if side == "top" else spec.assembly.title_bottom
        extra = [*options, *(["--mirror"] if mirrored else [])]
        args = page_arguments(layers=(layer, OUTLINE), title=title, out=out, sheet=sheet, options=extra)
        page, failure, others = _plot(cli, board, files, copy, args, sheet, ASSEMBLY, out)
        tool_writes |= others
        if page is None:
            assert failure is not None
            issues.append(failure)
            continue
        artifacts.append(page)
        if designators:
            issues.append(
                issue(
                    "drawing.designators-added",
                    f"{len(designators)} references were added to the {side} assembly drawing: their "
                    f"footprints show none on {layer}",
                    where=side,
                )
            )
        pages.append(
            Page(
                ASSEMBLY,
                out,
                layout.paper,
                layout.portrait,
                sheet.source,
                layout.placed,
                side,
                len(designators),
            )  # fmt: skip
        )
    return DrawingResult(
        artifacts=tuple(sorted(artifacts, key=lambda a: a.path)),
        issues=tuple(issues),
        tool_writes=tuple(sorted(tool_writes)),
        pages=tuple(pages),
    )


RUNNERS = {FAB: run_fab_drawing, ASSEMBLY: run_assembly_drawing}

__all__ = [
    "ASSEMBLY",
    "DRAWING_KINDS",
    "EVIDENCE",
    "FAB",
    "FOLDER",
    "REPEAT",
    "RUNNERS",
    "DrawingResult",
    "Page",
    "Sheet",
    "assembly_options",
    "board_major",
    "check_drill",
    "default_sheet",
    "fab_board_box",
    "no_room",
    "page_arguments",
    "run_assembly_drawing",
    "run_fab_drawing",
    "side_content",
]
