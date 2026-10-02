# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Drawing-sheet bench (c0012 Decision 17; capability kicad-oracle, "Drawing sheets are judged by what
KiCad draws").

``export_sheet_svg`` runs ``pcb export svg <board> -l Edge.Cuts --mode-single [--drawing-sheet <f>]``
through c0009's isolated ``KicadCli.run`` and keeps the output lines and the SVG (memoised per session).
``classify`` judges a case by what KiCad drew, never by the exit code:

- ``reject``: the output holds ``DRAWING_SHEET_ERROR``;
- ``absent``: the drawn text multiset equals the default-sheet control of the same board (silent
  fallback);
- ``load``: it differs and the case's marker, if any, is drawn;
- ``different``: it differs but the marker is missing (KiCad drew another sheet);
- ``inconclusive``: the positive control is not ``load``, the default control draws no text, or KiCad
  wrote no SVG.

Semantic cases compare the drawing with a prediction (``compare``): every text at its x within 0.01 mm
and its y within half its text height, every line end within 0.01 mm.
"""

from __future__ import annotations

import hashlib
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from _svg import Segment, SheetSvg, SvgText, read_sheet_svg

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse, parse_fragment

ROOT = Path(__file__).resolve().parents[3]
SHEETS = ROOT / "tests" / "data" / "kicad" / "sheets"
SKELETON_BOARD = ROOT / "tests" / "data" / "kicad" / "tokens" / "skeleton.kicad_pcb"
SKELETON_SHEET = ROOT / "tests" / "data" / "kicad" / "tokens" / "skeleton.kicad_wks"
DRAWING_SHEET_ERROR = "Error loading drawing sheet"
BOARD_NAME = "board.kicad_pcb"
SVG_NAME = "out.svg"
TEXT_X_TOLERANCE = Decimal("0.01")
LINE_TOLERANCE = Decimal("0.01")
SVG_ROUNDING = Decimal("0.0001")  # the SVG writes four decimals


@dataclass(frozen=True)
class SheetCase:
    """One export: the run outcome (``exit`` or ``timeout``), its output lines and the SVG, if any."""

    outcome: str
    lines: tuple[str, ...]
    svg: SheetSvg | None

    @property
    def message(self) -> bool:
        return any(DRAWING_SHEET_ERROR in line for line in self.lines)

    def strings(self) -> list[str]:
        return [] if self.svg is None else self.svg.strings()


def board_text(*, paper: str, title_block: str = "") -> str:
    """c0007's skeleton board with its ``paper`` child replaced by ``paper`` (a fragment such as
    ``(paper "A3")``) and, when given, ``title_block`` inserted right after it (KiCad's order)."""
    root = parse(SKELETON_BOARD.read_text(encoding="utf-8"))
    children: list[Node | Atom] = []
    for child in root.children:
        if isinstance(child, Node) and child.name == "paper":
            children.append(parse_fragment(paper))
            if title_block:
                children.append(parse_fragment(title_block))
        else:
            children.append(child)
    return dumps(root.with_children(children), style="kicad")


def _key(board: str, sheet_arg: str | None, files: Mapping[str, bytes]) -> str:
    digest = hashlib.sha256(board.encode("utf-8"))
    digest.update(repr(sheet_arg).encode("utf-8"))
    for name in sorted(files):
        digest.update(name.encode("utf-8") + b"\0" + hashlib.sha256(files[name]).digest())
    return digest.hexdigest()


_CACHE: dict[str, SheetCase] = {}


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module through _sheetcases

    return probes_runner()


def export_sheet_svg(
    board: Path | str,
    sheet: Path | str | None,
    *,
    files: Mapping[str, bytes] | None = None,
) -> SheetCase:
    """Export ``board`` (a board file, or board text) with ``--drawing-sheet <sheet>``, or without it
    for ``None``, on the session's ``kicad-cli``.

    A ``Path`` sheet is copied next to the board under its own name; a ``str`` is passed as given and
    not copied (a missing file). ``files`` maps extra relative names to contents (a project).
    """
    if isinstance(board, Path):
        board = board.read_text(encoding="utf-8")
    extra = dict(files or {})
    sheet_arg: str | None = None
    if isinstance(sheet, Path):
        sheet_arg = sheet.name
        extra[sheet.name] = sheet.read_bytes()
    elif isinstance(sheet, str):
        sheet_arg = sheet
    key = _key(board, sheet_arg, extra)
    if key in _CACHE:
        return _CACHE[key]
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        board_path = folder / BOARD_NAME
        board_path.write_text(board, encoding="utf-8")
        copies = {BOARD_NAME: board_path}
        for name, data in extra.items():
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(data)
            copies[name] = folder / name
        args = ["pcb", "export", "svg", "-l", "Edge.Cuts", "--mode-single", "-o", SVG_NAME]
        if sheet_arg is not None:
            args += ["--drawing-sheet", sheet_arg]
        run = runner().run([*args, BOARD_NAME], files=copies)
    lines = tuple(line.strip() for line in (run.stdout + "\n" + run.stderr).splitlines() if line.strip())
    data = run.outputs.get(SVG_NAME)
    svg = None if data is None else read_sheet_svg(data.decode("utf-8"))
    case = SheetCase(run.outcome, lines, svg)
    _CACHE[key] = case
    return case


def _raw_class(case: SheetCase, default: SheetCase, marker: str | None) -> str:
    if case.outcome == "timeout":
        return "timeout"
    if case.message:
        return "reject"
    if case.svg is None:
        return "inconclusive"
    if case.strings() == default.strings():
        return "absent"
    if marker is None or marker in case.strings():
        return "load"
    return "different"


def classify(case: SheetCase, *, default: SheetCase, control: SheetCase, marker: str | None = None) -> str:
    """The verdict class of ``case`` against the same-session controls (module docstring)."""
    if default.svg is None or not default.svg.texts:
        return "inconclusive"
    if _raw_class(control, default, None) != "load":
        return "inconclusive"
    return _raw_class(case, default, marker)


@dataclass(frozen=True)
class Expected:
    """A predicted text (page mm): its string, anchor and text height."""

    text: str
    x: Decimal
    y: Decimal
    height: Decimal


def _text_matches(found: Sequence[SvgText], want: Expected) -> int | None:
    for i, item in enumerate(found):
        if (
            item.text == want.text
            and abs(item.x - want.x) <= TEXT_X_TOLERANCE
            and abs(item.y - want.y) <= want.height / 2 + SVG_ROUNDING
        ):
            return i
    return None


def _segment_found(paths: Sequence[Segment], line: tuple[Decimal, Decimal, Decimal, Decimal]) -> bool:
    x1, y1, x2, y2 = line
    for s in paths:
        for a, b, c, d in ((s.x1, s.y1, s.x2, s.y2), (s.x2, s.y2, s.x1, s.y1)):
            if all(abs(u - v) <= LINE_TOLERANCE for u, v in ((a, x1), (b, y1), (c, x2), (d, y2))):
                return True
    return False


def compare(
    svg: SheetSvg,
    texts: Sequence[Expected],
    lines: Sequence[tuple[Decimal, Decimal, Decimal, Decimal]] = (),
) -> list[str]:
    """The mismatches between ``svg`` and a prediction (empty when ``equal``): the drawn text multiset
    must equal the predicted one, each text in place, and every predicted line must be drawn."""
    problems: list[str] = []
    found = list(svg.texts)
    for want in texts:
        index = _text_matches(found, want)
        if index is None:
            near = [f"{t.text!r}@({t.x}, {t.y})" for t in found if t.text == want.text]
            where = ", ".join(near) or "nowhere"
            problems.append(f"text {want.text!r} not drawn at ({want.x}, {want.y}); drawn at {where}")
        else:
            found.pop(index)
    problems += [f"unpredicted text {t.text!r} at ({t.x}, {t.y})" for t in found]
    problems += [f"line {line} not drawn" for line in lines if not _segment_found(svg.paths, line)]
    return problems


__all__ = [
    "DRAWING_SHEET_ERROR",
    "SHEETS",
    "SKELETON_SHEET",
    "Expected",
    "SheetCase",
    "board_text",
    "classify",
    "compare",
    "export_sheet_svg",
    "runner",
]
