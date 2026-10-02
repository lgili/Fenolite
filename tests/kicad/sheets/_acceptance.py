# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""v0.1 acceptance item 4 (c0012 Decision 18; capability kicad-oracle, "One drawing sheet serves several
sizes on both majors").

Each shipped example is built by ``fenolite template build`` (run as a subprocess), and each listed size
gets a board written by ``write_board`` for the running major with a seven-field title block. KiCad's SVG
must lack the load-error message, draw exactly the texts ``layout`` and ``resolve_text`` predict, differ
from the default sheet of the same board, and draw every predicted line within 0.01 mm. The same session
runs four controls: the sheet with ``(frobnicate 1)`` inserted (``reject``), a missing ``--drawing-sheet``
file and a project naming a missing sheet (``absent``), and c0007's skeleton sheet (``load``).
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
from decimal import Decimal
from functools import cache
from pathlib import Path

import _expected as ex
import _sheetcases as sc
from _sheet_bench import BOARD_NAME, SKELETON_SHEET, Expected, classify, compare, export_sheet_svg
from _svg import SheetSvg

from fenolite.backends.kicad.wks import read_drawing_sheet
from fenolite.model.presentation import DrawingSheet, SheetFrameRef, TitleBlock
from fenolite.templates import example_path, layout, resolve_text

MM = 1_000_000
EXAMPLE_SIZES: dict[str, tuple[str, ...]] = {
    "iso5457_generic": ("A4", "A3"),
    "letter_generic": ("Letter", "Tabloid"),
}
SIZE_REFS = {"A4": SheetFrameRef("A4"), "A3": SheetFrameRef("A3"), "Letter": SheetFrameRef("Letter"),
             "Tabloid": SheetFrameRef("Tabloid")}  # fmt: skip
PAPER_NAMES = {"A4": "A4", "A3": "A3", "Letter": "User", "Tabloid": "User"}
"""The paper name as the board writes it, which ``${PAPER}`` shows."""
_FOLDER = Path(tempfile.mkdtemp(prefix="fenolite-accept-"))


@cache
def built(example: str) -> Path:
    """The ``.kicad_wks`` that ``fenolite template build`` writes for ``example``."""
    folder = _FOLDER / example
    folder.mkdir(parents=True, exist_ok=True)
    spec = str(example_path(example))
    out = f"{example}.kicad_wks"
    args = [sys.executable, "-m", "fenolite", "template", "build", spec, "--target", "kicad", "--out", out]
    args += ["--confirm", "--json"]
    subprocess.run(args, cwd=folder, check=True, capture_output=True, timeout=300)
    return folder / f"{example}.kicad_wks"


def sha256(example: str) -> str:
    return hashlib.sha256(built(example).read_bytes()).hexdigest()


def board(size: str) -> str:
    return sc.written_board(SIZE_REFS[size], ex.TITLE)


def prediction(
    sheet: DrawingSheet, svg: SheetSvg, *, paper: str, block: TitleBlock
) -> tuple[list[Expected], list[tuple[Decimal, Decimal, Decimal, Decimal]]]:
    """``layout`` on the page KiCad drew, texts resolved for ``block``, ``paper`` and the board's name."""
    lay = layout(sheet, width=int(svg.width_mm * MM), height=int(svg.height_mm * MM))
    texts = [
        Expected(resolve_text(t.text, block, paper=paper, filename=BOARD_NAME), Decimal(t.x) / MM,
                 Decimal(t.y) / MM, Decimal(t.size[1]) / MM)
        for t in lay.texts
    ]  # fmt: skip
    lines = [tuple(Decimal(v) / MM for v in (ln.x1, ln.y1, ln.x2, ln.y2)) for ln in lay.lines]
    return texts, lines  # type: ignore[return-value]


def problems_for(
    size: str, svg: SheetSvg, texts: list[Expected], lines: list[tuple[Decimal, ...]]
) -> list[str]:
    """The mismatches, each naming the size (``compare`` names the text or line)."""
    return [f"{size}: {p}" for p in compare(svg, texts, lines)]  # type: ignore[arg-type]


def accept(example: str, size: str) -> tuple[str, list[str]]:
    """``(outcome, problems)``: ``equal`` when KiCad draws exactly the prediction for ``size``."""
    text = board(size)
    case = export_sheet_svg(text, built(example))
    outcome = classify(case, default=sc.default(text=text), control=sc.control(text=text))
    if outcome != "load" or case.svg is None:
        return outcome, [f"{size}: verdict {outcome}"]
    sheet = read_drawing_sheet(built(example).read_text(encoding="utf-8"))
    texts, lines = prediction(sheet, case.svg, paper=PAPER_NAMES[size], block=ex.TITLE)
    found = problems_for(size, case.svg, texts, lines)
    return ("different" if found else "equal"), found


def broken(example: str) -> Path:
    """The generated sheet with ``(frobnicate 1)`` inserted as an item."""
    source = built(example).read_text(encoding="utf-8")
    path = _FOLDER / f"{example}-broken.kicad_wks"
    path.write_text(source.rstrip().removesuffix(")") + "\t(frobnicate 1)\n)\n", encoding="utf-8")
    return path


def controls(example: str) -> dict[str, str]:
    """The four controls of the acceptance run, on the first listed size's board."""
    text = board(EXAMPLE_SIZES[example][0])
    default, control = sc.default(text=text), sc.control(text=text)

    def verdict(sheet: Path | str | None, files: dict[str, bytes] | None = None) -> str:
        return classify(export_sheet_svg(text, sheet, files=files), default=default, control=control)

    project = {"board.kicad_pro": sc.project(sc.running_major(), sheet_key="missing.kicad_wks")}
    return {
        "broken": verdict(broken(example)),
        "missing-file": verdict("missing.kicad_wks"),
        "project-missing": verdict(None, project),
        "skeleton": verdict(SKELETON_SHEET),
    }


def accept_probes() -> dict[str, tuple[object, tuple[int, ...]]]:
    return {
        f"wks-accept-{example}-{size.lower()}": (lambda e=example, s=size: accept(e, s)[0], (9, 10))
        for example, sizes in EXAMPLE_SIZES.items()
        for size in sizes
    }


__all__ = [
    "EXAMPLE_SIZES",
    "accept",
    "accept_probes",
    "built",
    "controls",
    "prediction",
    "problems_for",
    "sha256",
]
