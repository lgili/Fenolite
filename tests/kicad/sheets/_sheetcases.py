# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawing-sheet and paper probes (c0012 Decision 16; capability kicad-oracle, "Drawing sheet and
paper semantics are probed"). ``wks_probes()`` gives the ``wks-*`` and ``pcb-paper-*`` entries of
``_probes.PROBES``; each probe exports once per session through ``_sheet_bench``.

Every sheet case is judged against the same-session controls: the default sheet of the same board
(``wks-default``) and c0007's skeleton sheet (``wks-control``).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import _expected as ex
from _sheet_bench import (
    BOARD_NAME,
    SHEETS,
    SKELETON_SHEET,
    Expected,
    SheetCase,
    board_text,
    classify,
    compare,
    export_sheet_svg,
)

from fenolite.backends.kicad import pro
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import write_board
from fenolite.backends.kicad.sexpr import parse_fragment
from fenolite.backends.kicad.wks import read_drawing_sheet
from fenolite.model.design import Design
from fenolite.model.presentation import SheetFrameRef, TitleBlock
from fenolite.templates import layout, resolve_text

A4 = '(paper "A4")'
A3 = '(paper "A3")'
VALUE_ATOMS = (
    "ltcorner",
    "lbcorner",
    "rtcorner",
    "rbcorner",
    "page1only",
    "notonpage1",
    "left",
    "center",
    "right",
    "top",
    "bottom",
    "bold",
    "italic",
)
MISSING_SHEET = "missing.kicad_wks"


def sheet(name: str) -> Path:
    return SHEETS / f"{name}.kicad_wks"


def board(paper: str = A4, *, title: bool = False) -> str:
    return board_text(paper=paper, title_block=ex.TITLE_BLOCK if title else "")


def default(paper: str = A4, *, title: bool = False, text: str | None = None) -> SheetCase:
    return export_sheet_svg(text if text is not None else board(paper, title=title), None)


def control(paper: str = A4, *, title: bool = False, text: str | None = None) -> SheetCase:
    return export_sheet_svg(text if text is not None else board(paper, title=title), SKELETON_SHEET)


def written_board(sheet_ref: SheetFrameRef | None, block: TitleBlock | None = None) -> str:
    """A created two-layer board with ``sheet_ref`` and ``block``, written by ``write_board`` for the
    running major (task 6.3)."""
    design = Design.new("board", seed=12)
    assert design.board is not None
    created = dataclasses.replace(design.board, layers=created_layers(2), sheet=sheet_ref, title_block=block)
    return write_board(dataclasses.replace(design, board=created), target=running_major()).text


def verdict(
    sheet_file: Path | str, marker: str | None, paper: str = A4, *, title: bool = False
) -> tuple[str, SheetCase]:
    case = export_sheet_svg(board(paper, title=title), sheet_file)
    outcome = classify(
        case, default=default(paper, title=title), control=control(paper, title=title), marker=marker
    )
    return outcome, case


# -- controls and verdict classes


def wks_default() -> str:
    case = default()
    if case.outcome == "timeout":
        return "timeout"
    return "present" if case.svg is not None and case.svg.texts else "absent"


def wks_control() -> str:
    return verdict(SKELETON_SHEET, None)[0]


def svg_shape() -> str:
    outcome, case = verdict(sheet("probe_shape"), "Alpha")
    if outcome != "load" or case.svg is None:
        return outcome
    page_ok = abs(case.svg.width_mm - 297) <= Decimal("0.01") and abs(case.svg.height_mm - 210) <= Decimal(
        "0.01"
    )
    return "present" if page_ok and case.strings() == ["Alpha", "Bravo", "Charlie"] else "absent"


# -- semantics


MM = 1_000_000


def predicted(
    sheet_name: str, width_mm: Decimal, height_mm: Decimal, *, paper: str, block: TitleBlock | None = None
) -> list[Expected]:
    """What ``fenolite.templates.layout`` and ``resolve_text`` predict for a probe sheet on the page read
    from KiCad's SVG (task 8.3; ``tests/unit/templates/test_layout.py`` checks it against ``_expected``)."""
    read = read_drawing_sheet(sheet(sheet_name))
    lay = layout(read, width=int(width_mm * MM), height=int(height_mm * MM))
    texts = block or TitleBlock()
    return [
        Expected(resolve_text(t.text, texts, paper=paper, filename=BOARD_NAME),
                 Decimal(t.x) / MM, Decimal(t.y) / MM, Decimal(t.size[1]) / MM)
        for t in lay.texts
    ]  # fmt: skip


