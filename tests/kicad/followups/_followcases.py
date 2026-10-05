# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The follow-up probes of change c0074 (capability kicad-oracle, "Follow-up facts are probed"; hypotheses
H-K-PRO-WKS-SCH, H-K-OUTLINE-CHAIN, H-K-OUTLINE-FPEDGE, H-K-EXPORT-OPTIONS and H-K-STITCH-AVOID).

Every case runs ``kicad-cli`` once per session on temporary copies, through c0009's runner, and judges DRC
from the JSON report only. The boards, sheets and names are authored here for the probes.

- **Schematic frame.** The authored two-sheet schematic with a project file that names a drawing sheet
  holding one distinctive text, under the schematic key (relative and ``${KIPRJMOD}``), under the board
  key only, or not at all; ``sch export svg`` shows the text on both sheets or on none.
- **Outline gap.** A 50 × 30 mm rectangle of four edge lines whose last line stops short of the first
  corner by 9 999, 10 000 and 10 001 nm; ``invalid_outline`` says whether KiCad closes it.
- **Footprint edges.** The built blink whose top edge line is replaced by two lines leaving an opening
  that an ``fp_line`` of ``R1`` closes; and an ``fp_circle`` of ``R1`` on the edge layer with a track
  across it.
- **Export options.** The help pages of ``pcb export gerbers``, ``drill`` and ``pos``, and one run per
  preset key on the built blink, compared with the default run.
- **Stitching.** The blink with a fence across a rule area that forbids vias and one along the board
  edge, built with and without the avoidance.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path

import _lenscases as lc
from _buildcases import _folder
from _buildhelp import blink, build
from _layout_edit import add_items, add_to_footprint

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad import copper as copper_mod
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import Design as DslDesign
from fenolite.dsl import copper, placements, to_model
from fenolite.dsl import mm as dsl_mm
from fenolite.exports import plan, preset
from fenolite.lens.preserve import ExistingProject, prepare
from fenolite.model.board import Board, Graphic, Keepout
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
SCHEMATICS = ROOT / "tests" / "data" / "kicad" / "schematic"
MM = 1_000_000
BOARD = "blink.kicad_pcb"
MARKER = "FENOLITEPROBESHEET"
SHEET = (
    '(kicad_wks (version 20231118) (generator "fenolite")\n'
    "\t(setup (textsize 1.5 1.5) (linewidth 0.15) (textlinewidth 0.15) (left_margin 10) (right_margin 10) "
    "(top_margin 10) (bottom_margin 10))\n"
    f'\t(tbtext "{MARKER}" (name "probe") (pos 50 20) (font (size 2 2)))\n'
    ")\n"
)
"""A drawing sheet with one distinctive text, authored for the probe."""
SHEET_KEYS: Mapping[str, str] = {
    "relative": '{"schematic": {"page_layout_descr_file": "probe.kicad_wks"}}\n',
    "kiprjmod": '{"schematic": {"page_layout_descr_file": "${KIPRJMOD}/probe.kicad_wks"}}\n',
    "absent": "{}\n",
    "board-only": '{"pcbnew": {"page_layout_descr_file": "probe.kicad_wks"}}\n',
}
"""Case → the project file of the two-sheet schematic."""
GAPS = (9_999, 10_000, 10_001)
EDGE = '(stroke (width 0.05) (type solid)) (layer "Edge.Cuts")'
Files = dict[str, str | bytes]


def major() -> int:
    return lc.runner().major()


def target() -> int:
    return 10 if major() >= 10 else 9


# -- the schematic frame


