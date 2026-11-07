# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Review views of a board through ``kicad-cli`` (capability manufacturing-exports, "Render views"; facts:
``docs/formats/kicad/cli.md``, "Exports and renders").

Two SVG plots (``pcb export svg``) and two rendered PNG images (``pcb render``). A view is a review
artefact, never a verdict: a view that cannot be produced is reported, and nothing else changes.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from fenolite.backends.kicad.cli import RENDER_DIR, CliRun, KicadCli
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.model.presentation import PAPER_SIZES

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-EXPORT-RENDER",))
"""``KICAD-VERIFIED``: ``H-K-EXPORT-RENDER`` holds on 9.0.9 and 10.0.6 (c0024 task 6.2)."""
DEFAULT_WIDTH = 1600
DEFAULT_HEIGHT = 1200
FRONT_LAYERS = ("F.Cu", "F.SilkS", "F.Fab", "Edge.Cuts")
BACK_LAYERS = ("B.Cu", "B.SilkS", "B.Fab", "Edge.Cuts")


@dataclass(frozen=True, slots=True)
class View:
    """A review view: its file name, its kind and the side it shows."""

    name: str
    kind: Literal["svg", "png"]
    side: Literal["top", "bottom"]


VIEWS: Mapping[str, View] = MappingProxyType(
    {
        "front.svg": View("front.svg", "svg", "top"),
        "back.svg": View("back.svg", "svg", "bottom"),
        "top.png": View("top.png", "png", "top"),
        "bottom.png": View("bottom.png", "png", "bottom"),
    }
)


PageMode = Literal["sheet", "board"]
"""The page of an SVG plot (change c0409, B11): ``sheet`` plots the board on its drawing page, ``board``
plots the board area alone, without the drawing sheet (``--exclude-drawing-sheet --page-size-mode 2``;
``docs/formats/kicad/cli.md``, ``H-K-EXPORT-SVG-PAGE``)."""
BOARD_PAGE = ("--exclude-drawing-sheet", "--page-size-mode", "2")
_MM = 1_000_000
_OUTLINE = ("gr_line", "gr_arc", "gr_rect", "gr_circle", "gr_poly")
_POINTS = ("start", "end", "mid", "center")


def svg_arguments(view: View, page: PageMode = "sheet") -> list[str]:
    """``pcb export svg`` for one side, as one file: the back view is mirrored; ``page`` ``board`` plots
    the board area alone."""
    layers = FRONT_LAYERS if view.side == "top" else BACK_LAYERS
    args = ["pcb", "export", "svg", "--mode-single", "--layers", ",".join(layers)]
    if view.side == "bottom":
        args.append("--mirror")
    if page == "board":
        args.extend(BOARD_PAGE)
    return [*args, "-o", f"{RENDER_DIR}/{view.name}"]


def _nm(text: str) -> int | None:
    try:
        return int(Decimal(text) * _MM)
    except InvalidOperation:
        return None


def _xy(node: Node) -> tuple[int, int] | None:
    atoms = node.atoms()
    if len(atoms) < 2:
        return None
    x, y = _nm(atoms[0].value), _nm(atoms[1].value)
    return None if x is None or y is None else (x, y)


def _outline_points(root: Node) -> Iterator[tuple[int, int]]:
    """The points of the board's ``Edge.Cuts`` drawings; a circle gives the corners of its square."""
    for head in _OUTLINE:
        for shape in root.nodes(head):
            layer = shape.find("layer")
            if layer is None or not layer.atoms() or layer.atoms()[0].value != "Edge.Cuts":
                continue
            found: list[tuple[int, int]] = []
            for name in _POINTS:
                point = shape.find(name)
                xy = _xy(point) if point is not None else None
                if xy is not None:
                    found.append(xy)
            if head == "gr_circle" and len(found) == 2:  # (end) before (center) in _POINTS
                (ex, ey), (cx, cy) = found
                r = abs(ex - cx) + abs(ey - cy)  # a bound of the radius
                found = [(cx - r, cy - r), (cx + r, cy + r)]
            yield from found
            pts = shape.find("pts")
            for xy in pts.nodes("xy") if pts is not None else ():
                point = _xy(xy)
                if point is not None:
                    yield point


def _sheet(root: Node) -> tuple[int, int] | None:
    """The page's width and height, landscape unless the board says ``portrait``."""
    paper = root.find("paper")
    atoms = paper.atoms() if paper is not None else ()
    if not atoms:
        return None
    name = atoms[0].value
    if name == "User" and len(atoms) >= 3:
        width, height = _nm(atoms[1].value), _nm(atoms[2].value)
        return None if width is None or height is None else (width, height)
    size = PAPER_SIZES.get(name)
    if size is None:
        return None
    short, long = size
    return (short, long) if any(atom.value == "portrait" for atom in atoms[1:]) else (long, short)


def board_page(text: str) -> PageMode:
    """``board`` when the outline of the board ``text`` holds reaches outside its drawing page, so a plot
    on the page would cut it off or leave it out; ``sheet`` otherwise, or when the page or the outline is
    not read."""
    try:
        root = parse(text)
    except FormatError:
        return "sheet"
    sheet = _sheet(root)
    points = list(_outline_points(root))
    if sheet is None or not points:
        return "sheet"
    width, height = sheet
    inside = all(0 <= x <= width and 0 <= y <= height for x, y in points)
    return "sheet" if inside else "board"


def _first_line(run: CliRun) -> str:
    lines = [line.strip() for line in (run.stderr or run.stdout).splitlines() if line.strip()]
    return lines[0].replace("<tmp>/", "").replace("<tmp>", ".") if lines else ""


def plot_view(
    cli: KicadCli,
    name: str,
    board: Path,
    files: Mapping[str, Path],
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    page: PageMode = "sheet",
) -> tuple[bytes | None, str]:
    """``(data, message)`` for the view ``name`` of a copy of ``board``: the file's bytes, or ``None`` and
    why (a timeout, a non-zero exit, no file). ``page`` is the page of an SVG plot."""
    view = VIEWS[name]
    if view.kind == "svg":
        run = cli.export(svg_arguments(view, page), board, files=files, out=RENDER_DIR)
        produced = f"{RENDER_DIR}/{view.name}"
    else:
        run = cli.render(board, side=view.side, width=width, height=height, files=files)
        produced = f"{RENDER_DIR}/{view.side}.png"
    if run.outcome == "timeout":
        return None, f"kicad-cli timed out after {cli.timeout:g} s"
    data = run.outputs.get(produced)
    if run.returncode != 0 or not data:
        return None, f"exit {run.returncode}: {_first_line(run) or 'kicad-cli wrote no file'}"
    return data, ""


def view_digest(name: str, data: bytes) -> str:
    """The SHA-256 of a view for comparing two plots: an SVG without its ``<title>`` line, where
    ``kicad-cli`` 9.0 writes the date; a PNG as it is."""
    if VIEWS[name].kind == "svg":
        lines = data.splitlines(keepends=True)
        data = b"".join(line for line in lines if not line.lstrip().startswith(b"<title>"))
    return hashlib.sha256(data).hexdigest()


def png_size(data: bytes) -> tuple[int, int] | None:
    """``(width, height)`` from a PNG's header, or ``None`` when ``data`` is no PNG."""
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


__all__ = [
    "BACK_LAYERS",
    "BOARD_PAGE",
    "DEFAULT_HEIGHT",
    "DEFAULT_WIDTH",
    "EVIDENCE",
    "FRONT_LAYERS",
    "VIEWS",
    "PageMode",
    "View",
    "board_page",
    "plot_view",
    "png_size",
    "svg_arguments",
    "view_digest",
]