def semantic(sheet_name: str, marker: str, papers: tuple[str, ...]) -> str:
    """``equal`` when the drawing matches the ``layout`` prediction on every paper of ``papers``."""
    for paper in papers:
        outcome, case = verdict(sheet(sheet_name), marker, paper)
        if outcome != "load" or case.svg is None:
            return "inconclusive" if outcome in ("absent", "different") else outcome
        name = parse_fragment(paper).atoms()[0].value  # type: ignore[union-attr]
        if compare(case.svg, predicted(sheet_name, case.svg.width_mm, case.svg.height_mm, paper=name)):
            return "different"
    return "equal"


def scoped(sheet_name: str, text: str) -> str:
    """``present`` or ``absent``: whether ``text`` is drawn on a board export (page 1 of 1)."""
    outcome, case = verdict(sheet(sheet_name), "Scope")
    if outcome != "load":
        return "inconclusive" if outcome in ("absent", "different") else outcome
    return "present" if text in case.strings() else "absent"


def undefined_var() -> str:
    outcome, case = verdict(sheet("probe_undefined"), "Undefined")
    if outcome != "load":
        return "inconclusive" if outcome in ("absent", "different") else outcome
    return "present" if "${NOPE}" in case.strings() else "absent"


def percent() -> str:
    for name in ("probe_percent", "probe_percent_legacy"):
        outcome, case = verdict(sheet(name), "Percent", title=True)
        if outcome != "load" or case.svg is None:
            return "inconclusive" if outcome in ("absent", "different") else outcome
        if compare(case.svg, ex.expected("wks-percent", case.svg.width_mm, case.svg.height_mm)):
            return "different"
    return "equal"


def _resolution_start() -> tuple[str, Decimal | None]:
    """The verdict of ``probe_resolution`` and the drawn x of its line start (``None`` if not found)."""
    outcome, case = verdict(sheet("probe_resolution"), "Resolution")
    if outcome != "load" or case.svg is None:
        return ("inconclusive" if outcome in ("absent", "different") else outcome), None
    _, y1, x2, y2 = ex.RESOLUTION_LINE
    tol = Decimal("0.01")
    for s in case.svg.paths:
        for (ax, ay), (bx, by) in (((s.x1, s.y1), (s.x2, s.y2)), ((s.x2, s.y2), (s.x1, s.y1))):
            if abs(bx - x2) <= tol and abs(by - y2) <= tol and abs(ay - y1) <= tol:
                if -ax.as_tuple().exponent < 4:  # type: ignore[operator]
                    return "inconclusive", None  # fewer than 4 decimals cannot show 0.0006 mm
                return "load", ax
    return "different", None


def resolution() -> str:
    """``equal`` when the start is drawn at the truncated micrometre (``H-K-WKS-RES``)."""
    outcome, x = _resolution_start()
    if x is None:
        return outcome
    return "equal" if abs(x - ex.RESOLUTION_LINE[0]) <= ex.RESOLUTION_TOLERANCE else "different"


def resolution_exact() -> str:
    """``equal`` when the start is drawn as written, without truncation (``H-K-WKS-RES-2``)."""
    outcome, x = _resolution_start()
    if x is None:
        return outcome
    return "equal" if abs(x - ex.RESOLUTION_EXACT_X) <= ex.RESOLUTION_TOLERANCE else "different"


# -- projects (c0010's project template with the keys set here)


def project(target: int, *, sheet_key: str | None = None, variables: dict[str, str] | None = None) -> bytes:
    """``board.kicad_pro`` from ``pro.template(target)`` with ``page_layout_descr_file`` and
    ``text_variables`` set."""
    data = pro.template(target)
    if sheet_key is not None:
        data["pcbnew"]["page_layout_descr_file"] = sheet_key  # type: ignore[index]
    if variables:
        data["text_variables"] = dict(variables)
    return pro.write_project_text(data).encode("utf-8")


def running_major() -> int:
    from _probes import major

    return major()


def tokens() -> str:
    """``equal`` when the eleven variables and the project parameter resolve as ``_expected`` says."""
    files = {"board.kicad_pro": project(running_major(), variables=dict([ex.PARAMETER]))}
    text = written_board(SheetFrameRef("A4"), ex.TITLE)
    case = export_sheet_svg(text, sheet("probe_tokens"), files=files)
    outcome = classify(case, default=default(text=text), control=control(text=text), marker="Tokens")
    if outcome != "load" or case.svg is None:
        return "inconclusive" if outcome in ("absent", "different") else outcome
    block = dataclasses.replace(ex.TITLE, params=dict([ex.PARAMETER]))
    found = compare(
        case.svg, predicted("probe_tokens", case.svg.width_mm, case.svg.height_mm, paper="A4", block=block)
    )
    return "different" if found else "equal"