@cache
def schematic_sheet(case: str) -> str:
    """``present`` when ``sch export svg`` draws the probe text on both sheets, ``absent`` on none."""
    folder = SCHEMATICS / ("hier" if major() >= 10 else "hier_v9")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "top.kicad_pro").write_text(SHEET_KEYS[case], encoding="utf-8")
        (work / "probe.kicad_wks").write_text(SHEET, encoding="utf-8")
        files = {
            "top.kicad_sch": folder / "top.kicad_sch",
            "child.kicad_sch": folder / "child.kicad_sch",
            "top.kicad_pro": work / "top.kicad_pro",
            "probe.kicad_wks": work / "probe.kicad_wks",
        }
        run = lc.runner().run(
            ["sch", "export", "svg", "-o", "svg", "top.kicad_sch"], files=files, folders=["svg"]
        )
    drawn = [data for name, data in run.outputs.items() if name.startswith("svg/") and name.endswith(".svg")]
    if run.returncode != 0 or len(drawn) < 2:
        return "inconclusive"
    marked = sum(1 for data in drawn if MARKER.encode() in data)
    return "present" if marked == len(drawn) else "absent" if marked == 0 else "inconclusive"


# -- DRC helpers


def drc(files: Mapping[str, str | bytes], board: str = BOARD) -> DrcReport | None:
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(files, Path(tmp))
        extra = {k: v for k, v in tops.items() if k != board}
        return lc.runner().drc(Path(tmp) / board, files=extra).report


def types(report: DrcReport) -> set[str]:
    return {v.type for v in report.violations}


def names_uuid(report: DrcReport, kind: str, uuids: set[str]) -> bool:
    """Whether a violation of ``kind`` names one of ``uuids``."""
    return any(v.type == kind and uuids & {item.uuid for item in v.items} for v in report.violations)


# -- the outline gap


def gap_board(gap: int) -> str:
    """A 50 × 30 mm rectangle of four edge lines whose last line stops ``gap`` nm short of its corner."""
    corners = [
        Point(100 * MM, 100 * MM),
        Point(150 * MM, 100 * MM),
        Point(150 * MM, 130 * MM),
        Point(100 * MM, 130 * MM),
    ]
    ends = [*corners[1:], Point(corners[0].x, corners[0].y + gap)]
    graphics = tuple(
        Graphic(id=derived_id("gfx", "followup", f"gap:{n}"), kind="line", layer="Edge.Cuts", points=(a, b))
        for n, (a, b) in enumerate(zip(corners, ends, strict=True))
    )
    board = Board(id=derived_id("brd", "followup", "gap"), layers=created_layers(2), graphics=graphics)
    design = dataclasses.replace(Design.new("gap", seed=0), board=board)
    return write_board(design, target=target()).text


@cache
def outline_gap(gap: int) -> str:
    """``present`` when KiCad reports ``invalid_outline`` for the gap, ``absent`` when it closes it."""
    report = drc({"gap.kicad_pcb": gap_board(gap), "gap.kicad_pro": "{}\n"}, "gap.kicad_pcb")
    if report is None:
        return "inconclusive"
    return "present" if "invalid_outline" in types(report) else "absent"


# -- edge items inside footprints


@cache
def blink_files() -> Files:
    output = build(blink(), target())
    return {rel: data for rel, data in output.files.items() if not rel.startswith(".fenolite/")}


def blink_text() -> str:
    data = blink_files()[BOARD]
    return data.decode("utf-8") if isinstance(data, bytes) else data


def opened(text: str) -> str:
    """The blink whose top edge line is replaced by two lines that leave an opening from x = 120 to 125."""
    top = "(gr_line\n\t\t(start 100 100)\n\t\t(end 150 100)"
    assert text.count(top) == 1
    text = text.replace(top, "(gr_line\n\t\t(start 100 100)\n\t\t(end 120 100)")
    line = f'(gr_line (start 125 100) (end 150 100) {EDGE} (uuid "0e0e0e0e-0000-4000-8000-0000000000a0"))'
    return add_items(text, line)


@cache
def fp_edge_closes() -> str:
    """``present`` when the ``fp_line`` of ``R1`` (at (132, 109) mm) closes the opening: no
    ``invalid_outline`` with it, and ``invalid_outline`` without it."""
    line = f'(fp_line (start -12 -9) (end -7 -9) {EDGE} (uuid "0e0e0e0e-0000-4000-8000-0000000000a1"))'
    open_board = opened(blink_text())
    closed = add_to_footprint(open_board, "R1", line)
    without, with_line = drc({**blink_files(), BOARD: open_board}), drc({**blink_files(), BOARD: closed})
    if without is None or with_line is None or "invalid_outline" not in types(without):
        return "inconclusive"
    return "absent" if "invalid_outline" in types(with_line) else "present"


