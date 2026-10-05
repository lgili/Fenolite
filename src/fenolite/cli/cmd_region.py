# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite region PATH --box X1,Y1,X2,Y2``: what a rectangle of the board holds (capability
cli-contract, "Region command"; ``docs/cli-contract.md``, "region"). Runs no tool."""

from __future__ import annotations

import argparse
from collections import Counter
from typing import Any

from fenolite.analysis.views import ALL_KINDS, region_view
from fenolite.cli._boardview import UNIT_HINT, length, load_board, to_json
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.geometry import BBox

HELP = "list the footprints, pads, copper, zones and texts that touch a rectangle of a board (runs no tool)"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'region'."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument(
        "--box", required=True, metavar="X1,Y1,X2,Y2", help="two corners with units: 10mm,5mm,30mm,20mm"
    )
    parser.add_argument("--layer", metavar="NAME", help="keep only the items on this layer")
    parser.add_argument("--kinds", metavar="A,B", help=f"keep only these kinds, of {','.join(ALL_KINDS)}")


def _box(text: str) -> BBox:
    parts = [part for part in text.split(",")]
    if len(parts) != 4:
        raise CliError("FEN-2001", "--box takes four lengths: X1,Y1,X2,Y2", where="--box", hint=UNIT_HINT)
    x1, y1, x2, y2 = (length(part, "--box") for part in parts)
    if x1 == x2 or y1 == y2:
        raise CliError("FEN-2001", "--box: the rectangle has no area", where="--box")
    return BBox(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def _kinds(text: str | None) -> tuple[str, ...]:
    if text is None:
        return ALL_KINDS
    names = [name.strip() for name in text.split(",")]
    bad = [name for name in names if name not in ALL_KINDS]
    if bad or not names:
        raise CliError(
            "FEN-2001",
            f"--kinds: unknown kind {bad[0]!r}",
            where="--kinds",
            hint=f"kinds: {','.join(ALL_KINDS)}",
        )
    return tuple(kind for kind in ALL_KINDS if kind in names)


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    box = _box(args.box)
    kinds = _kinds(args.kinds)
    view = load_board(args.path, ctx)
    items = region_view(view.design, box, pads=view.pads, extents=view.extents, layer=args.layer, kinds=kinds)
    counted = Counter(item.kind for item in items)
    result: dict[str, Any] = {
        "box": to_json(box),
        "layer": args.layer,
        "counts": {kind: counted[kind] for kind in kinds},
        "items": to_json(items),
    }
    return Result(result=result, issues=view.issues, evidence=view.evidence, input=view.input)


COMMAND = Command(
    name="region",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    paged="items",
    example_args=(EXAMPLE_BOARD, "--box", "0mm,0mm,300mm,200mm"),
)