def project_sheet(sheet_key: str, *, with_file: bool) -> str:
    """A sheet named only by the project key (no ``--drawing-sheet``): ``present`` when its marker and the
    project variable are drawn, else the verdict class."""
    files = {"board.kicad_pro": project(running_major(), sheet_key=sheet_key, variables=dict([ex.PARAMETER]))}
    if with_file:
        files["probe_pro.kicad_wks"] = sheet("probe_pro").read_bytes()
    case = export_sheet_svg(board(), None, files=files)
    outcome = classify(case, default=default(), control=control(), marker="Project")
    if not with_file:
        return outcome
    if outcome != "load":
        return "inconclusive" if outcome in ("absent", "different") else outcome
    return "present" if ex.PARAMETER[1] in case.strings() else "absent"


# -- bitmaps


def _extra_lines(case: SheetCase, base: SheetCase) -> set[str]:
    return set(case.lines) - set(base.lines)


def bitmap_corrupt() -> str:
    outcome, case = verdict(sheet("probe_bitmap_corrupt"), "Corrupt")
    if outcome == "timeout":
        return outcome
    return "present" if _extra_lines(case, control()) else "absent"


def bitmap() -> str:
    return verdict(sheet("probe_bitmap"), "Bitmap")[0]


def bitmap_clean() -> str:
    """``absent`` when no line that the corrupt bitmap adds over the control appears for the good one
    (reads the memoised runs of ``wks-bitmap``, ``wks-bitmap-corrupt`` and ``wks-control``)."""
    _, good = verdict(sheet("probe_bitmap"), "Bitmap")
    _, bad = verdict(sheet("probe_bitmap_corrupt"), "Corrupt")
    return "present" if _extra_lines(bad, control()) & set(good.lines) else "absent"


# -- paper


def paper(name: str) -> str:
    if name in ex.PAPERS_MIL:
        _, width, height = ex.PAPERS_MIL[name]
        exact = True
    else:
        _, width, height, exact = ex.PAPERS[name]
    case = export_sheet_svg(written_board(ex.PAPER_REFS[name]), None)
    if case.outcome == "timeout":
        return "timeout"
    if case.svg is None:
        return "reject"
    tolerance = Decimal(0) if exact else ex.PAPER_TOLERANCE
    ok = abs(case.svg.width_mm - width) <= tolerance and abs(case.svg.height_mm - height) <= tolerance
    return "equal" if ok else "different"


def wks_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    both = (9, 10)
    probes: dict[str, tuple[Callable[[], str], tuple[int, ...]]] = {
        "wks-default": (wks_default, both),
        "wks-control": (wks_control, both),
        "wks-svg-shape": (svg_shape, both),
        "wks-broken": (lambda: verdict(sheet("probe_broken"), "Broken")[0], both),
        "wks-missing-file": (lambda: verdict(MISSING_SHEET, None)[0], both),
        "wks-corners": (lambda: semantic("probe_corners", "LT", (A4, A3)), both),
        "wks-repeat": (lambda: semantic("probe_repeat", "Repeat", (A4, A3)), both),
        "wks-page1only": (lambda: scoped("probe_page1only", "First"), both),
        "wks-notonpage1": (lambda: scoped("probe_notonpage1", "Later"), both),
        "wks-undefined-var": (undefined_var, both),
        "wks-percent": (percent, both),
        "wks-tokens": (tokens, both),
        "wks-pro-relative": (lambda: project_sheet("probe_pro.kicad_wks", with_file=True), both),
        "wks-pro-kiprjmod": (lambda: project_sheet("${KIPRJMOD}/probe_pro.kicad_wks", with_file=True), both),
        "wks-pro-missing": (lambda: project_sheet(MISSING_SHEET, with_file=False), both),
        "wks-bitmap-corrupt": (bitmap_corrupt, both),
        "wks-bitmap": (bitmap, both),
        "wks-bitmap-clean": (bitmap_clean, both),
        "wks-resolution": (resolution, both),
        "wks-resolution-exact": (resolution_exact, both),
    }
    for atom in (*VALUE_ATOMS, "unknown"):
        probes[f"wks-value-{atom}"] = (
            lambda atom=atom: verdict(sheet(f"probe_value_{atom}"), "Value")[0],
            both,
        )
    for name in (*ex.PAPERS, *ex.PAPERS_MIL):
        probes[f"pcb-paper-{name}"] = (lambda name=name: paper(name), both)
    return probes


__all__ = ["VALUE_ATOMS", "wks_probes"]