TRACK = "0e0e0e0e-0000-4000-8000-0000000000b1"


@cache
def fp_edge_cutout() -> str:
    """``present`` when a track across an ``fp_circle`` of ``R1`` on the edge layer gets
    ``copper_edge_clearance``, and the same track without the circle does not."""
    circle = (
        f'(fp_circle (center 0 12) (end 1 12) {EDGE} (fill no) (uuid "0e0e0e0e-0000-4000-8000-0000000000a2"))'
    )
    track = f'(segment (start 128 121) (end 136 121) (width 0.25) (layer "F.Cu") (uuid "{TRACK}"))'
    plain = add_items(blink_text(), track)
    holed = add_to_footprint(plain, "R1", circle)
    without, with_hole = drc({**blink_files(), BOARD: plain}), drc({**blink_files(), BOARD: holed})
    if without is None or with_hole is None or names_uuid(without, "copper_edge_clearance", {TRACK}):
        return "inconclusive"
    return "present" if names_uuid(with_hole, "copper_edge_clearance", {TRACK}) else "absent"


# -- export options

HELP_KINDS = ("gerbers", "drill", "pos")
OPTIONS: Mapping[str, tuple[str, ...]] = {
    "gerbers": (
        "--layers", "--no-protel-ext", "--no-x2", "--no-netlist", "--disable-aperture-macros", "--precision",
        "--subtract-soldermask", "--use-drill-file-origin", "--include-border-title", "--exclude-refdes",
        "--exclude-value",
    ),
    "drill": (
        "--format", "--excellon-units", "--excellon-separate-th", "--drill-origin", "--excellon-mirror-y",
        "--excellon-min-header", "--excellon-zeros-format", "--excellon-oval-format", "--generate-map",
        "--map-format", "--gerber-precision",
    ),
    "pos": (
        "--format", "--units", "--side", "--exclude-dnp", "--exclude-fp-th", "--smd-only",
        "--use-drill-file-origin", "--bottom-negate-x",
    ),
}  # fmt: skip
"""Kind → every option a preset can give."""
VARIANTS: Mapping[str, Mapping[str, str]] = {
    "gerbers": {
        "layers": 'layers = ["F.Cu", "Edge.Cuts"]',
        "protel_extensions": "protel_extensions = true",
        "x2": "x2 = false",
        "netlist_attributes": "netlist_attributes = false",
        "aperture_macros": "aperture_macros = false",
        "precision": "precision = 5",
        "subtract_soldermask": "subtract_soldermask = true",
        "use_drill_file_origin": "use_drill_file_origin = true",
        "include_border_title": "include_border_title = true",
        "exclude_refdes": "exclude_refdes = true",
        "exclude_value": "exclude_value = true",
    },
    "drill": {
        "format": 'format = "gerber"',
        "units": 'units = "in"',
        "separate_th": "separate_th = false",
        "mirror_y": "mirror_y = true",
        "minimal_header": "minimal_header = true",
        "origin": 'origin = "plot"',
        "zeros": 'zeros = "suppressleading"',
        "oval_format": 'oval_format = "route"',
        "map": 'map = "svg"',
        "gerber_precision": 'format = "gerber"\ngerber_precision = 5',
    },
    "pos": {
        "format": 'format = "ascii"',
        "units": 'units = "in"',
        "side": 'side = "front"',
        "exclude_dnp": "exclude_dnp = true",
        "exclude_fp_th": "exclude_fp_th = true",
        "smd_only": "smd_only = true",
        "use_drill_file_origin": "use_drill_file_origin = true",
        "bottom_negate_x": "bottom_negate_x = true",
    },
}
"""Kind → preset key → the line that sets it to a value other than its default."""


@cache
def help_page(kind: str) -> str:
    run = lc.runner().run(["pcb", "export", kind, "--help"], files={})
    return run.stdout + run.stderr


