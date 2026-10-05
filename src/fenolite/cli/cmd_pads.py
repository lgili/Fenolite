# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite pads``: the pads of a board in the board frame, without running any tool.

It is the query a script author needs before writing a track by hand: where a pad is, on which layers
and on which net. The records are the backend's ``BoardPad`` (``docs/copper.md``); ``--origin`` reports
positions relative to a point, such as the DSL's board origin, so the numbers are the ones
``Design.track`` takes (``docs/dsl.md``, "Copper").
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fenolite.backends import registry
from fenolite.backends.base import BoardFrame, BoardPad
from fenolite.backends.kicad import frame
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.core.units import parse_length
from fenolite.geometry import Thick, thick_bbox
from fenolite.model.design import Design

HELP = "list the pads of a board in the board frame: position, layers, net (runs no tool)"
DEFAULT_ORIGIN = "0mm,0mm"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'pads'."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument(
        "ref", metavar="REF", nargs="?", help="only the pads of this part (path or reference)"
    )
    parser.add_argument("number", metavar="NUMBER", nargs="?", help="only the pads with this number")
    parser.add_argument(
        "--origin",
        default=DEFAULT_ORIGIN,
        metavar="X,Y",
        help="report positions relative to this point, two lengths with units (default 0mm,0mm)",
    )


def _origin(text: str) -> Point:
    parts = text.split(",")
    try:
        if len(parts) != 2:
            raise ValueError(f"expected two lengths separated by a comma, got {text!r}")
        return Point(parse_length(parts[0].strip()), parse_length(parts[1].strip()))
    except ValueError as error:
        raise CliError(
            "FEN-2001", f"--origin: {error}", where="--origin", hint="two lengths with units: 100mm,100mm"
        ) from None


def _box(pad: BoardPad, origin: Point) -> list[int] | None:
    """The bounding box of the pad's copper over its copper layers, relative to ``origin``."""
    boxes = [thick_bbox(Thick(entry.core, entry.width, entry.filled)) for entry in pad.copper]
    if not boxes:
        return None
    return [
        min(box.x0 for box in boxes) - origin.x,
        min(box.y0 for box in boxes) - origin.y,
        max(box.x1 for box in boxes) - origin.x,
        max(box.y1 for box in boxes) - origin.y,
    ]


def _selected(pads: Sequence[BoardPad], ref: str | None, number: str | None) -> list[BoardPad]:
    """The pads of ``ref`` (a component path first, else a reference, as ``find_pads`` matches) that carry
    ``number``."""
    if ref is None:
        return list(pads)
    matched = [pad for pad in pads if pad.path and pad.path == ref]
    if not matched:
        matched = [pad for pad in pads if pad.ref == ref]
    if not matched:
        known = sorted({name for pad in pads for name in (pad.path, pad.ref) if name})
        close = difflib.get_close_matches(ref, known, n=5, cutoff=0.0)
        hint = f"closest: {', '.join(close)}" if close else "the board holds no part"
        raise CliError("FEN-2001", f"no part {ref!r} on the board", where="REF", hint=hint)
    if number is None:
        return matched
    found = [pad for pad in matched if pad.number == number]
    if not found:
        numbers = ", ".join(dict.fromkeys(pad.number for pad in matched if pad.number))
        raise CliError(
            "FEN-2001", f"{ref} has no pad {number!r}", where="NUMBER", hint=f"pads of {ref}: {numbers}"
        )
    return found


def _rows(pads: Sequence[BoardPad], chosen: Sequence[BoardPad], origin: Point) -> list[dict[str, Any]]:
    """One object per chosen pad. ``index`` counts the pads of the same footprint with the same number, in
    pad order: the value that ``Part.pad(number, index=…)`` takes."""
    seen: Counter[tuple[str, str]] = Counter()
    index_of: dict[int, int] = {}
    for pad in pads:
        key = (pad.footprint_id, pad.number)
        index_of[id(pad)] = seen[key]
        seen[key] += 1
    rows: list[dict[str, Any]] = []
    for pad in chosen:
        holder = pad.ref or pad.footprint_id
        rows.append(
            {
                "where": f"{holder}-{pad.number}" if pad.number else holder,
                "ref": pad.ref,
                "number": pad.number,
                "index": index_of[id(pad)],
                "kind": pad.kind,
                "position": [pad.position.x - origin.x, pad.position.y - origin.y],
                "rotation": pad.rotation,
                "side": pad.side,
                "layers": list(pad.layers),
                "net": pad.net,
                "box": _box(pad, origin),
                "drill": pad.drill,
            }
        )
    return rows


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    origin = _origin(args.origin)
    given = Path(args.path)
    path = resolve_board(given if given.is_absolute() else ctx.cwd / given)
    backend = registry.for_path(path)
    if backend is None:
        raise CliError("FEN-2001", f"no backend reads {path.name}", hint="pass a board file")
    read = backend.read(path)
    design = read.content
    if not isinstance(design, Design) or design.board is None or not isinstance(backend, BoardFrame):
        raise CliError("FEN-2001", f"{path.name} is not a board", hint="pass a board file")
    found: list[Issue] = []
    pads = backend.board_pads(design, issues=found)
    chosen = _selected(pads, args.ref, None if args.number is None else str(args.number))
    rows = _rows(pads, chosen, origin)
    issues = [issue for issue in read.issues if issue.severity == "error"]
    return Result(
        result={"origin": [origin.x, origin.y], "count": len(rows), "pads": rows},
        issues=tuple(issues),
        evidence=Evidence.combine(read.evidence, frame.EVIDENCE),
        input=InputRef(
            path=path.name,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            kind="board",
            format_version=None,
        ),
    )


COMMAND = Command(
    name="pads",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_BOARD, "R1"),
)

__all__ = ["COMMAND"]
