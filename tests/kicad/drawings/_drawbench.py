# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The bench and the probes of the drawing kinds (change c0117; capability kicad-oracle, "Drawing facts
are probed"; hypotheses ``H-K-DRAW-ITEMS``, ``-TEXT``, ``-PAGE``, ``-SHEET``, ``-DRILL``, ``-ASSEMBLY``,
``-REPEAT`` and ``-LAYER``).

The subject is the authored bench of ``tests/_drawdesign.py``, written by ``write_board`` for the major
of the running ``kicad-cli``. A probe plots a copy of it and reads the searchable texts and the stroked
paths of the SVG, or the PDF, through the runner. Each probe has a control: the same plot without the
item, the option or the variable must give the other reading, else the probe is ``inconclusive``.
"""

from __future__ import annotations

import re
import tempfile
import time
import zlib
from collections.abc import Callable, Sequence
from decimal import Decimal
from functools import cache
from pathlib import Path

from _boards import FIXTURE
from _drawdesign import DNP_REF, NAME, bench_design, bench_text
from _svg import SheetSvg, read_sheet_svg

from fenolite.backends.base import PlotDimension, PlotItem, PlotTable, PlotText
from fenolite.backends.kicad.cli import CliRun, KicadCli
from fenolite.backends.kicad.drawing import default_sheet_obstacles, plot_copy, read_drill_report
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.core.coords import Point
from fenolite.exports.drawing_layout import AUTO_PAPERS
from fenolite.exports.drawing_spec import DEFAULT, DrawingSpec
from fenolite.exports.drawing_tables import GLYPH_BOUND, GLYPH_SET, LINE_PITCH, drill_rows, text_width
from fenolite.exports.drawings import (
    DRILL_OPTIONS,
    DrawingResult,
    check_drill,
    default_sheet,
    run_assembly_drawing,
    run_fab_drawing,
)
from fenolite.exports.manifest import content_sha256

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
MM = 1_000_000
SIZE = 1_500_000
BOARD = f"{NAME}.kicad_pcb"
PAUSE = 1.1
"""Seconds between two runs that are compared: more than the one-second resolution of the dates."""
TOLERANCE = Decimal("0.01")
NOTE = " ".join(["Fabricate", "to", "the", "class", "that", "the", "order", "states;"] * 6)[:227]
SHEET = (
    '(kicad_wks (version 20231118) (generator "fenolite-tests") (setup (textsize 1.5 1.5) (linewidth 0.15)'
    " (textlinewidth 0.15) (left_margin 10) (right_margin 10) (top_margin 10) (bottom_margin 10))"
    ' (tbtext "${FENOLITE_DRAWING}" (name "") (pos 50 20)))\n'
)
"""An authored drawing sheet whose one text shows the variable every drawing page defines."""
_TEXT = re.compile(r'<text x="([-\d.]+)" y="([-\d.]+)"\s+textLength="([-\d.]+)"[^>]*>([^<]*)</text>')
_STREAM = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.S)


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def major() -> int:
    return runner().major()


@cache
def workspace() -> Path:
    return Path(tempfile.mkdtemp(prefix="fenolite-drawings-"))


@cache
def bench() -> str:
    return bench_text(major())


@cache
def bench_file() -> Path:
    path = workspace() / "bench" / BOARD
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(bench(), encoding="utf-8", newline="\n")
    return path


def with_nodes(text: str, *nodes: str) -> str:
    """``text`` with root nodes added by token edit, before the closing parenthesis."""
    return text.rstrip()[:-1] + "\n" + "\n".join(nodes) + "\n)\n"


def copy(items: Sequence[PlotItem], *, layers: Sequence[str] = ("Dwgs.User",), paper: str = "A3") -> str:
    return plot_copy(bench(), list(items), paper=paper, major=major(), layers=layers)


def export(
    text: str,
    kind: str,
    layers: str,
    *options: str,
    sheet: bool = False,
    files: dict[str, bytes] | None = None,
) -> CliRun:
    """``pcb export <kind> --mode-single`` of a board text; without ``sheet`` an SVG leaves the drawing
    sheet out, and a PDF never draws it."""
    args = ["pcb", "export", kind, "--mode-single", "--layers", layers, *options]
    if kind == "svg" and not sheet:
        args.append("--exclude-drawing-sheet")
    if kind == "pdf" and sheet:
        args.append("--include-border-title")
    given: dict[str, Path | bytes] = {BOARD: text.encode("utf-8"), **(files or {})}
    return runner().run([*args, "-o", f"out.{kind}", BOARD], files=given)


def svg_text(
    text: str, layers: str, *options: str, sheet: bool = False, files: dict[str, bytes] | None = None
) -> str:
    run = export(text, "svg", layers, *options, sheet=sheet, files=files)
    return run.outputs.get("out.svg", b"").decode("utf-8", "replace") if run.returncode == 0 else ""


def strings(svg: str) -> list[str]:
    return [found[3] for found in _TEXT.findall(svg)]


def lines(svg: str) -> list[tuple[Decimal, Decimal, Decimal, str]]:
    """The searchable texts of an SVG: x, y, length and string of each drawn line."""
    return [(Decimal(x), Decimal(y), Decimal(length), text) for x, y, length, text in _TEXT.findall(svg)]


def marks(svg: str) -> int:
    """How many elements an SVG draws: paths and circles."""
    return len(re.findall(r"<(?:path|circle)\b", svg))


def sheet_svg(text: str, layers: str, *options: str, sheet: bool = False) -> SheetSvg | None:
    found = svg_text(text, layers, *options, sheet=sheet)
    return read_sheet_svg(found) if found else None


def has_segment(svg: SheetSvg, x1: Decimal, y1: Decimal, x2: Decimal, y2: Decimal) -> bool:
    def near(a: Decimal, b: Decimal) -> bool:
        return abs(a - b) <= TOLERANCE

    return any(
        (near(s.x1, x1) and near(s.y1, y1) and near(s.x2, x2) and near(s.y2, y2))
        or (near(s.x1, x2) and near(s.y1, y2) and near(s.x2, x1) and near(s.y2, y1))
        for s in svg.paths
    )


def shown_texts(data: bytes) -> int:
    """How many text-showing operators the page streams of a PDF hold."""
    count = 0
    for raw in _STREAM.findall(data):
        try:
            count += len(re.findall(rb"\bTj\b", zlib.decompress(raw)))
        except zlib.error:
            continue
    return count


def _seen(wanted: Sequence[str], svg: str, control: str) -> str:
    """``present`` when every wanted string is drawn, ``absent`` when none is; the control must draw none."""
    if not svg or not control or any(text in strings(control) for text in wanted):
        return "inconclusive"
    found = [text in strings(svg) for text in wanted]
    return "present" if all(found) else "absent" if not any(found) else "inconclusive"


TABLE = PlotTable(
    "probe:table", "Dwgs.User", Point(200 * MM, 20 * MM), (20 * MM, 30 * MM, 30 * MM), (6 * MM, 6 * MM),
    (("Cell A1", "Cell B1", "Cell C1"), ("Cell A2", "Cell B2", "Cell C2")), SIZE,
)  # fmt: skip


def _gr_text(text: str, x: int, y: int, n: int, *, size: str = "1.5", layer: str = "Dwgs.User",
             justify: str = "(justify left top)") -> str:  # fmt: skip
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    thickness = Decimal(size) * 15 / 100
    return (
        f'(gr_text "{escaped}" (at {x} {y} 0) (layer "{layer}") (uuid "d0a00000-0000-4000-8000-{n:012d}")'
        f" (effects (font (size {size} {size}) (thickness {thickness})) {justify}))"
    )


# -- items (H-K-DRAW-ITEMS)


def table() -> str:
    wanted = [cell for row in TABLE.cells for cell in row]
    return _seen(wanted, svg_text(copy([TABLE]), "Dwgs.User"), svg_text(copy([]), "Dwgs.User"))


def textbox() -> str:
    knockout = " (knockout no)" if major() >= 10 else ""
    box = (
        '(gr_text_box "Box text" (start 200 20) (end 270 40) (margins 1 1 1 1) (layer "Dwgs.User")'
        ' (uuid "d0a00000-0000-4000-8000-000000000101") (effects (font (size 1.5 1.5) (thickness 0.225))'
        f" (justify left top)) (border yes) (stroke (width 0.1) (type solid)){knockout})"
    )
    return _seen(
        ["Box text"], svg_text(with_nodes(bench(), box), "Dwgs.User"), svg_text(bench(), "Dwgs.User")
    )


def dimension() -> str:
    """The text KiCad computes from the two points is drawn, not the cache text that was written."""
    item = PlotDimension(
        "probe:width", "Dwgs.User", Point(100 * MM, 100 * MM), Point(176 * MM, 100 * MM), -8 * MM,
        "horizontal", 2, SIZE,
    )  # fmt: skip
    text = copy([item]).replace('"76.00 mm"', '"9 mm"')
    drawn = svg_text(text, "Dwgs.User")
    if "9 mm" in strings(drawn):
        return "absent"
    return _seen(["76.00 mm"], drawn, svg_text(copy([]), "Dwgs.User"))


def variables() -> str:
    text = with_nodes(bench(), _gr_text("${TITLE} / ${REVISION}", 200, 20, 102))
    return _seen(["Drawing bench / B"], svg_text(text, "Dwgs.User"), svg_text(bench(), "Dwgs.User"))


def define_board() -> str:
    text = with_nodes(bench(), _gr_text("${FAB_NOTE}", 200, 20, 103))
    defined = svg_text(text, "Dwgs.User", "-D", "FAB_NOTE=hello")
    return _seen(["hello"], defined, svg_text(text, "Dwgs.User"))


def define_sheet() -> str:
    files = {"sheet.kicad_wks": SHEET.encode("utf-8")}
    options = ("--drawing-sheet", "sheet.kicad_wks")
    defined = svg_text(bench(), "Cmts.User", *options, "-D", "FENOLITE_DRAWING=Fabrication", sheet=True,
                       files=files)  # fmt: skip
    return _seen(["Fabrication"], defined, svg_text(bench(), "Cmts.User", *options, sheet=True, files=files))


# -- text (H-K-DRAW-TEXT)


def _wrapped(note: str) -> tuple[int, Decimal]:
    """How many lines KiCad draws for a note in a cell 80 mm wide and 6 mm high, and the lowest baseline."""
    cell = PlotTable(
        "probe:wrap", "Dwgs.User", Point(200 * MM, 20 * MM), (80 * MM,), (6 * MM,), ((note,),), SIZE
    )
    drawn = lines(svg_text(copy([cell]), "Dwgs.User"))
    return len(drawn), max((line[1] for line in drawn), default=Decimal(0))


def wrap_overflow() -> str:
    """A long text in a cell is wrapped by KiCad and leaves its row; a short one stays one line."""
    count, lowest = _wrapped(NOTE)
    short, _ = _wrapped("Short note.")
    if short != 1:
        return "inconclusive"
    return "present" if count > 1 and lowest > Decimal(26) else "absent"


def pitch() -> str:
    for n, size in enumerate(("1.5", "3"), 110):
        drawn = lines(
            svg_text(with_nodes(bench(), _gr_text("first\nsecond", 200, 20, n, size=size)), "Dwgs.User")
        )
        if len(drawn) != 2:
            return "inconclusive"
        if (
            abs(drawn[1][1] - drawn[0][1] - Decimal(size) * LINE_PITCH.numerator / LINE_PITCH.denominator)
            > TOLERANCE
        ):
            return "different"
    return "equal"


def glyph_bound() -> str:
    """No line of glyphs of ``GLYPH_SET`` is longer than ``text_width`` says: one glyph and ten repeats
    of each, one text per case. The control is the bound without the constant KiCad adds to a line,
    which a single wide glyph must exceed."""
    glyphs = sorted(GLYPH_SET - {" "})
    cases = [glyph * count for glyph in glyphs for count in (1, 10)]
    nodes = [_gr_text(case, 10, 20 + index, 1000 + index) for index, case in enumerate(cases)]
    drawn = lines(svg_text(with_nodes(bench(), *nodes), "Dwgs.User"))
    if len(drawn) != len(cases):
        return "inconclusive"
    mm = Decimal(MM)
    advances = Decimal(SIZE) * GLYPH_BOUND.numerator / GLYPH_BOUND.denominator / mm
    pairs = list(zip(cases, drawn, strict=True))
    if not any(line[2] > len(case) * advances for case, line in pairs):
        return "inconclusive"
    return (
        "equal"
        if all(line[2] <= Decimal(text_width(case, SIZE)) / mm for case, line in pairs)
        else "different"
    )


# -- page (H-K-DRAW-PAGE)

_LINE = (
    '(gr_line (start 150 30) (end 250 40) (stroke (width 0.1) (type solid)) (layer "Dwgs.User")'
    ' (uuid "d0a00000-0000-4000-8000-000000000120"))'
)


def page_position() -> str:
    """A line and a text are drawn at the page point of their board coordinates."""
    text = with_nodes(bench(), _LINE, _gr_text("anchor", 200, 60, 121))
    svg = sheet_svg(text, "Dwgs.User")
    moved = sheet_svg(text.replace("(start 150 30)", "(start 151 30)"), "Dwgs.User")
    if svg is None or moved is None:
        return "inconclusive"
    here = (Decimal(150), Decimal(30), Decimal(250), Decimal(40))
    if has_segment(moved, *here):
        return "inconclusive"
    anchored = any(t.text == "anchor" and abs(t.x - 200) <= TOLERANCE for t in svg.texts)
    return "equal" if has_segment(svg, *here) and anchored else "different"


def mirrored() -> str:
    """``--mirror`` maps x to W − x; without it the line stays."""
    text = with_nodes(bench(), _LINE)
    svg, plain = sheet_svg(text, "Dwgs.User", "--mirror"), sheet_svg(text, "Dwgs.User")
    if (
        svg is None
        or plain is None
        or has_segment(plain, svg.width_mm - 150, Decimal(30), svg.width_mm - 250, Decimal(40))
    ):
        return "inconclusive"
    there = (svg.width_mm - 150, Decimal(30), svg.width_mm - 250, Decimal(40))
    return "equal" if has_segment(svg, *there) else "different"


def no_holes() -> str:
    """``--drill-shape-opt 0`` draws no hole; the default draws the pad holes."""
    without = svg_text(bench(), "Edge.Cuts,Dwgs.User", "--drill-shape-opt", "0")
    default = svg_text(bench(), "Edge.Cuts,Dwgs.User")
    if not without or not default or "<circle" not in default:
        return "inconclusive"
    return "equal" if "<circle" not in without and marks(without) < marks(default) else "different"


def help_scale(kind: str) -> str:
    run = runner().run(["pcb", "export", kind, "--help"], files={})
    if not run.stdout.strip():
        return "inconclusive"
    return "present" if "--scale" in run.stdout else "absent"


# -- KiCad's default sheet (H-K-DRAW-SHEET)


def default_sheet_boxes(paper: str) -> str:
    """The borders and the title block that KiCad's default sheet plots lie where
    ``default_sheet_obstacles`` puts them, on the page size of ``AUTO_PAPERS``."""
    text = plot_copy(bench(), [], paper=paper, major=major(), layers=())
    svg = sheet_svg(text, "Cmts.User", "--drill-shape-opt", "0", sheet=True)
    bare = sheet_svg(text, "Cmts.User", "--drill-shape-opt", "0")
    if svg is None or bare is None or bare.paths:
        return "inconclusive"
    mm = Decimal(MM)
    width, height = AUTO_PAPERS[paper]
    if abs(svg.width_mm - width / mm) > TOLERANCE or abs(svg.height_mm - height / mm) > TOLERANCE:
        return "different"
    margin, boxes = default_sheet_obstacles(width, height)
    outer = [Decimal(v) / mm for v in margin]
    inner = [
        Decimal(boxes[0][3]) / mm,
        Decimal(boxes[1][1]) / mm,
    ]  # the y of the inner border, top and bottom
    title = [Decimal(v) / mm for v in boxes[-1]]
    wanted = [
        (outer[0], outer[1], outer[2], outer[1]),
        (outer[0], outer[3], outer[2], outer[3]),
        (outer[0], outer[1], outer[0], outer[3]),
        (Decimal(12), inner[0], svg.width_mm - 12, inner[0]),
        (Decimal(12), inner[1], svg.width_mm - 12, inner[1]),
        (title[0], title[1], title[0], title[3]),
        (title[0], title[1], title[2], title[1]),
    ]
    return "equal" if all(has_segment(svg, *segment) for segment in wanted) else "different"


# -- drill maps and report (H-K-DRAW-DRILL)


@cache
def drill_run(attempt: int = 0) -> CliRun:
    del attempt
    args = ["pcb", "export", "drill", "-o", "drawings/", *DRILL_OPTIONS, BOARD]
    return runner().run(args, files={BOARD: bench().encode("utf-8")}, folders=("drawings",))


def drill_files() -> str:
    """The through maps and the report are written, and every drill file has its map. The names of the
    files of a layer pair are recorded in ``docs/evidence/kicad-drawings.md``."""
    names = {name.removeprefix("drawings/") for name in drill_run().outputs if name.startswith("drawings/")}
    drills = {name for name in names if name.endswith(".drl")}
    wanted = {f"{NAME}-PTH.drl", f"{NAME}-NPTH.drl"}
    if not wanted <= drills:
        return "different"
    maps = {name.removesuffix(".drl") + "-drl_map.pdf" for name in drills}
    return "equal" if names == drills | maps | {f"{NAME}-drill.rpt"} and len(drills) == 3 else "different"


def drill_counts() -> str:
    """Per drill file and diameter, the report counts what ``drill_rows`` counts; the control drops a
    via from the model, which the check must then find."""
    report = read_drill_report(
        drill_run().outputs.get(f"drawings/{NAME}-drill.rpt", b"").decode("utf-8", "replace")
    )
    design = read_board(bench())
    rows = drill_rows(design)
    if not report.files or not check_drill(rows[1:], report):
        return "inconclusive"
    return "equal" if not check_drill(rows, report) else "different"


# -- assembly options (H-K-DRAW-ASSEMBLY)

FAB_PLOT = ("F.Fab,Edge.Cuts", "--drill-shape-opt", "0")


def _option(option: str, *, more: bool) -> str:
    base, changed = svg_text(bench(), *FAB_PLOT), svg_text(bench(), *FAB_PLOT, option)
    if not base or not changed:
        return "inconclusive"
    if marks(changed) == marks(base):
        return "absent"
    return "present" if (marks(changed) > marks(base)) == more else "inconclusive"


def dnp_crossout() -> str:
    return _option("--crossout-DNP-footprints-on-fab-layers", more=True)


def dnp_hide() -> str:
    hidden = svg_text(bench(), *FAB_PLOT, "--hide-DNP-footprints-on-fab-layers")
    if f"V{DNP_REF}" not in strings(svg_text(bench(), *FAB_PLOT)):
        return "inconclusive"
    gone = bool(hidden) and f"V{DNP_REF}" not in strings(hidden)
    return (
        "present"
        if gone and _option("--hide-DNP-footprints-on-fab-layers", more=False) == "present"
        else "absent"
    )


def values() -> str:
    """``--exclude-value`` removes the value texts of a PDF plot (the SVG export has no such option)."""
    base = export(bench(), "pdf", *FAB_PLOT).outputs.get("out.pdf", b"")
    changed = export(bench(), "pdf", *FAB_PLOT, "--exclude-value").outputs.get("out.pdf", b"")
    if not base or not changed or not shown_texts(base):
        return "inconclusive"
    return "present" if shown_texts(changed) < shown_texts(base) else "absent"


def pads() -> str:
    return _option("--sketch-pads-on-fab-layers", more=True)


def _glyphs(svg: str, text: str) -> list[tuple[Decimal, ...]]:
    """The strokes of a drawn text, relative to their smallest x and y."""
    start = svg.find(f"<desc>{text}</desc>")
    if start < 0:
        return []
    group = svg[start : svg.index("</g>", start)]
    found = [
        tuple(Decimal(v) for v in re.findall(r"[-\d.]+", d)) for d in re.findall(r'<path d="([^"]*)"', group)
    ]
    xs = [v for stroke in found for v in stroke[0::2]]
    ys = [v for stroke in found for v in stroke[1::2]]
    return sorted(tuple(v - (min(xs) if i % 2 == 0 else min(ys)) for i, v in enumerate(s)) for s in found)


def bottom_designator() -> str:
    """A mirrored text on ``B.Fab`` in a ``--mirror`` plot has the strokes of the same text on ``F.Fab``
    in a plain plot: it reads right. The control, the text without ``mirror``, has other strokes."""
    front = PlotText("probe:front", "QR7", "F.Fab", Point(150 * MM, 150 * MM), 3 * MM)
    back = PlotText("probe:back", "QR7", "B.Fab", Point(150 * MM, 150 * MM), 3 * MM)
    wanted = _glyphs(svg_text(copy([front], layers=("F.Fab",)), "F.Fab"), "QR7")
    text = copy([back], layers=("B.Fab",))
    drawn = _glyphs(svg_text(text, "B.Fab", "--mirror"), "QR7")
    control = _glyphs(svg_text(text.replace("(justify mirror)", ""), "B.Fab", "--mirror"), "QR7")

    def near(p: tuple[Decimal, ...], q: tuple[Decimal, ...]) -> bool:
        turned = (*q[2:4], *q[0:2])  # a stroke may be drawn from either end
        return any(
            all(abs(x - y) <= TOLERANCE for x, y in zip(p, other, strict=True)) for other in (q, turned)
        )

    def same(a: list[tuple[Decimal, ...]], b: list[tuple[Decimal, ...]]) -> bool:
        left = list(b)
        for stroke in a:
            match = next(
                (other for other in left if len(other) == len(stroke) == 4 and near(stroke, other)), None
            )
            if match is None:
                return False
            left.remove(match)
        return not left

    if not wanted or not drawn or not control or same(control, wanted):
        return "inconclusive"
    return "equal" if same(drawn, wanted) else "different"


# -- repeats (H-K-DRAW-REPEAT)


@cache
def exported(attempt: int = 0, spec: DrawingSpec = DEFAULT) -> tuple[DrawingResult, DrawingResult]:
    """Both drawing kinds of the bench; ``attempt`` asks for another run, taken a second later."""
    if attempt:
        time.sleep(PAUSE)
    cli = runner()
    design = read_board(bench_file())
    fab = run_fab_drawing(cli, bench_file(), {}, design=design, spec=spec, sheet=default_sheet())
    assembly = run_assembly_drawing(cli, bench_file(), {}, design=design, spec=spec, sheet=default_sheet())
    return fab, assembly


def _repeat(suffix: str) -> str:
    first = {a.path: a for result in exported(0) for a in result.artifacts if a.path.endswith(suffix)}
    second = {a.path: a for result in exported(1) for a in result.artifacts if a.path.endswith(suffix)}
    if not first or set(first) != set(second):
        return "inconclusive"
    same = all(
        content_sha256(first[path].data, first[path].kind)
        == content_sha256(second[path].data, second[path].kind)
        for path in first
    )
    return "equal" if same else "different"


def repeat_pdf() -> str:
    return _repeat(".pdf")


def repeat_report() -> str:
    return _repeat(".rpt")


# -- layer rows (H-K-DRAW-LAYER)


def layer_added() -> str:
    """A board whose layer table lacks the three layers gets their rows, and its items on them plot."""
    text = FIXTURE.read_text(encoding="utf-8")
    table_text = dumps(parse(text).find("layers"), style="compact")  # type: ignore[arg-type]
    names = ("Dwgs.User", "F.Fab", "B.Fab")
    missing = [name for name in names if f'"{name}"' not in table_text]
    if "Dwgs.User" not in missing:
        return "inconclusive"
    items = [PlotText(f"probe:{name}", f"on {name}", name, Point(20 * MM, 20 * MM), SIZE) for name in names]
    copied = plot_copy(text, items, paper="A4", major=major(), layers=names)
    plain = plot_copy(text, [], paper="A4", major=major(), layers=names)
    outcomes = set()
    for name in names:
        drawn = svg_text(copied, name, *(("--mirror",) if name == "B.Fab" else ()))
        outcomes.add(_seen([f"on {name}"], drawn, svg_text(plain, name)))
    return outcomes.pop() if len(outcomes) == 1 else "inconclusive"


def draw_probes() -> Probes:
    both = (9, 10)
    probes: Probes = {
        "draw-table": (table, both),
        "draw-textbox": (textbox, both),
        "draw-dimension": (dimension, both),
        "draw-vars": (variables, both),
        "draw-defvar-board": (define_board, both),
        "draw-defvar-sheet": (define_sheet, both),
        "draw-wrap-overflow": (wrap_overflow, both),
        "draw-pitch": (pitch, both),
        "draw-glyph-bound": (glyph_bound, both),
        "draw-page-position": (page_position, both),
        "draw-mirror": (mirrored, both),
        "draw-no-holes": (no_holes, both),
        "help-pcb-export-pdf-scale": (lambda: help_scale("pdf"), both),
        "help-pcb-export-svg-scale": (lambda: help_scale("svg"), both),
        "draw-drill-files": (drill_files, both),
        "draw-drill-counts": (drill_counts, both),
        "draw-dnp-crossout": (dnp_crossout, both),
        "draw-dnp-hide": (dnp_hide, both),
        "draw-values": (values, both),
        "draw-pads": (pads, both),
        "draw-bottom-designator": (bottom_designator, both),
        "draw-repeat-pdf": (repeat_pdf, both),
        "draw-repeat-report": (repeat_report, both),
        "draw-layer-added": (layer_added, both),
    }
    for paper in AUTO_PAPERS:
        probes[f"draw-default-sheet-{paper}"] = (lambda paper=paper: default_sheet_boxes(paper), both)
    return probes


__all__ = ["bench", "bench_design", "bench_file", "draw_probes", "exported", "lines", "svg_text", "workspace"]