def help_row(kind: str, option: str) -> str:
    page = help_page(kind)
    if "Usage" not in page and "usage" not in page:
        return "inconclusive"
    words = page.replace(",", " ").replace("[", " ").replace("]", " ").replace("=", " ").split()
    return "present" if option in words else "absent"


def _stable(kind: str, outputs: Mapping[str, bytes]) -> dict[str, bytes]:
    """The files an export wrote under its folder, without the lines that carry the creation date."""
    volatile = plan.VOLATILE_PREFIXES.get(kind, ())
    found: dict[str, bytes] = {}
    for name, data in outputs.items():
        if not name.startswith(f"{plan.KINDS[kind].folder}/"):
            continue
        lines = (
            [line for line in data.split(b"\n") if not line.lstrip().startswith(volatile)]
            if volatile
            else None
        )
        found[name] = data if lines is None else b"\n".join(lines)
    return found


@cache
def export_run(kind: str, body: str) -> dict[str, bytes] | None:
    """The stable files of one export of the built blink with the preset ``body`` (``""``: no preset)."""
    chosen = (
        None if not body else preset.read_preset(f'schema = "{preset.PRESET_SCHEMA}"\n[{kind}]\n{body}\n')
    )
    design = read_board(blink_text())
    with tempfile.TemporaryDirectory() as tmp:
        tops = _folder(blink_files(), Path(tmp))
        extra = {k: v for k, v in tops.items() if k != BOARD}
        args = preset.arguments(kind, chosen, stem="blink", layers=plan.gerber_layers(design))
        run = lc.runner().export(list(args), Path(tmp) / BOARD, files=extra, out=plan.KINDS[kind].folder)
    if run.returncode != 0:
        return None
    return _stable(kind, run.outputs)


def export_option(kind: str, key: str) -> str:
    """``different`` when the run with the key set writes other files than the default run, ``equal`` when
    it writes the same, ``reject`` when ``kicad-cli`` refuses the arguments."""
    default, changed = export_run(kind, ""), export_run(kind, VARIANTS[kind][key])
    if default is None:
        return "inconclusive"
    if changed is None:
        return "reject"
    return "equal" if changed == default else "different"


# -- stitching

AREA = (
    Point(120 * MM, 124 * MM),
    Point(124 * MM, 124 * MM),
    Point(124 * MM, 128 * MM),
    Point(120 * MM, 128 * MM),
)
"""A rule area over x from 20 to 24 mm and y from 24 to 28 mm of the blink board, in the written frame."""


def fenced() -> DslDesign:
    """The blink with a 0.5 mm edge clearance, a fence across the board at y = 26 mm (it crosses ``AREA``)
    and a fence 0.4 mm from the left edge."""
    d = blink()
    gnd = d.nets["GND"]
    d.rules.minimum(edge_clearance=dsl_mm(0.5))
    sizes = {"diameter": dsl_mm(0.6), "drill": dsl_mm(0.3), "clearance": dsl_mm(0.2)}
    d.stitch(
        "across", net=gnd, pitch=dsl_mm(4), along=[(dsl_mm(5), dsl_mm(26)), (dsl_mm(45), dsl_mm(26))], **sizes
    )
    d.stitch(
        "edge", net=gnd, pitch=dsl_mm(2), along=[(dsl_mm(0.4), dsl_mm(3)), (dsl_mm(0.4), dsl_mm(9))], **sizes
    )
    return d


def with_area(text: str) -> str:
    """The board ``text`` with ``AREA`` as a rule area that forbids vias on both copper layers."""
    design = read_board(text)
    assert design.board is not None
    area = Keepout(
        id=derived_id("kpo", "followup", "area"),
        native_ids={"kicad": "0e0e0e0e-0000-4000-8000-0000000000c1"},
        outline=AREA,
        layers=("F.Cu", "B.Cu"),
        no_vias=True,
    )
    board = dataclasses.replace(design.board, keepouts=(*design.board.keepouts, area))
    return write_board(dataclasses.replace(design, board=board), target=target()).text


def _text(files: Mapping[str, str | bytes], name: str) -> str | None:
    data = files.get(name)
    return None if data is None else data.decode("utf-8") if isinstance(data, bytes) else data


def fence_build(*, avoid: bool) -> Files:
    """The fenced blink built over a board that holds the rule area; with ``avoid=False`` the keep-outs
    and the edge do not count, as before change c0074."""
    d = fenced()
    first = build(d, target(), copper_intents=copper(d))
    assert first.files, [i.message for i in first.issues if i.severity == "error"]
    files: Files = {rel: data for rel, data in first.files.items() if not rel.startswith(".fenolite/")}
    files[BOARD] = with_area(_text(files, BOARD) or "")
    again = fenced()
    existing = ExistingProject(
        _text(files, BOARD), _text(files, "blink.kicad_pro"), _text(files, "blink.kicad_dru")
    )
    ready = prepare(to_model(again), placements(again), existing, name="blink")
    original = copper_mod._Barriers.blocks  # pyright: ignore[reportPrivateUsage]
    if not avoid:
        copper_mod._Barriers.blocks = lambda self, point, diameter: False  # type: ignore[method-assign]  # pyright: ignore[reportPrivateUsage]
    try:
        output = build(
            again,
            target(),
            prepared=ready,
            placements_override=ready.placements,
            copper_intents=copper(again),
        )
    finally:
        copper_mod._Barriers.blocks = original  # type: ignore[method-assign]  # pyright: ignore[reportPrivateUsage]
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return {rel: data for rel, data in output.files.items() if not rel.startswith(".fenolite/")}


def stitch_vias(files: Mapping[str, str | bytes]) -> dict[str, Point]:
    """KiCad uuid → position of every script via of the board."""
    board = read_board(_text(files, BOARD) or "").board
    assert board is not None
    return {
        via.native_ids["kicad"]: via.position
        for via in board.vias
        if copper_mod.is_copper_uuid(via.native_ids.get("kicad", ""))
    }


@cache
def stitch_reports() -> tuple[tuple[Files, DrcReport | None], tuple[Files, DrcReport | None]]:
    avoided, control = fence_build(avoid=True), fence_build(avoid=False)
    return (avoided, drc(avoided)), (control, drc(control))


def stitch_avoid() -> str:
    """``equal`` when the fence built with the avoidance has no ``items_not_allowed`` and no
    ``copper_edge_clearance`` entry for a stitch via, and the control fence has both."""
    (avoided, clean), (control, flagged) = stitch_reports()
    if clean is None or flagged is None:
        return "inconclusive"
    kinds = ("items_not_allowed", "copper_edge_clearance")
    ours, theirs = set(stitch_vias(avoided)), set(stitch_vias(control))
    if not all(names_uuid(flagged, kind, theirs) for kind in kinds):
        return "inconclusive"
    return "different" if any(names_uuid(clean, kind, ours) for kind in kinds) else "equal"


def followup_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    probes: dict[str, tuple[Callable[[], str], tuple[int, ...]]] = {}
    for case in SHEET_KEYS:
        probes[f"wks-sch-key-{case}"] = (lambda case=case: schematic_sheet(case), both)
    for gap in GAPS:
        probes[f"outline-gap-{gap}"] = (lambda gap=gap: outline_gap(gap), both)
    probes["outline-fp-edge-closes"] = (fp_edge_closes, both)
    probes["outline-fp-edge-cutout"] = (fp_edge_cutout, both)
    for kind, options in OPTIONS.items():
        for option in options:
            probes[f"help-pcb-export-{kind}-{option.lstrip('-')}"] = (
                lambda kind=kind, option=option: help_row(kind, option),
                both,
            )
        for key in VARIANTS[kind]:
            probes[f"export-option-{kind}-{key}"] = (
                lambda kind=kind, key=key: export_option(kind, key),
                both,
            )
    probes["stitch-avoid"] = (stitch_avoid, both)
    return probes


__all__ = [
    "GAPS",
    "HELP_KINDS",
    "OPTIONS",
    "SHEET_KEYS",
    "VARIANTS",
    "export_option",
    "followup_probes",
    "fp_edge_closes",
    "fp_edge_cutout",
    "help_row",
    "outline_gap",
    "schematic_sheet",
    "stitch_avoid",
    "stitch_reports",
    "stitch_vias",
]
